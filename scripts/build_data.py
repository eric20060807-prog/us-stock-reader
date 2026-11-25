"""抓取行情、宏观数据和新闻，计算信号，生成 data/market.json 供网页读取。

由 GitHub Actions 定时运行（见 .github/workflows/update.yml），也可以本地运行：
    pip install -r scripts/requirements.txt
    python scripts/build_data.py
"""
import datetime as dt
import html
import io
import json
import math
import os
import re
import sys
import tempfile
import time

import feedparser
import numpy as np
import pandas as pd
import requests
import yfinance as yf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from universe import CROSS_ASSET, FEEDS, FRED, INDICES, SECTORS  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "market.json")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
SEC_UA = "MarketPulse research bot admin@example.com"  # 美国证监会要求带联系方式的 User-Agent

try:
    yf.set_tz_cache_location(tempfile.mkdtemp())
except Exception:
    pass


def log(*a):
    print(*a, flush=True)


def clean(x, nd=4):
    """把 numpy / NaN 转成可写入 JSON 的数值。"""
    if x is None:
        return None
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    if math.isnan(x) or math.isinf(x):
        return None
    return round(x, nd)


# ----------------------------------------------------------------------------- 行情

def download(tickers):
    close, vol = pd.DataFrame(), pd.DataFrame()
    try:
        raw = yf.download(tickers, period="2y", interval="1d", auto_adjust=True, progress=False, threads=True)
        close, vol = raw["Close"].copy(), raw["Volume"].copy()
    except Exception as e:
        log("批量下载失败：", e)
    for t in tickers:
        if t in close.columns and close[t].dropna().size > 30:
            continue
        for i in range(3):
            try:
                r = yf.download(t, period="2y", interval="1d", auto_adjust=True, progress=False, threads=False)
                if r is not None and not r.empty:
                    c, v = r["Close"], r["Volume"]
                    close[t] = c.iloc[:, 0] if isinstance(c, pd.DataFrame) else c
                    vol[t] = v.iloc[:, 0] if isinstance(v, pd.DataFrame) else v
                    break
            except Exception as e:
                log(f"  {t} 第 {i + 1} 次下载失败：{e}")
            time.sleep(2 * (i + 1))
    close.index = pd.to_datetime(close.index).tz_localize(None)
    vol.index = pd.to_datetime(vol.index).tz_localize(None)
    return close.sort_index(), vol.sort_index()


def rsi(s, n=14):
    d = s.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)


def returns(s):
    last = s.iloc[-1]

    def r(n):
        return clean(last / s.iloc[-n - 1] - 1) if len(s) > n else None

    prev_year = s[s.index.year < s.index[-1].year]
    ytd = clean(last / prev_year.iloc[-1] - 1) if len(prev_year) else None
    return {"chg1": r(1), "r5": r(5), "r21": r(21), "r63": r(63), "ytd": ytd}


def _bucket(x):
    return 0 if x < 15 else (2 if x > 85 else 1)


def analyze_stock(s, v):
    s = s.dropna()
    if len(s) < 60:
        return None
    v = v.reindex(s.index).fillna(0)
    last = float(s.iloc[-1])
    sma50s, sma200s = s.rolling(50).mean(), s.rolling(200).mean()
    ema20s = s.ewm(span=20, adjust=False).mean()
    s50, s200, e20 = float(sma50s.iloc[-1]), float(sma200s.iloc[-1]), float(ema20s.iloc[-1])
    r14s, r2s = rsi(s, 14), rsi(s, 2)
    r14, r2 = float(r14s.iloc[-1]), float(r2s.iloc[-1])
    atr = float(s.diff().abs().rolling(14).mean().iloc[-1])
    vol = float(np.log(s).diff().iloc[-60:].std())
    hi52, lo52 = float(s.iloc[-252:].max()), float(s.iloc[-252:].min())
    avgv = float(v.iloc[-21:-1].mean())
    volratio = float(v.iloc[-1]) / avgv if avgv > 0 else None
    rising = ema20s.iloc[-1] > ema20s.iloc[-6]
    has200 = not math.isnan(s200)

    if has200 and last < s200:
        level, status = 0, "弱势"
    elif has200 and last > e20 > s50 > s200 and rising:
        level, status = 3, "强势上涨"
    elif last > s50 and (not has200 or s50 > s200):
        level, status = 2, "偏强"
    else:
        level, status = 1, "震荡"

    # 买入区 / 止损 / 目标
    zlo, zhi = e20 - 0.5 * atr, e20 + 0.5 * atr
    if zlo <= last <= zhi or (last < zlo and last >= s50):
        ref, how = last, "现价在买入区内"
    elif last > zhi:
        ref, how = (zlo + zhi) / 2, f"等回调到 {zlo:.2f}–{zhi:.2f}"
    else:
        ref, how = max(s50, zlo), f"等站回 {s50:.2f}（50日线）"
    stop = ref - 2 * atr
    target = ref + 2 * (ref - stop)

    # 短线：历史同类情况 3 天后的表现
    cur_b, cur_up = _bucket(r2), (last > s200) if has200 else True
    hist = pd.DataFrame({"b": r2s.map(_bucket), "up": s > sma200s, "f": s.shift(-3) / s - 1})
    hist = hist[sma200s.notna()].dropna()
    m = hist[(hist["b"] == cur_b) & (hist["up"] == cur_up)]
    n3 = len(m)
    p3 = float((m["f"] > 0).mean()) if n3 else None
    a3 = float(m["f"].mean()) if n3 else None
    if level == 0:
        act = "回避"
    elif cur_b == 0 and level >= 2:
        act = "短线买点"
    elif cur_b == 2 or r14 > 75:
        act = "过热勿追"
    elif level == 1:
        act = "观望"
    else:
        act = "持有/等回调"

    crossed_down = has200 and last < s200 and (s.iloc[-6:-1] > sma200s.iloc[-6:-1]).any()
    out = returns(s)
    out.update({
        "last": clean(last, 2), "level": level, "status": status, "action": act,
        "rsi": clean(r14, 1), "rsi2": clean(r2, 1),
        "sma50": clean(s50, 2), "sma200": clean(s200, 2), "ema20": clean(e20, 2),
        "hi52": clean(hi52, 2), "lo52": clean(lo52, 2), "off_hi": clean(last / hi52 - 1),
        "volratio": clean(volratio, 2),
        "ref": clean(ref, 2), "how": how, "stop": clean(stop, 2), "target": clean(target, 2),
        "breakout": clean(float(s.iloc[-20:].max()) * 1.005, 2),
        "range3": [clean(last * math.exp(-vol * math.sqrt(3)), 2), clean(last * math.exp(vol * math.sqrt(3)), 2)],
        "range21": [clean(last * math.exp(-vol * math.sqrt(21)), 2), clean(last * math.exp(vol * math.sqrt(21)), 2)],
        "p3": clean(p3, 3), "a3": clean(a3), "n3": n3,
        "crossed_down": bool(crossed_down),
        "chart": [clean(x, 2) for x in s.iloc[-130:].tolist()],
        "chart_start": s.index[-130 if len(s) >= 130 else 0].strftime("%Y-%m-%d"),
    })
    return out


def spark(s, n=90):
    return [clean(x, 4) for x in s.dropna().iloc[-n:].tolist()]


# ----------------------------------------------------------------------------- 慢速数据（每天刷新一次）

def slow_data(stocks, prev):
    today = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    cache = (prev or {}).get("cache") or {}
    if cache.get("date") == today and cache.get("caps"):
        log("市值 / 财报日期：使用今天已缓存的数据")
        return cache
    log("刷新市值和财报日期……")
    caps, earn = {}, {}
    for t in stocks:
        try:
            tk = yf.Ticker(t)
            fi = tk.fast_info
            cap = None
            for key in ("market_cap", "marketCap"):
                try:
                    cap = fi[key]
                    break
                except Exception:
                    continue
            if cap:
                caps[t] = float(cap)
            try:
                cal = tk.calendar
                ed = cal.get("Earnings Date") if isinstance(cal, dict) else None
                if ed:
                    d = ed[0] if isinstance(ed, (list, tuple)) else ed
                    earn[t] = pd.Timestamp(d).strftime("%Y-%m-%d")
            except Exception:
                pass
        except Exception as e:
            log(f"  {t}：{e}")
    if not caps and cache.get("caps"):
        return cache
    return {"date": today, "caps": caps, "earn": earn}


# ----------------------------------------------------------------------------- 宏观（FRED）

def fred():
    out = []
    for sid, label, unit, kind in FRED:
        try:
            r = requests.get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}", headers={"User-Agent": UA}, timeout=25)
            r.raise_for_status()
            df = pd.read_csv(io.StringIO(r.text))
            df.columns = ["date", "v"]
            df["v"] = pd.to_numeric(df["v"], errors="coerce")
            df = df.dropna()
            df["date"] = pd.to_datetime(df["date"])
            s = df.set_index("date")["v"]
            if kind == "yoy":
                s = (s / s.shift(12) - 1) * 100
            elif kind == "diff":
                s = s.diff()
            s = s.dropna()
            if s.empty:
                continue
            daily = (s.index[-1] - s.index[-2]).days < 7 if len(s) > 1 else False
            hist = s.iloc[-120:] if daily else s.iloc[-24:]
            out.append({
                "id": sid, "label": label, "unit": unit,
                "value": clean(s.iloc[-1], 2), "prev": clean(s.iloc[-2], 2) if len(s) > 1 else None,
                "date": s.index[-1].strftime("%Y-%m-%d"), "freq": "日" if daily else ("季" if sid.startswith("A191") else "月/周"),
                "spark": [clean(x, 3) for x in hist.tolist()],
            })
        except Exception as e:
            log(f"FRED {sid} 失败：{e}")
    return out


# ----------------------------------------------------------------------------- 新闻

TOPICS = [
    (r"\b(fomc|federal reserve|the fed|fed's|powell|rate cuts?|rate hikes?|interest rates?|monetary policy|central bank)\b", 3, "美联储/利率"),
    (r"\b(inflation|cpi|pce|consumer prices?|price index)\b", 3, "通胀"),
    (r"\b(jobs report|payrolls?|unemployment|jobless|labor market|employment situation)\b", 3, "就业"),
    (r"\b(gdp|recession|economic growth|retail sales|consumer spending)\b", 2.5, "经济增长"),
    (r"\b(tariffs?|trade war|trade deal|export controls?|sanctions?|import duties)\b", 3, "关税/贸易"),
    (r"\b(executive order|proclamation|white house|congress|senate|shutdown|debt ceiling|budget|tax bill|legislation)\b", 2, "政策/立法"),
    (r"\b(treasury|yields?|bond market|bonds)\b", 1.5, "债市"),
    (r"\b(earnings|revenue|guidance|outlook|quarterly results|beats|misses)\b", 1, "财报"),
    (r"\b(ai|artificial intelligence|chips?|semiconductors?|data centers?|gpu)\b", 1, "AI/芯片"),
    (r"\b(oil|opec|crude|natural gas)\b", 1.5, "能源"),
    (r"\b(sec|antitrust|lawsuit|probe|investigation|regulators?)\b", 1, "监管"),
    (r"\b(china|beijing|taiwan|europe|ecb|japan|boj)\b", 1, "国际"),
]
OFFICIAL = {"央行", "政策", "监管", "经济数据"}


def strip_html(x):
    x = re.sub(r"<[^>]+>", " ", x or "")
    return re.sub(r"\s+", " ", html.unescape(x)).strip()


def news(name_map):
    now = dt.datetime.now(dt.timezone.utc)
    items, seen = [], set()
    patterns = []
    for sym, (cn, en) in name_map.items():
        pats = [re.escape(en)]
        if len(sym) >= 3 and sym.isalpha():
            pats.append(r"\b" + re.escape(sym) + r"\b")
        patterns.append((sym, re.compile(r"(?:^|\W)(" + "|".join(pats) + r")(?:\W|$)")))
    for source, url, cat in FEEDS:
        try:
            ua = SEC_UA if "sec.gov" in url else UA
            r = requests.get(url, headers={"User-Agent": ua, "Accept": "application/rss+xml, application/xml, text/xml, */*"}, timeout=25)
            r.raise_for_status()
            feed = feedparser.parse(r.content)
        except Exception as e:
            log(f"新闻源 {source} 失败：{e}")
            continue
        n_ok = 0
        for e in feed.entries[:40]:
            title = strip_html(e.get("title", ""))
            link = e.get("link", "")
            if not title or not link:
                continue
            key = re.sub(r"\W+", "", title.lower())[:80]
            if key in seen:
                continue
            tp = e.get("published_parsed") or e.get("updated_parsed")
            when = dt.datetime(*tp[:6], tzinfo=dt.timezone.utc) if tp else None
            max_age = 10 if cat in OFFICIAL else 3
            if when and (now - when).days > max_age:
                continue
            seen.add(key)
            summary = strip_html(e.get("summary", ""))
            if len(summary) > 180:
                summary = summary[:177].rsplit(" ", 1)[0] + "…"
            text = f"{title} {summary}".lower()
            score, tags = 0.0, []
            for pat, w, tag in TOPICS:
                if re.search(pat, text):
                    score += w
                    tags.append(tag)
            tickers = [sym for sym, p in patterns if p.search(f"{title} {summary}")][:5]
            score += 2 if cat in OFFICIAL else 0
            score += 0.5 * len(tickers)
            items.append({
                "title": title, "link": link, "source": source, "cat": cat,
                "time": when.isoformat() if when else None, "summary": summary,
                "tags": tags[:4], "tickers": tickers, "score": round(min(score, 10), 1),
            })
            n_ok += 1
        log(f"新闻源 {source}：{n_ok} 条")
    items.sort(key=lambda x: x["time"] or "", reverse=True)
    return items[:150]


# ----------------------------------------------------------------------------- 汇总

def pct_txt(x):
    if x is None:
        return "—"
    t = f"{x * 100:+.2f}%"
    return "0.00%" if t in ("+0.00%", "-0.00%") else t


def main():
    prev = None
    if os.path.exists(OUT):
        try:
            with open(OUT, encoding="utf-8") as f:
                prev = json.load(f)
        except Exception:
            prev = None

    name_map, sector_of = {}, {}
    for etf, (cn, members) in SECTORS.items():
        for sym, names in members.items():
            name_map[sym] = names
            sector_of[sym] = etf
    stocks = list(name_map)
    tickers = stocks + list(SECTORS) + list(INDICES) + list(CROSS_ASSET)
    log(f"下载 {len(tickers)} 个行情……")
    close, vol = download(tickers)
    if close.empty:
        raise SystemExit("没有下载到任何行情，退出（保留旧数据）")
    as_of = close["^GSPC"].dropna().index[-1] if "^GSPC" in close else close.index[-1]

    # 指数与跨资产
    def quote(t, label):
        s = close[t].dropna() if t in close else pd.Series(dtype=float)
        if len(s) < 2:
            return None
        return {"sym": t, "name": label, "last": clean(s.iloc[-1], 4), "chg1": clean(s.iloc[-1] / s.iloc[-2] - 1),
                "diff": clean(s.iloc[-1] - s.iloc[-2], 4), **{k: v for k, v in returns(s).items() if k != "chg1"},
                "spark": spark(s, 90)}

    indices = [q for t, n in INDICES.items() if (q := quote(t, n))]
    cross = [q for t, n in CROSS_ASSET.items() if (q := quote(t, n))]

    # 个股
    data = {}
    for sym in stocks:
        if sym not in close:
            continue
        try:
            a = analyze_stock(close[sym], vol[sym] if sym in vol else pd.Series(dtype=float))
        except Exception as e:
            log(f"{sym} 计算失败：{e}")
            a = None
        if a:
            a["name"], a["en"] = name_map[sym]
            a["sector"] = sector_of[sym]
            data[sym] = a
    log(f"成功计算 {len(data)} 只股票")

    cache = slow_data(list(data), prev)
    for sym, a in data.items():
        a["cap"] = cache.get("caps", {}).get(sym)
        a["earn"] = cache.get("earn", {}).get(sym)

    # 板块
    sectors = []
    for etf, (cn, members) in SECTORS.items():
        if etf not in close:
            continue
        s = close[etf].dropna()
        mem = [data[m] for m in members if m in data]
        row = {"etf": etf, "name": cn, **returns(s), "spark": spark(s, 90),
               "adv": sum(1 for m in mem if (m["chg1"] or 0) > 0), "n": len(mem),
               "above200": clean(np.mean([m["level"] > 0 for m in mem])) if mem else None,
               "members": [m for m in members if m in data]}
        sectors.append(row)

    # 市场宽度与情绪
    vals = list(data.values())
    adv = sum(1 for a in vals if (a["chg1"] or 0) > 0)
    dec = sum(1 for a in vals if (a["chg1"] or 0) < 0)
    above200 = np.mean([a["level"] > 0 for a in vals]) if vals else 0
    above50 = np.mean([a["last"] > a["sma50"] for a in vals if a["sma50"]]) if vals else 0
    new_hi = [s for s, a in data.items() if a["off_hi"] is not None and a["off_hi"] >= -0.01]
    vix = close["^VIX"].dropna() if "^VIX" in close else pd.Series(dtype=float)
    spx = close["^GSPC"].dropna() if "^GSPC" in close else pd.Series(dtype=float)
    comps = {}
    if len(vix) > 252:
        lo, hi = vix.iloc[-252:].min(), vix.iloc[-252:].max()
        comps["波动率（VIX 越低越贪婪）"] = float(1 - (vix.iloc[-1] - lo) / (hi - lo)) * 100 if hi > lo else 50
    if len(spx) > 130:
        gap = spx.iloc[-1] / spx.rolling(125).mean().iloc[-1] - 1
        comps["标普相对 125 日均线"] = float(np.clip(50 + gap * 500, 0, 100))
    comps["站上 200 日线的股票比例"] = float(above200 * 100)
    comps["站上 50 日线的股票比例"] = float(above50 * 100)
    comps["今日上涨家数占比"] = float(adv / max(adv + dec, 1) * 100)
    score = float(np.mean(list(comps.values())))
    label = "极度恐惧" if score < 25 else "恐惧" if score < 45 else "中性" if score <= 55 else "贪婪" if score <= 75 else "极度贪婪"
    sentiment = {"score": round(score), "label": label, "components": {k: round(v) for k, v in comps.items()}}
    breadth = {"adv": adv, "dec": dec, "above200": clean(above200), "above50": clean(above50),
               "new_hi": len(new_hi), "total": len(vals)}

    # 机会与风险清单
    df = pd.DataFrame({s: {"r21": a["r21"] or 0, "r63": a["r63"] or 0} for s, a in data.items()}).T
    score_mom = (df["r21"].rank(pct=True) * 0.5 + df["r63"].rank(pct=True) * 0.5).to_dict() if len(df) else {}
    for s in data:
        data[s]["mom_score"] = clean(score_mom.get(s), 3)

    def pick(cond, key, rev=True, n=12):
        rows = [(s, a) for s, a in data.items() if cond(a)]
        rows.sort(key=lambda x: (key(x[1]) if key(x[1]) is not None else -1e9), reverse=rev)
        return [s for s, _ in rows[:n]]

    opps = {
        "trend": {"title": "趋势强势", "desc": "长短期均线多头排列、RSI 未过热，按近 1 个月和 3 个月涨幅综合排名",
                  "items": pick(lambda a: a["level"] == 3 and 45 <= (a["rsi"] or 0) <= 72, lambda a: a["mom_score"])},
        "dip": {"title": "短线买点", "desc": "处在上升趋势中，但最近 2 天急跌（2 日 RSI < 15），历史上常见短线反弹",
                "items": pick(lambda a: a["action"] == "短线买点", lambda a: a["r63"])},
        "volume": {"title": "放量异动", "desc": "成交量是 20 日均量的 2 倍以上，且当日涨跌超过 3%，常与消息或资金动向有关",
                   "items": pick(lambda a: (a["volratio"] or 0) >= 2 and abs(a["chg1"] or 0) >= 0.03, lambda a: a["volratio"])},
        "high": {"title": "创 52 周新高", "desc": "价格距离一年最高点不到 1%，处于突破状态",
                 "items": pick(lambda a: a["off_hi"] is not None and a["off_hi"] >= -0.01, lambda a: a["r21"])},
        "oversold": {"title": "超卖观察", "desc": "长期趋势尚未破坏，但 RSI 低于 35，等企稳信号再考虑",
                     "items": pick(lambda a: a["level"] >= 1 and (a["rsi"] or 50) < 35, lambda a: a["rsi"], rev=False)},
        "risk": {"title": "风险警示", "desc": "最近 5 个交易日内刚跌破 200 日均线，长期趋势转弱",
                 "items": pick(lambda a: a["crossed_down"], lambda a: a["chg1"], rev=False)},
    }
    movers = {
        "gainers": pick(lambda a: a["chg1"] is not None, lambda a: a["chg1"], n=10),
        "losers": pick(lambda a: a["chg1"] is not None, lambda a: a["chg1"], rev=False, n=10),
    }

    # 宏观、新闻、财报
    macro = fred()
    if not macro and prev:
        macro = prev.get("macro", [])
    news_items = news(name_map)
    if not news_items and prev:
        news_items = prev.get("news", [])
    today = pd.Timestamp(dt.date.today())
    earnings = sorted(
        [{"sym": s, "date": a["earn"]} for s, a in data.items()
         if a.get("earn") and today <= pd.Timestamp(a["earn"]) <= today + pd.Timedelta(days=21)],
        key=lambda x: (x["date"], -(data[x["sym"]].get("cap") or 0)))

    # 今日速览（规则生成）
    idx = {q["sym"]: q for q in indices}
    cr = {q["sym"]: q for q in cross}
    brief = []
    parts = [f"{idx[t]['name']} {pct_txt(idx[t]['chg1'])}" for t in ("^GSPC", "^IXIC", "^DJI") if t in idx]
    if parts:
        brief.append("、".join(parts) + "。")
    srt = sorted([s for s in sectors if s["chg1"] is not None], key=lambda s: s["chg1"], reverse=True)
    if srt:
        up_n = sum(1 for s in srt if s["chg1"] > 0)
        brief.append(f"{len(srt)} 个行业中 {up_n} 个上涨，{srt[0]['name']}领涨（{pct_txt(srt[0]['chg1'])}），"
                     f"{srt[-1]['name']}{'领跌' if srt[-1]['chg1'] < 0 else '涨幅最小'}（{pct_txt(srt[-1]['chg1'])}）。")
    if "^TNX" in cr and cr["^TNX"]["diff"] is not None:
        brief.append(f"10 年期美债收益率 {cr['^TNX']['last']:.2f}%（{cr['^TNX']['diff'] * 100:+.0f} 个基点）。")
    if "^VIX" in idx:
        v = idx["^VIX"]["last"]
        mood = "市场情绪平静" if v < 15 else "波动处于正常水平" if v < 20 else "市场明显紧张" if v < 30 else "市场处于恐慌状态"
        brief.append(f"VIX 为 {v:.1f}，{mood}。")
    brief.append(f"股票池中 {adv} 只上涨、{dec} 只下跌，{above200:.0%} 的股票站在 200 日均线之上。")
    if movers["gainers"]:
        g = data[movers["gainers"][0]]
        brief.append(f"涨幅最大的是 {g['name']}（{movers['gainers'][0]}，{pct_txt(g['chg1'])}）。")
    imp = [n for n in news_items if n["cat"] in OFFICIAL]
    if imp:
        brief.append(f"最新官方动态：{imp[0]['source']} — {imp[0]['title']}")

    out = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "as_of": as_of.strftime("%Y-%m-%d"),
        "brief": brief, "indices": indices, "cross": cross, "sentiment": sentiment, "breadth": breadth,
        "sectors": sectors, "stocks": data, "opportunities": opps, "movers": movers,
        "news": news_items, "macro": macro, "earnings": earnings, "cache": cache,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, OUT)
    log(f"已写入 {OUT}（{os.path.getsize(OUT) / 1024:.0f} KB）")


if __name__ == "__main__":
    main()
