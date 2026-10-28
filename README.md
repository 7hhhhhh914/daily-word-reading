# 每日单词阅读

在真实语境里掌握每天背的新词：上传「不背单词」截图 → 识别单词 → 选要求 → 生成感兴趣话题的英文文章。

## 功能

四步向导（带步骤指示、可返回上一步、顶部有首页按钮）：
1. **上传截图**：点击/拖拽/相册多选，自动压缩到长边 1280px，缩略图 + 开始识别
2. **确认单词**：每词一张卡片（单词 + 音标 + 各词性释义分行），可编辑、删除、加词性、手动新增；自动补全的字段有淡色提示
3. **文章要求**：时长（150词/分）、难度（四级/六级/考研/雅思/托福）、主题（预设 + 自由输入）
4. **阅读文章**：新词高亮，点词弹层（音标/发音/中英释义/例句/搭配词根近反义）+ 认识/不认识；**全文翻译开关**（段落对照）；文末「返回首页/查看错题本」

另有：**单词语境查询**（手动输入单词查真实新闻里的用法，含词形变化，按命中数排序）、**错题本**（完整释义 + 搜索 + 详情展开 + 标记/删除）。

## 快速开始

```bash
cd daily-word-reading
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt        # 国内可加 -i https://pypi.tuna.tsinghua.edu.cn/simple
cp .env.example .env                   # 填 LLM_API_KEY
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- 本机：http://127.0.0.1:8000
- 手机（同 WiFi）：http://<Mac局域网IP>:8000（`ipconfig getifaddr en0` 查 IP）
- 手机（跨网络，任意 WiFi/流量）：用 Cloudflare 隧道 `cloudflared tunnel --url http://localhost:8000`，拿到 `trycloudflare.com` 网址即可

## 需要配置的 Key

`.env` 里，只需一个：

| 配置 | 说明 |
|---|---|
| `LLM_API_KEY` | 大模型 API Key（默认阿里云百炼，见 `.env.example` 注释） |
| `LLM_BASE_URL` | OpenAI 兼容接口地址（默认百炼） |
| `MODEL_OCR` | 视觉模型（读图），默认 `qwen3-vl-plus` |
| `MODEL_ARTICLE` | 文本模型（整理+写文章+查词），默认 `qwen-plus` |

> 阿里云百炼需在控制台「模型广场」开通对应模型并充值少量余额，费用极低。

## 已知限制

- **新闻匹配只查「标题 + 摘要」**：RSS 不提供全文，所以通用词（如 apple、improve）在娱乐/新闻摘要里命中较少，而娱乐词（release、fans、debut）命中较好。要提升通用词覆盖，需接 GNews/NewsAPI 或抓取文章全文（见 TODO.md）。
- 部分英文源被墙（BBC、The Guardian、allkpop），目前用 Soompi、Koreaboo、Variety、THR、Billboard、NPR、France24 共 7 个源，小时级缓存。
- 词形匹配为规则 + 常见不规则词表，偶有漏配。

## 技术栈

FastAPI + SQLite + 原生 HTML/CSS/JS（无重框架）。识别用「视觉模型读图 + 文本模型补全」，文章用「真实新闻素材 + 主题优先生成 + 逐段翻译」，新闻用「7 源 RSS + 小时级缓存」。
