/* 美股雷达：读取 data/market.json 并渲染页面 */
(() => {
  "use strict";
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  const UP = "#3DDC97", DOWN = "#FF5C7A", ICE = "#7FE7FF", DIM = "#5D6F92";
  const LEVEL_TXT = ["弱势", "震荡", "偏强", "强势上涨"];
  const ACTION_COLOR = { "短线买点": UP, "持有/等回调": "#9BE8C4", "观望": "#FFC857", "过热勿追": "#FFC857", "回避": DOWN };
  const PERIOD_LIM = { chg1: 0.03, r5: 0.06, r21: 0.12, r63: 0.2, ytd: 0.4 };
  const PERIOD_TXT = { chg1: "今日", r5: "一周", r21: "一个月", r63: "三个月", ytd: "今年以来" };

  let D = null;
  const state = { mapP: "chg1", secP: "chg1", radar: "trend", newsSort: "score", newsTag: "", sortK: "chg1", sortDir: -1 };

  // ------------------------------------------------------------------ 格式化
  const cls = (x) => (x == null ? "flat" : x > 0.00005 ? "up" : x < -0.00005 ? "down" : "flat");
  const pct = (x, d = 2) => {
    if (x == null) return "—";
    const t = (x * 100).toFixed(d);
    return Number(t) === 0 ? (0).toFixed(d) + "%" : (x > 0 ? "+" : "") + t + "%";
  };
  const num = (x, d = 2) => (x == null ? "—" : Number(x).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d }));
  const price = (x) => (x == null ? "—" : "$" + num(x, x >= 1000 ? 0 : 2));
  const cap = (x) => (!x ? "—" : x >= 1e12 ? "$" + (x / 1e12).toFixed(2) + " 万亿" : "$" + Math.round(x / 1e8).toLocaleString() + " 亿");
  const span = (x, d) => `<span class="${cls(x)}">${pct(x, d)}</span>`;
  function ago(iso) {
    if (!iso) return "";
    const m = (Date.now() - new Date(iso).getTime()) / 60000;
    if (m < 1) return "刚刚";
    if (m < 60) return Math.round(m) + " 分钟前";
    if (m < 60 * 24) return Math.round(m / 60) + " 小时前";
    return Math.round(m / 1440) + " 天前";
  }

  function sparkSVG(arr, w = 120, h = 34, color, fill = true) {
    const v = (arr || []).filter((x) => x != null);
    if (v.length < 2) return `<svg viewBox="0 0 ${w} ${h}" aria-hidden="true"></svg>`;
    const lo = Math.min(...v), hi = Math.max(...v), r = hi - lo || 1;
    const pts = v.map((y, i) => [(i / (v.length - 1)) * w, h - 2 - ((y - lo) / r) * (h - 4)]);
    const d = pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1)).join("");
    const c = color || (v[v.length - 1] >= v[0] ? UP : DOWN);
    const id = "g" + Math.random().toString(36).slice(2, 8);
    return `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-hidden="true">
      ${fill ? `<defs><linearGradient id="${id}" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="${c}" stop-opacity=".28"/><stop offset="1" stop-color="${c}" stop-opacity="0"/></linearGradient></defs>
      <path d="${d}L${w} ${h}L0 ${h}Z" fill="url(#${id})"/>` : ""}
      <path d="${d}" fill="none" stroke="${c}" stroke-width="1.6" vector-effect="non-scaling-stroke"/></svg>`;
  }

  function mix(a, b, t) { return a.map((x, i) => Math.round(x + (b[i] - x) * t)); }
  function heat(v, lim) {
    if (v == null) return "rgb(38,50,78)";
    const t = Math.max(-1, Math.min(1, v / lim));
    const n = [38, 50, 78], u = [22, 168, 104], d = [214, 46, 82];
    const c = t >= 0 ? mix(n, u, Math.pow(t, 0.8)) : mix(n, d, Math.pow(-t, 0.8));
    return `rgb(${c.join(",")})`;
  }

  // ------------------------------------------------------------------ 时钟与开盘状态
  function tick() {
    const now = new Date();
    const parts = Object.fromEntries(new Intl.DateTimeFormat("en-US", { timeZone: "America/New_York", hour12: false, weekday: "short", hour: "2-digit", minute: "2-digit", second: "2-digit" })
      .formatToParts(now).map((p) => [p.type, p.value]));
    const h = +parts.hour % 24, m = +parts.minute, mins = h * 60 + m, wk = !["Sat", "Sun"].includes(parts.weekday);
    $("#ny-clock").textContent = `美东 ${String(h).padStart(2, "0")}:${parts.minute}:${parts.second}`;
    let st = "休市", open = false;
    if (wk && mins >= 570 && mins < 960) { st = "交易中"; open = true; }
    else if (wk && mins >= 240 && mins < 570) st = "盘前";
    else if (wk && mins >= 960 && mins < 1200) st = "盘后";
    const pill = $("#mkt-state");
    pill.textContent = st;
    pill.classList.toggle("open", open);
    if (D) $("#updated").textContent = `数据更新于 ${ago(D.generated_at)}`;
  }

  // ------------------------------------------------------------------ 跑马灯
  function renderTape() {
    const items = [...D.indices, ...D.cross].map((q) => {
      const isYield = q.sym === "^TNX";
      const val = isYield ? q.last.toFixed(2) + "%" : num(q.last, q.last > 1000 ? 0 : 2);
      const chg = isYield ? `<span class="${cls(q.diff)}">${q.diff > 0 ? "+" : ""}${(q.diff * 100).toFixed(0)}bp</span>` : span(q.chg1);
      return `<div class="tape-item"><b>${esc(q.name)}</b><span class="v">${val}</span>${chg}</div>`;
    }).join("");
    $("#tape").innerHTML = items + items;
  }

  // ------------------------------------------------------------------ 热力图
  function squarify(nodes, rect) {
    const total = nodes.reduce((s, n) => s + n.value, 0);
    if (!total || rect.w <= 0 || rect.h <= 0) return [];
    const scale = (rect.w * rect.h) / total;
    const items = nodes.map((n) => ({ ...n, area: n.value * scale }));
    const out = [], r = { ...rect };
    let row = [];
    const worst = (row, side) => {
      const s = row.reduce((a, n) => a + n.area, 0), mx = Math.max(...row.map((n) => n.area)), mn = Math.min(...row.map((n) => n.area));
      return Math.max((side * side * mx) / (s * s), (s * s) / (side * side * mn));
    };
    const lay = (row) => {
      const s = row.reduce((a, n) => a + n.area, 0);
      if (r.w >= r.h) {
        const cw = s / r.h; let y = r.y;
        row.forEach((n) => { const hh = n.area / cw; out.push({ ...n, x: r.x, y, w: cw, h: hh }); y += hh; });
        r.x += cw; r.w -= cw;
      } else {
        const rh = s / r.w; let x = r.x;
        row.forEach((n) => { const ww = n.area / rh; out.push({ ...n, x, y: r.y, w: ww, h: rh }); x += ww; });
        r.y += rh; r.h -= rh;
      }
    };
    let i = 0;
    while (i < items.length) {
      const side = Math.min(r.w, r.h), n = items[i];
      if (!row.length || worst([...row, n], side) <= worst(row, side)) { row.push(n); i++; }
      else { lay(row); row = []; }
    }
    if (row.length) lay(row);
    return out;
  }

  function renderMap() {
    const box = $("#treemap"), W = box.clientWidth, H = box.clientHeight, p = state.mapP, lim = PERIOD_LIM[p];
    const secs = D.sectors.map((s) => {
      const kids = s.members.map((m) => ({ sym: m, a: D.stocks[m], value: D.stocks[m]?.cap || 5e10 })).filter((k) => k.a).sort((a, b) => b.value - a.value);
      return { s, kids, value: kids.reduce((t, k) => t + k.value, 0) };
    }).filter((x) => x.kids.length).sort((a, b) => b.value - a.value);
    let html = "";
    for (const sr of squarify(secs, { x: 0, y: 0, w: W, h: H })) {
      const head = sr.h > 40 && sr.w > 50 ? 17 : 0;
      html += `<div class="tm-sector" style="left:${sr.x}px;top:${sr.y}px;width:${sr.w}px;height:${sr.h}px">${head ? `<span>${esc(sr.s.name)} ${pct(sr.s[p] ?? null, 1)}</span>` : ""}</div>`;
      for (const c of squarify(sr.kids, { x: sr.x, y: sr.y + head, w: sr.w, h: sr.h - head })) {
        const v = c.a[p], area = c.w * c.h;
        const fs = Math.max(9, Math.min(26, Math.sqrt(area) / 4.2));
        const label = c.w > 34 && c.h > 22 ? `<b>${esc(c.sym)}</b>${c.h > 36 && c.w > 44 ? `<i>${pct(v, 1)}</i>` : ""}` : "";
        html += `<button class="tm-cell" data-sym="${esc(c.sym)}" style="left:${c.x}px;top:${c.y}px;width:${c.w}px;height:${c.h}px;background:${heat(v, lim)};--fs:${fs.toFixed(1)}px" aria-label="${esc(c.a.name)} ${esc(c.sym)} ${PERIOD_TXT[p]} ${pct(v)}">${label}</button>`;
      }
    }
    box.innerHTML = html;
    $("#map-legend").innerHTML = `<span>${pct(-lim, 0)}</span><span class="bar" style="background:linear-gradient(90deg,${heat(-lim, lim)},${heat(0, lim)},${heat(lim, lim)})"></span><span>${pct(lim, 0)}</span><span>（${PERIOD_TXT[p]}）</span>`;
  }

  // ------------------------------------------------------------------ 侧栏：速览、情绪、宽度
  function renderSide() {
    $("#brief").innerHTML = D.brief.map((b) => `<li>${esc(b)}</li>`).join("");
    const sc = D.sentiment.score, segs = ["#D62E52", "#F07A55", "#8A9BBA", "#6ED3A3", "#16A868"];
    let g = "";
    const cx = 110, cy = 112, R = 92;
    const pt = (deg, rr) => [cx + rr * Math.cos((deg * Math.PI) / 180), cy - rr * Math.sin((deg * Math.PI) / 180)];
    [[0, 25], [25, 45], [45, 55], [55, 75], [75, 100]].forEach(([a, b], i) => {
      const [x1, y1] = pt(180 - a * 1.8 - 0.8, R), [x2, y2] = pt(180 - b * 1.8 + 0.8, R);
      g += `<path d="M${x1} ${y1} A${R} ${R} 0 0 1 ${x2} ${y2}" stroke="${segs[i]}" stroke-width="14" fill="none"/>`;
    });
    const [nx, ny] = pt(180 - sc * 1.8, R - 30);
    g += `<line x1="${cx}" y1="${cy}" x2="${nx}" y2="${ny}" stroke="#E6EEF9" stroke-width="3" stroke-linecap="round"/><circle cx="${cx}" cy="${cy}" r="6" fill="#E6EEF9"/>`;
    g += `<text x="14" y="126" fill="${DIM}" font-size="10">恐惧</text><text x="186" y="126" fill="${DIM}" font-size="10">贪婪</text>`;
    $("#gauge").innerHTML = g;
    $("#senti-score").textContent = sc;
    $("#senti-label").textContent = D.sentiment.label + "（本站综合指标）";
    $("#senti-parts").innerHTML = Object.entries(D.sentiment.components).map(([k, v]) => `<li><span>${esc(k)}</span><span>${v}</span></li>`).join("");
    const b = D.breadth, tot = Math.max(b.adv + b.dec, 1);
    $("#ad-bar .adv").style.width = (b.adv / tot) * 100 + "%";
    $("#ad-bar .dec").style.width = (b.dec / tot) * 100 + "%";
    $("#ad-legend").innerHTML = `<span>上涨 <b class="up">${b.adv}</b></span><span>下跌 <b class="down">${b.dec}</b></span>
      <span>站上 200 日线 <b>${pct(b.above200, 0).replace("+", "")}</b></span><span>站上 50 日线 <b>${pct(b.above50, 0).replace("+", "")}</b></span>
      <span>52 周新高 <b>${b.new_hi}</b></span><span>股票池 <b>${b.total}</b></span>`;
  }

  // ------------------------------------------------------------------ 指数卡片
  function renderIndices() {
    $("#index-grid").innerHTML = [...D.indices, ...D.cross].map((q) => {
      const isYield = q.sym === "^TNX";
      const v = isYield ? q.last.toFixed(2) + "%" : num(q.last, q.last > 1000 ? 0 : 2);
      const c = isYield ? `<span class="${cls(q.diff)}">${q.diff > 0 ? "+" : ""}${(q.diff * 100).toFixed(0)} 基点</span>` : span(q.chg1);
      const color = q.sym === "^VIX" ? ((q.spark.at(-1) >= q.spark[0]) ? DOWN : UP) : undefined;
      return `<div class="idx"><div class="n">${esc(q.name)}</div><div class="v">${v}</div><div class="c">${c}</div>
        ${sparkSVG(q.spark, 200, 40, color)}
        <div class="sub"><span>周 ${pct(q.r5, 1)}</span><span>月 ${pct(q.r21, 1)}</span><span>年内 ${pct(q.ytd, 1)}</span></div></div>`;
    }).join("");
  }

  // ------------------------------------------------------------------ 行业条形图
  function renderSectors() {
    const p = state.secP;
    const rows = [...D.sectors].sort((a, b) => (b[p] ?? -9) - (a[p] ?? -9));
    const mx = Math.max(...rows.map((r) => Math.abs(r[p] || 0)), 0.001);
    $("#sector-bars").innerHTML = rows.map((r) => {
      const v = r[p] || 0, w = (Math.abs(v) / mx) * 50;
      const bar = v >= 0 ? `left:50%;width:${w}%;background:${UP}` : `right:50%;width:${w}%;background:${DOWN}`;
      return `<button class="sbar" data-etf="${r.etf}" aria-label="${esc(r.name)} ${PERIOD_TXT[p]} ${pct(v)}">
        <span class="nm">${esc(r.name)}<small>${r.etf}</small></span>
        <span class="track"><i style="${bar}"></i></span>
        <span class="pct ${cls(v)}">${pct(r[p])}</span>
        <span class="br">今日 ${r.adv}/${r.n} 只上涨</span></button>`;
    }).join("");
  }

  // ------------------------------------------------------------------ 机会雷达
  function oppCard(sym) {
    const a = D.stocks[sym];
    if (!a) return "";
    const lc = ACTION_COLOR[a.action] || DIM;
    return `<button class="opp" data-sym="${esc(sym)}" style="--lc:${lc}">
      <div class="top"><div><span class="sym">${esc(sym)}</span><span class="nm">${esc(a.name)}</span></div>
        <div><span class="px">${price(a.last)}</span> ${span(a.chg1)}</div></div>
      <div class="mid"><div><span class="tag l${a.level}">${a.status}</span> <span class="tag" style="color:${lc};border-color:${lc}66">${esc(a.action)}</span></div>
        ${sparkSVG(a.chart.slice(-60), 120, 30)}</div>
      ${a.level === 0 ? `<div class="lv"><div style="grid-column:1/-1">长期趋势转弱，收盘站回 200 日线 <b style="display:inline">${price(a.sma200)}</b> 之前不考虑买入</div></div>` :
      `<div class="lv"><div>买入参考<b>${price(a.ref)}</b></div><div class="s">止损<b>${price(a.stop)}</b></div><div class="t">目标<b>${price(a.target)}</b></div></div>`}
    </button>`;
  }

  function renderRadar() {
    const tabs = Object.entries(D.opportunities).map(([k, o]) => [k, o.title, o.items, o.desc]);
    tabs.push(["gainers", "今日涨幅榜", D.movers.gainers, "股票池中今日涨幅最大的股票"], ["losers", "今日跌幅榜", D.movers.losers, "股票池中今日跌幅最大的股票"]);
    $("#radar-tabs").innerHTML = tabs.map(([k, t, items]) =>
      `<button role="tab" data-k="${k}" aria-selected="${k === state.radar}">${esc(t)}<span>${items.length}</span></button>`).join("");
    const cur = tabs.find((t) => t[0] === state.radar) || tabs[0];
    $("#radar-desc").textContent = cur[3];
    $("#radar-list").innerHTML = cur[2].length ? cur[2].map(oppCard).join("") : `<div class="empty">目前没有股票符合这个条件。条件不满足时不出手，本身也是一种纪律。</div>`;
  }

  // ------------------------------------------------------------------ 新闻
  function renderNews() {
    const tags = {};
    D.news.forEach((n) => n.tags.forEach((t) => (tags[t] = (tags[t] || 0) + 1)));
    const tagList = Object.entries(tags).sort((a, b) => b[1] - a[1]).map((x) => x[0]);
    $("#news-tags").innerHTML = [`<button data-t="" aria-pressed="${!state.newsTag}">全部</button>`]
      .concat(tagList.map((t) => `<button data-t="${esc(t)}" aria-pressed="${state.newsTag === t}">${esc(t)}</button>`)).join("");
    let items = D.news.filter((n) => !state.newsTag || n.tags.includes(state.newsTag));
    const age = (n) => (n.time ? (Date.now() - new Date(n.time)) / 36e5 : 48);
    items = [...items].sort(state.newsSort === "time"
      ? (a, b) => (b.time || "").localeCompare(a.time || "")
      : (a, b) => b.score * Math.exp(-age(b) / 48) - a.score * Math.exp(-age(a) / 48));
    const official = new Set(["央行", "政策", "监管", "经济数据"]);
    const li = (n) => `<li class="${n.score >= 5 ? "hot" : ""}">
      <div class="meta"><span class="src">${esc(n.source)}</span><span>${ago(n.time)}</span>${n.score >= 5 ? '<span style="color:#FFC857">重要</span>' : ""}</div>
      <a class="t" href="${esc(n.link)}" target="_blank" rel="noopener noreferrer">${esc(n.title)}</a>
      ${n.summary ? `<p>${esc(n.summary)}</p>` : ""}
      <div class="tags">${n.tags.map((t) => `<span class="tag">${esc(t)}</span>`).join("")}${n.tickers.map((t) => `<button class="tk" data-sym="${esc(t)}">${esc(t)}</button>`).join("")}</div></li>`;
    const off = items.filter((n) => official.has(n.cat)).slice(0, 40), mkt = items.filter((n) => !official.has(n.cat)).slice(0, 40);
    const none = '<li class="muted">这个主题下暂时没有新闻。</li>';
    $("#news-official").innerHTML = off.map(li).join("") || none;
    $("#news-market").innerHTML = mkt.map(li).join("") || none;
  }

  // ------------------------------------------------------------------ 宏观
  function renderMacro() {
    $("#macro-grid").innerHTML = D.macro.map((m) => {
      const ch = m.prev != null ? m.value - m.prev : null;
      const unit = m.unit === "%" ? "%" : m.unit ? " " + m.unit : "";
      const chTxt = ch == null ? "" : `${ch > 0 ? "▲" : ch < 0 ? "▼" : "■"} ${Math.abs(ch).toFixed(2)}`;
      return `<div class="mac"><div class="n">${esc(m.label)}</div><div class="v">${num(m.value, m.unit === "千人" ? 0 : 2)}<small style="font-size:14px;color:${DIM}">${esc(unit)}</small></div>
        <div class="d"><span>${chTxt} 较上期</span><span>${m.date}</span></div>${sparkSVG(m.spark, 200, 34, ICE)}</div>`;
    }).join("") || `<div class="mac">宏观数据暂时没有获取到，下次更新会自动重试。</div>`;
  }

  // ------------------------------------------------------------------ 财报
  function renderEarnings() {
    const by = {};
    D.earnings.forEach((e) => (by[e.date] = by[e.date] || []).push(e.sym));
    const wd = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];
    $("#earn-list").innerHTML = Object.entries(by).map(([d, syms]) => {
      const dt = new Date(d + "T12:00:00");
      return `<div class="eday"><h3>${dt.getMonth() + 1} 月 ${dt.getDate()} 日<small>${wd[dt.getDay()]}</small></h3>
        ${syms.map((s) => `<button class="row" data-sym="${esc(s)}"><span><b>${esc(s)}</b> <span class="muted">${esc(D.stocks[s]?.name || "")}</span></span><span class="muted small">${cap(D.stocks[s]?.cap)}</span></button>`).join("")}</div>`;
    }).join("") || `<div class="empty">未来三周股票池里没有已公布日期的财报。</div>`;
  }

  // ------------------------------------------------------------------ 选股器
  function renderTable() {
    const q = $("#q").value.trim().toLowerCase(), fs = $("#f-sector").value, fa = $("#f-action").value;
    let rows = Object.entries(D.stocks).filter(([s, a]) =>
      (!q || s.toLowerCase().includes(q) || a.name.toLowerCase().includes(q) || a.en.toLowerCase().includes(q)) &&
      (!fs || a.sector === fs) && (!fa || a.action === fa));
    const k = state.sortK, dir = state.sortDir;
    rows.sort((x, y) => {
      const a = k === "sym" ? x[0] : x[1][k], b = k === "sym" ? y[0] : y[1][k];
      if (a == null) return 1;
      if (b == null) return -1;
      return (typeof a === "string" ? a.localeCompare(b) : a - b) * dir;
    });
    $("#table tbody").innerHTML = rows.map(([s, a]) => `<tr data-sym="${esc(s)}" tabindex="0">
      <td><span class="sym">${esc(s)}</span><span class="nm">${esc(a.name)}</span></td>
      <td class="num">${price(a.last)}</td><td class="num">${span(a.chg1)}</td><td class="num">${span(a.r5, 1)}</td>
      <td class="num">${span(a.r21, 1)}</td><td class="num">${span(a.ytd, 1)}</td><td class="num">${a.rsi ?? "—"}</td>
      <td><span class="tag l${a.level}">${a.status}</span></td>
      <td><span style="color:${ACTION_COLOR[a.action] || DIM}">${esc(a.action)}</span></td>
      ${a.level === 0 ? `<td class="num muted" colspan="3">站回 ${price(a.sma200)} 再考虑</td>` :
      `<td class="num">${price(a.ref)}</td><td class="num down">${price(a.stop)}</td><td class="num up">${price(a.target)}</td>`}</tr>`).join("");
    $$("#table th").forEach((th) => th.setAttribute("aria-sort", th.dataset.k === k ? (dir > 0 ? "ascending" : "descending") : "none"));
    $("#table-count").textContent = `共 ${rows.length} 只股票。点击表头排序，点击行查看详情。`;
  }

  function initFilters() {
    $("#f-sector").innerHTML = `<option value="">全部行业</option>` + D.sectors.map((s) => `<option value="${s.etf}">${esc(s.name)}</option>`).join("");
    const acts = [...new Set(Object.values(D.stocks).map((a) => a.action))];
    $("#f-action").innerHTML = `<option value="">全部信号</option>` + acts.map((a) => `<option>${esc(a)}</option>`).join("");
  }

  // ------------------------------------------------------------------ 详情弹窗
  let lastFocus = null;
  function openStock(sym) {
    const a = D.stocks[sym];
    if (!a) return;
    lastFocus = document.activeElement;
    const W = 800, H = 240, pad = 6, ch = a.chart.filter((x) => x != null);
    const lines = [["买入参考", a.ref, ICE], ["止损", a.stop, DOWN], ["目标", a.target, UP], ["50日线", a.sma50, DIM], ["200日线", a.sma200, DIM]].filter((l) => l[1] != null);
    const all = ch.concat(lines.map((l) => l[1]));
    const lo = Math.min(...all), hi = Math.max(...all), r = hi - lo || 1;
    const y = (v) => pad + (1 - (v - lo) / r) * (H - pad * 2);
    const PR = 110;
    const x = (i) => (i / (ch.length - 1)) * (W - PR);
    const path = ch.map((v, i) => (i ? "L" : "M") + x(i).toFixed(1) + " " + y(v).toFixed(1)).join("");
    let svg = `<defs><linearGradient id="mg" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="${ICE}" stop-opacity=".22"/><stop offset="1" stop-color="${ICE}" stop-opacity="0"/></linearGradient></defs>`;
    svg += `<path d="${path}L${x(ch.length - 1)} ${H}L0 ${H}Z" fill="url(#mg)"/>`;
    const labs = lines.map(([n, v, c]) => ({ n, v, c, ly: y(v) })).sort((p, q) => p.ly - q.ly);
    for (let i = 1; i < labs.length; i++) labs[i].ly = Math.max(labs[i].ly, labs[i - 1].ly + 14);
    const over = labs.length ? Math.max(0, labs[labs.length - 1].ly - (H - 6)) : 0;
    labs.forEach((l) => (l.ly -= over));
    for (let i = labs.length - 2; i >= 0; i--) labs[i].ly = Math.min(labs[i].ly, labs[i + 1].ly - 14);
    labs.forEach(({ n, v, c, ly }) => {
      svg += `<line x1="0" x2="${W - PR}" y1="${y(v)}" y2="${y(v)}" stroke="${c}" stroke-dasharray="4 4" stroke-opacity=".8"/>
        <text x="${W - PR + 6}" y="${ly + 4}" fill="${c}" font-size="11">${n} ${num(v)}</text>`;
    });
    svg += `<path class="ln" d="${path}"/>`;
    const related = D.news.filter((n) => n.tickers.includes(sym)).slice(0, 6);
    const p3 = a.p3 != null ? `历史上和现在处境相似时，3 天后上涨的比例是 <b>${Math.round(a.p3 * 100)}%</b>（样本 ${a.n3} 次，平均 ${pct(a.a3, 1)}）${a.n3 < 20 ? "，样本较少，参考性低" : ""}。` : "";
    $("#m-body").innerHTML = `
      <div class="m-head"><h2 id="m-title">${esc(sym)}</h2><span class="muted">${esc(a.name)}｜${esc(D.sectors.find((s) => s.etf === a.sector)?.name || "")}</span>
        <span class="px">${price(a.last)}</span><span class="c">${span(a.chg1)}</span></div>
      <svg class="m-chart" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="${esc(sym)} 近半年走势">${svg}</svg>
      <div class="muted small">近半年收盘价走势（起点 ${a.chart_start}）</div>
      <div class="m-grid">
        <div>一周<b class="${cls(a.r5)}">${pct(a.r5, 1)}</b></div><div>一个月<b class="${cls(a.r21)}">${pct(a.r21, 1)}</b></div>
        <div>三个月<b class="${cls(a.r63)}">${pct(a.r63, 1)}</b></div><div>今年以来<b class="${cls(a.ytd)}">${pct(a.ytd, 1)}</b></div>
        <div>RSI（14）<b>${a.rsi ?? "—"}</b></div><div>距 52 周高点<b>${pct(a.off_hi, 1)}</b></div>
        <div>成交量 / 20 日均量<b>${a.volratio != null ? a.volratio.toFixed(2) + " 倍" : "—"}</b></div><div>市值<b>${cap(a.cap)}</b></div>
      </div>
      <div class="m-plan"><h3>交易计划参考</h3>
        趋势状态：<span class="tag l${a.level}">${a.status}</span>　短线信号：<b style="color:${ACTION_COLOR[a.action] || DIM}">${esc(a.action)}</b><br>
        ${a.level === 0 ? `价格在 200 日均线（${price(a.sma200)}）下方，长期趋势转弱。收盘重新站上这个价格之前，规则不建议买入。` :
        `买入：${esc(a.how)}，参考价 <b>${price(a.ref)}</b>；突破买入价 ${price(a.breakout)}<br>止损：<b class="down">${price(a.stop)}</b>（收盘跌破就离场）　目标：<b class="up">${price(a.target)}</b>（盈亏比 2:1）`}<br>
        常见波动范围：3 天 ${price(a.range3[0])}–${price(a.range3[1])}，1 个月 ${price(a.range21[0])}–${price(a.range21[1])}。这是按近期波动统计的范围，不是涨跌预测。<br>
        ${p3}${a.earn ? `<br>下次财报：<b>${a.earn}</b>，财报前后波动通常明显加大。` : ""}
      </div>
      ${related.length ? `<div class="m-news"><h3>相关新闻</h3>${related.map((n) => `<a href="${esc(n.link)}" target="_blank" rel="noopener noreferrer"><span class="muted small">${esc(n.source)}｜${ago(n.time)}</span><br>${esc(n.title)}</a>`).join("")}</div>` : ""}`;
    $("#modal").hidden = false;
    document.body.style.overflow = "hidden";
    $("#m-close").focus();
  }
  function closeModal() {
    $("#modal").hidden = true;
    document.body.style.overflow = "";
    lastFocus?.focus?.();
  }

  // ------------------------------------------------------------------ 交互
  function bind() {
    document.addEventListener("click", (e) => {
      const symEl = e.target.closest("[data-sym]");
      if (symEl) { openStock(symEl.dataset.sym); return; }
      const mp = e.target.closest("#map-period button");
      if (mp) { state.mapP = mp.dataset.p; $$("#map-period button").forEach((b) => b.setAttribute("aria-pressed", b === mp)); renderMap(); }
      const sp = e.target.closest("#sector-period button");
      if (sp) { state.secP = sp.dataset.p; $$("#sector-period button").forEach((b) => b.setAttribute("aria-pressed", b === sp)); renderSectors(); }
      const sb = e.target.closest(".sbar");
      if (sb) { $("#f-sector").value = sb.dataset.etf; renderTable(); $("#screener").scrollIntoView(); }
      const rt = e.target.closest("#radar-tabs button");
      if (rt) { state.radar = rt.dataset.k; renderRadar(); }
      const ns = e.target.closest("#news-sort button");
      if (ns) { state.newsSort = ns.dataset.s; $$("#news-sort button").forEach((b) => b.setAttribute("aria-pressed", b === ns)); renderNews(); }
      const nt = e.target.closest("#news-tags button");
      if (nt) { state.newsTag = nt.dataset.t; renderNews(); }
      const th = e.target.closest("#table th");
      if (th) {
        const k = th.dataset.k;
        state.sortDir = state.sortK === k ? -state.sortDir : (k === "sym" ? 1 : -1);
        state.sortK = k; renderTable();
      }
      if (e.target.id === "modal" || e.target.closest("#m-close")) closeModal();
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && !$("#modal").hidden) closeModal();
      if (e.key === "Enter" && e.target.matches("tbody tr")) openStock(e.target.dataset.sym);
    });
    ["#q", "#f-sector", "#f-action"].forEach((s) => $(s).addEventListener("input", renderTable));

    const tip = $("#tip");
    $("#treemap").addEventListener("mousemove", (e) => {
      const c = e.target.closest(".tm-cell");
      if (!c) { tip.hidden = true; return; }
      const a = D.stocks[c.dataset.sym];
      tip.innerHTML = `<b>${esc(c.dataset.sym)}</b> ${esc(a.name)}<br>${price(a.last)}　今日 ${span(a.chg1)}<br>
        一周 ${span(a.r5, 1)}　一个月 ${span(a.r21, 1)}<br><span class="tag l${a.level}">${a.status}</span> <span style="color:${ACTION_COLOR[a.action]}">${esc(a.action)}</span>`;
      tip.hidden = false;
      const x = Math.min(e.clientX + 14, innerWidth - tip.offsetWidth - 8), y = Math.min(e.clientY + 14, innerHeight - tip.offsetHeight - 8);
      tip.style.left = x + "px"; tip.style.top = y + "px";
    });
    $("#treemap").addEventListener("mouseleave", () => (tip.hidden = true));
    let t;
    new ResizeObserver(() => { clearTimeout(t); t = setTimeout(() => D && renderMap(), 120); }).observe($("#treemap"));
  }

  function renderAll() {
    renderTape(); renderMap(); renderSide(); renderIndices(); renderSectors();
    renderRadar(); renderNews(); renderMacro(); renderEarnings(); renderTable();
    tick();
  }

  async function load(first) {
    try {
      const r = await fetch("data/market.json?t=" + Date.now(), { cache: "no-store" });
      if (!r.ok) throw new Error("HTTP " + r.status);
      D = await r.json();
      if (first) initFilters();
      renderAll();
    } catch (err) {
      if (first) {
        $("#main").insertAdjacentHTML("afterbegin", `<div class="error"><b>数据加载失败。</b>
          如果你是直接双击打开的本地文件，浏览器会阻止读取数据，请部署到 GitHub Pages 后访问网址；
          如果网站刚建好，请等 GitHub Actions 第一次运行完成（约 5 分钟）后刷新。（${esc(err.message)}）</div>`);
      }
    }
  }

  bind();
  tick();
  setInterval(tick, 1000);
  load(true);
  setInterval(() => load(false), 5 * 60 * 1000);
})();
