"""功能二：生成文章 —— 用今日单词 + 感兴趣话题，基于真实新闻写阅读文章。"""
import datetime
import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import config, db
from ..services import generator, llm_client, rss_fetcher

router = APIRouter()

TARGETS = {"四级", "六级", "考研", "雅思", "托福"}


class GenerateRequest(BaseModel):
    topic: str = "K-pop"
    duration_min: int = 5
    target: str = "四级"
    words: list[str] = []      # 可选；为空则用今日已录入的单词


def _short_date(published: str) -> str:
    """从 RSS 的 published 字段抽出「21 Oct 2026」这样的短日期。"""
    m = re.search(r"(\d{1,2} [A-Za-z]{3} \d{4})", published or "")
    return m.group(1) if m else ""


_MONTHS = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
           "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}


def _parse_date(published: str):
    """把 published 解析成 (年, 月, 日)，失败返回 None。"""
    m = re.search(r"(\d{1,2}) ([A-Za-z]{3}) (\d{4})", published or "")
    if not m:
        return None
    mon = _MONTHS.get(m.group(2))
    if not mon:
        return None
    return (int(m.group(3)), mon, int(m.group(1)))


async def fetch_facts(topic: str, limit: int = 6) -> list[dict]:
    """抓新闻，按「相关度 + 新鲜度」排序，返回事实列表。

    排序：相关度从高到低；同等相关度时日期新的靠前；无日期的排最后。
    """
    entries, _ = await rss_fetcher.fetch_all_cached()
    # 附加 Google News 关键词搜索（海外媒体，主题相关，需代理；失败不影响）
    try:
        gnews = await rss_fetcher.search_google_news(topic)
        if gnews:
            entries = list(entries) + gnews
    except Exception:
        pass

    terms = [t for t in topic.lower().split() if t]
    facts: list[dict] = []
    for e in entries:
        text = f"{e['title']} {e['summary']}".lower()
        # Google News 结果视为已相关（关键词搜索本身已匹配主题）
        is_gnews = e.get("source") == "Google News"
        rel = 1 if is_gnews else (sum(1 for t in terms if t in text) if terms else 0)
        if terms and rel == 0:
            continue
        facts.append({
            "source": e["source"], "title": e["title"], "link": e["link"],
            "summary": (e["summary"] or "")[:300],
            "published": e.get("published", ""),
            "date": _parse_date(e.get("published", "")),
            "rel": rel,
        })

    def _key(f):
        d = f["date"] or (0, 0, 0)
        return (-f["rel"], -(d[0] * 10000 + d[1] * 100 + d[2]))

    facts.sort(key=_key)
    return facts[:limit]


def build_facts_string(facts: list[dict]) -> str:
    if not facts:
        return "（未抓到相关新闻，请明确告诉用户「没找到相关报道」，绝不编造。）"
    lines = [f"- [{f['source']} · {_short_date(f['published'])}] {f['title']}: {f['summary']}" for f in facts]
    return "\n".join(lines)


async def generate_article_core(topic: str, duration: int, target: str, word_list: list[str], target_meanings: dict) -> dict:
    """生成文章并保存，返回响应 dict。word_list / target_meanings 由调用方准备好。"""
    fact_list = await fetch_facts(topic)
    facts = build_facts_string(fact_list)
    word_count = duration * 150
    user_prompt = generator.build_user_prompt(topic, target, word_count, word_list, facts)

    try:
        result = llm_client.complete_json(
            system=generator.SYSTEM_PROMPT,
            user=user_prompt,
            model=config.MODEL_ARTICLE,
            max_tokens=12000,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文章生成失败：{e}")

    title = (result.get("title") or "").strip() or "Untitled"
    hard_list = result.get("hard_words", [])
    unused = [w.strip().lower() for w in result.get("unused_words", []) if w and w.strip()]
    translations = result.get("translations", []) or []
    hard_meanings = {h.get("word", "").strip().lower(): (h.get("meaning_cn") or "") for h in hard_list}
    paragraphs = generator.parse_paragraphs(result.get("paragraphs", []), target_meanings, hard_meanings)

    content = {
        "title": title,
        "topic": topic,
        "duration_min": duration,
        "target": target,
        "paragraphs": paragraphs,
        "translations": translations,
        "target_words": [{"word": w, "meaning_cn": target_meanings.get(w, "")} for w in word_list],
        "unused_words": unused,
        "hard_words": hard_list,
    }
    article_id = db.add_article(title, topic, duration, target, content)
    for w in word_list:
        db.link_article_word(article_id, w, "new")

    return {
        "article_id": article_id,
        "title": title,
        "paragraphs": paragraphs,
        "translations": translations,
        "target_words": [{"word": w, "meaning_cn": target_meanings.get(w, "")} for w in word_list],
        "unused_words": unused,
        "hard_words": hard_list,
        "sources": [
            {"source": f["source"], "title": f["title"], "link": f["link"], "published": f["published"]}
            for f in fact_list
        ],
        "no_facts": not fact_list,
    }


@router.post("/articles/generate")
async def generate_article(req: GenerateRequest):
    if req.target not in TARGETS:
        raise HTTPException(status_code=400, detail="target 必须是 四级/六级/考研/雅思/托福 之一。")
    duration = max(1, min(req.duration_min or 5, 30))

    # 目标单词 + 释义
    if req.words:
        word_list = [w.strip().lower() for w in req.words if w.strip()]
        target_meanings = db.get_word_meanings(word_list)
    else:
        today = datetime.date.today().isoformat()
        rows = db.list_words(today)
        word_list = [r["word"] for r in rows]
        target_meanings = {r["word"]: (r["meaning_cn"] or "") for r in rows}

    if not word_list:
        raise HTTPException(status_code=400, detail="还没有单词，请先上传截图并确认单词。")

    return await generate_article_core(req.topic, duration, req.target, word_list, target_meanings)
