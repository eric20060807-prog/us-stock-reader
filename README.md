# 美股雷达

一个自动更新的美股行情网站，部署在 GitHub Pages 上，完全免费。

**网站内容：**
- **美股全景热力图**：11 个行业、约 120 只大盘股，方块大小代表市值，颜色代表涨跌，可以切换今日、一周、一个月、今年以来。
- **今日速览**：根据当天数据自动生成的市场要点。
- **市场情绪**与**市场宽度**：综合 VIX、均线和涨跌家数计算。
- **主要指数与资产**：标普、纳指、道指、罗素、VIX、美债、美元、黄金、原油、比特币。
- **行业表现**：可以看今日、一周、一个月、三个月、今年以来。
- **机会雷达**：趋势强势、短线买点、放量异动、52 周新高、超卖观察、风险警示，以及涨跌幅榜。
- **政策与新闻**：美联储、白宫、SEC、劳工统计局、经济分析局的官方动态，加上 CNBC、MarketWatch、Yahoo 的市场新闻。按重要性排序，可以按主题筛选。
- **宏观数据**：利率、CPI、PCE、就业、GDP、消费者信心、房贷利率。
- **未来三周财报日历**。
- **选股器**：全部股票可以搜索、筛选、排序。点击任意股票，会弹出走势图、买入参考价、止损价、目标价和相关新闻。

数据由 GitHub Actions 自动更新：美股交易时段每 30 分钟一次，另外每天早晚各一次。

---

## 第一次上线（约 10 分钟，不需要写代码）

### 1. 新建仓库
1. 登录 https://github.com ，点右上角 **+** → **New repository**。
2. **Repository name** 填 `us-stock-radar`（也可以取别的英文名）。
3. 选 **Public**。免费账号只有公开仓库才能用 GitHub Pages。
4. 点 **Create repository**。

### 2. 上传文件
1. 在新仓库页面，点蓝色小字 **uploading an existing file**。
2. 在 Mac 上打开 `market-site` 文件夹，**按 `Command + Shift + .`（句号）显示隐藏文件**，这时会多出一个 `.github` 文件夹。它负责自动更新数据，一定要一起上传。
3. 按 `Command + A` 全选文件夹里的所有内容，然后拖到网页的上传区域。
4. 等文件列表出现后，点页面底部绿色的 **Commit changes**。
5. 回到仓库首页，检查能看到 `.github`、`assets`、`scripts`、`index.html`、`README.md`。

> 如果没看到 `.github`：点 **Add file → Create new file**，文件名输入 `.github/workflows/update.yml`，打开电脑上的同名文件，把内容全部复制粘贴进去，再点 **Commit changes**。

### 3. 打开网站功能（GitHub Pages）
1. 仓库顶部点 **Settings**，左侧点 **Pages**。
2. **Source** 选 **Deploy from a branch**，**Branch** 选 `main`，文件夹选 `/ (root)`，点 **Save**。

### 4. 第一次抓取数据
1. 仓库顶部点 **Actions**。如果提示启用，点绿色按钮同意。
2. 左侧点 **更新行情数据**，右侧点 **Run workflow → Run workflow**。
3. 等 3–6 分钟，出现绿色对勾就完成了。

### 5. 打开网站
网址是：`https://你的GitHub用户名.github.io/us-stock-radar/`

第一次可能要再等 1–2 分钟才能打开。以后数据会自动更新，不用再管。

---

## 常见问题

- **Actions 出现红叉**：点进去看报错，截图发给 Claude。如果报错里有 `Permission denied` 或 `403`，到 **Settings → Actions → General → Workflow permissions**，选 **Read and write permissions** 并保存，然后重新运行。
- **网页显示“数据加载失败”**：说明第一次数据还没生成，等 Actions 跑完再刷新。
- **想增减股票**：编辑 `scripts/universe.py`，按同样的格式加一行，例如 `"AAOI": ("应用光电", "Applied Optoelectronics"),`。保存后，下次自动更新就会生效。
- **某个新闻源没有内容**：个别网站偶尔会拦截自动抓取，其余新闻源不受影响。
- **数据延迟**：行情来自 Yahoo Finance，通常有约 15 分钟延迟，加上每 30 分钟才更新一次，所以不适合秒级盯盘。

## 免责声明

网站上的所有信号、价位和名单，都由固定的技术规则自动计算，不构成投资建议，不保证盈利。
