"""股票池：按行业分组。每只股票：代码 -> (中文名, 英文名，用于新闻匹配)。可自行增减。"""

SECTORS = {
    "XLK": ("信息技术", {
        "AAPL": ("苹果", "Apple"), "MSFT": ("微软", "Microsoft"), "NVDA": ("英伟达", "Nvidia"),
        "AVGO": ("博通", "Broadcom"), "ORCL": ("甲骨文", "Oracle"), "CRM": ("Salesforce", "Salesforce"),
        "AMD": ("AMD", "AMD"), "ADBE": ("Adobe", "Adobe"), "CSCO": ("思科", "Cisco"),
        "QCOM": ("高通", "Qualcomm"), "TXN": ("德州仪器", "Texas Instruments"), "AMAT": ("应用材料", "Applied Materials"),
        "MU": ("美光", "Micron"), "LRCX": ("泛林", "Lam Research"), "KLAC": ("科磊", "KLA"),
        "INTC": ("英特尔", "Intel"), "IBM": ("IBM", "IBM"), "NOW": ("ServiceNow", "ServiceNow"),
        "PLTR": ("Palantir", "Palantir"), "ANET": ("Arista", "Arista"), "MRVL": ("迈威尔", "Marvell"),
        "ADI": ("亚德诺", "Analog Devices"), "DELL": ("戴尔", "Dell"), "GLW": ("康宁", "Corning"),
        "SNDK": ("闪迪", "Sandisk"), "WDC": ("西部数据", "Western Digital"),
        "AAOI": ("应用光电", "Applied Optoelectronics"), "AXTI": ("AXT", "AXT Inc"),
    }),
    "XLC": ("通信服务", {
        "GOOGL": ("谷歌", "Alphabet"), "META": ("Meta", "Meta"), "NFLX": ("奈飞", "Netflix"),
        "DIS": ("迪士尼", "Disney"), "TMUS": ("T-Mobile", "T-Mobile"), "VZ": ("威瑞森", "Verizon"),
        "T": ("AT&T", "AT&T"), "CMCSA": ("康卡斯特", "Comcast"),
    }),
    "XLY": ("可选消费", {
        "AMZN": ("亚马逊", "Amazon"), "TSLA": ("特斯拉", "Tesla"), "HD": ("家得宝", "Home Depot"),
        "MCD": ("麦当劳", "McDonald's"), "BKNG": ("Booking", "Booking"), "LOW": ("劳氏", "Lowe's"),
        "TJX": ("TJX", "TJX"), "SBUX": ("星巴克", "Starbucks"), "NKE": ("耐克", "Nike"),
        "CMG": ("Chipotle", "Chipotle"),
    }),
    "XLP": ("必需消费", {
        "WMT": ("沃尔玛", "Walmart"), "COST": ("好市多", "Costco"), "PG": ("宝洁", "Procter"),
        "KO": ("可口可乐", "Coca-Cola"), "PEP": ("百事", "PepsiCo"), "PM": ("菲莫国际", "Philip Morris"),
        "MO": ("奥驰亚", "Altria"), "MDLZ": ("亿滋", "Mondelez"), "CL": ("高露洁", "Colgate"),
    }),
    "XLF": ("金融", {
        "BRK-B": ("伯克希尔", "Berkshire"), "JPM": ("摩根大通", "JPMorgan"), "V": ("Visa", "Visa"),
        "MA": ("万事达", "Mastercard"), "BAC": ("美国银行", "Bank of America"), "WFC": ("富国银行", "Wells Fargo"),
        "GS": ("高盛", "Goldman"), "MS": ("摩根士丹利", "Morgan Stanley"), "AXP": ("美国运通", "American Express"),
        "BLK": ("贝莱德", "BlackRock"), "SCHW": ("嘉信理财", "Schwab"), "C": ("花旗", "Citigroup"),
    }),
    "XLV": ("医疗保健", {
        "LLY": ("礼来", "Eli Lilly"), "UNH": ("联合健康", "UnitedHealth"), "JNJ": ("强生", "Johnson & Johnson"),
        "ABBV": ("艾伯维", "AbbVie"), "MRK": ("默沙东", "Merck"), "TMO": ("赛默飞", "Thermo Fisher"),
        "ABT": ("雅培", "Abbott"), "ISRG": ("直觉外科", "Intuitive Surgical"), "AMGN": ("安进", "Amgen"),
        "PFE": ("辉瑞", "Pfizer"), "VRTX": ("福泰制药", "Vertex"), "GILD": ("吉利德", "Gilead"),
    }),
    "XLI": ("工业", {
        "GE": ("GE航空", "GE Aerospace"), "CAT": ("卡特彼勒", "Caterpillar"), "RTX": ("雷神", "RTX"),
        "HON": ("霍尼韦尔", "Honeywell"), "UNP": ("联合太平洋", "Union Pacific"), "BA": ("波音", "Boeing"),
        "DE": ("迪尔", "Deere"), "LMT": ("洛克希德", "Lockheed"), "ETN": ("伊顿", "Eaton"),
        "UBER": ("优步", "Uber"), "NOC": ("诺格", "Northrop"), "GEV": ("GE Vernova", "GE Vernova"),
    }),
    "XLE": ("能源", {
        "XOM": ("埃克森美孚", "Exxon"), "CVX": ("雪佛龙", "Chevron"), "COP": ("康菲", "ConocoPhillips"),
        "EOG": ("EOG", "EOG"), "SLB": ("斯伦贝谢", "Schlumberger"), "PSX": ("Phillips 66", "Phillips 66"),
        "MPC": ("马拉松原油", "Marathon Petroleum"), "OXY": ("西方石油", "Occidental"),
    }),
    "XLU": ("公用事业", {
        "NEE": ("新纪元能源", "NextEra"), "SO": ("南方电力", "Southern Company"), "DUK": ("杜克能源", "Duke Energy"),
        "CEG": ("Constellation", "Constellation"), "VST": ("Vistra", "Vistra"), "AEP": ("美国电力", "American Electric"),
        "BE": ("Bloom Energy", "Bloom Energy"),
    }),
    "XLRE": ("房地产", {
        "PLD": ("安博", "Prologis"), "AMT": ("美国铁塔", "American Tower"), "EQIX": ("Equinix", "Equinix"),
        "WELL": ("Welltower", "Welltower"), "SPG": ("西蒙地产", "Simon Property"), "O": ("Realty Income", "Realty Income"),
        "PSA": ("公共存储", "Public Storage"),
    }),
    "XLB": ("原材料", {
        "LIN": ("林德", "Linde"), "SHW": ("宣伟", "Sherwin-Williams"), "APD": ("空气化工", "Air Products"),
        "FCX": ("自由港", "Freeport"), "NEM": ("纽蒙特", "Newmont"), "ECL": ("艺康", "Ecolab"),
    }),
}

# 指数与跨资产行情（ticker tape / 指数卡片）
INDICES = {
    "^GSPC": "标普500", "^IXIC": "纳斯达克", "^DJI": "道琼斯", "^RUT": "罗素2000", "^VIX": "VIX 恐慌指数",
}
CROSS_ASSET = {
    "^TNX": "10年美债收益率", "DX-Y.NYB": "美元指数", "GC=F": "黄金", "CL=F": "原油 WTI", "BTC-USD": "比特币",
}

# 宏观数据（FRED，免 API key 的 CSV 接口）
# kind: level = 直接显示；yoy = 计算同比；diff = 计算环比变化（千人）
FRED = [
    ("DFEDTARU", "联邦基金利率上限", "%", "level"),
    ("DGS10", "10年期国债收益率", "%", "level"),
    ("DGS2", "2年期国债收益率", "%", "level"),
    ("T10Y2Y", "10年-2年利差", "%", "level"),
    ("CPIAUCSL", "CPI 同比", "%", "yoy"),
    ("CPILFESL", "核心 CPI 同比", "%", "yoy"),
    ("PCEPILFE", "核心 PCE 同比", "%", "yoy"),
    ("UNRATE", "失业率", "%", "level"),
    ("PAYEMS", "非农新增就业", "千人", "diff"),
    ("A191RL1Q225SBEA", "GDP 环比年化", "%", "level"),
    ("UMCSENT", "密歇根消费者信心", "", "level"),
    ("MORTGAGE30US", "30年房贷利率", "%", "level"),
]

# 新闻 / 政策 RSS 源：(名称, 网址, 类别)
FEEDS = [
    ("美联储", "https://www.federalreserve.gov/feeds/press_all.xml", "央行"),
    ("美联储讲话", "https://www.federalreserve.gov/feeds/speeches.xml", "央行"),
    ("白宫", "https://www.whitehouse.gov/presidential-actions/feed/", "政策"),
    ("美国证监会", "https://www.sec.gov/news/pressreleases.rss", "监管"),
    ("劳工统计局", "https://www.bls.gov/feed/bls_latest.rss", "经济数据"),
    ("经济分析局", "https://apps.bea.gov/rss/rss.xml", "经济数据"),
    ("CNBC", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114", "市场"),
    ("CNBC 经济", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258", "宏观"),
    ("CNBC 财报", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=15839135", "公司"),
    ("MarketWatch", "https://feeds.content.dowjones.io/public/rss/mw_topstories", "市场"),
    ("MarketWatch 快讯", "https://feeds.content.dowjones.io/public/rss/mw_marketpulse", "市场"),
    ("Yahoo 财经", "https://finance.yahoo.com/news/rssindex", "市场"),
]
