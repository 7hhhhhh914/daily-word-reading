"""读取 .env 配置与项目路径。"""
import os

from dotenv import load_dotenv

load_dotenv()

# ---- 路径 ----
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 项目根
APP_DIR = os.path.join(BASE_DIR, "app")
STATIC_DIR = os.path.join(APP_DIR, "static")
DATA_DIR = os.path.join(APP_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "words.db")

# ---- 大模型（OpenAI 兼容接口，国内大模型通用）----
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
MODEL_OCR = os.getenv("MODEL_OCR", "qwen3-vl-plus")       # 视觉模型，识别截图
MODEL_ARTICLE = os.getenv("MODEL_ARTICLE", "qwen-plus")   # 文本模型，写文章

GNEWS_API_KEY = os.getenv("GNEWS_API_KEY", "")
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")

HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))

# 梯子代理（自动检测）：优先读 .env 的 PROXY，否则自动读系统代理（macOS）。
# 梯子开着就自动走代理抓海外新闻，关了就自动直连，无需手动改端口。
def _detect_proxy() -> str:
    env = os.getenv("PROXY", "")
    if env:
        return env
    try:
        import subprocess
        out = subprocess.run(["scutil", "--proxy"], capture_output=True, text=True, timeout=3).stdout
        host = port = None
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("HTTPSProxy :"):
                host = line.split(":", 1)[1].strip()
            elif line.startswith("HTTPSPort :"):
                port = line.split(":", 1)[1].strip()
        if host and port:
            return f"http://{host}:{port}"
    except Exception:
        pass
    return ""


PROXY = _detect_proxy()

# ---- RSS 新闻源（category 用于按主题筛选；allkpop 被 Cloudflare 拦截、BBC/Guardian 国内被墙，暂不收录）----
RSS_SOURCES = [
    {"name": "Soompi", "url": "https://www.soompi.com/feed/", "category": "kpop"},
    {"name": "Koreaboo", "url": "https://www.koreaboo.com/feed/", "category": "kpop"},
    {"name": "Variety", "url": "https://variety.com/feed/", "category": "entertainment"},
    {"name": "Hollywood Reporter", "url": "https://www.hollywoodreporter.com/feed/", "category": "entertainment"},
    {"name": "Billboard", "url": "https://www.billboard.com/feed/", "category": "music"},
    {"name": "NPR", "url": "https://feeds.npr.org/1001/rss.xml", "category": "general"},
    {"name": "France24", "url": "https://www.france24.com/en/rss", "category": "general"},
    {"name": "BBC", "url": "https://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml", "category": "general"},
    {"name": "The Guardian", "url": "https://www.theguardian.com/culture/rss", "category": "general"},
]

# 单个源抓取超时（秒）
RSS_TIMEOUT = 15
# 每个源最多取的文章数
RSS_MAX_ENTRIES = 30
