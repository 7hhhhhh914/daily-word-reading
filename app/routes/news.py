"""功能三：单词新闻 —— 选主题 + 选单词 → 检索匹配新闻。"""
import datetime
import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import db
from ..services import morphology, rss_fetcher

router = APIRouter()


class NewsSearchRequest(BaseModel):
    topic: str = ""            # 话题
    words: list[str] = []      # 选中的单词


def _split_words(raw: list[str]) -> list[str]:
    words: list[str] = []
    for chunk in raw:
        for w in re.split(r"[\s,，;；]+", chunk):
            w = w.strip().lower()
            if w and w not in words:
                words.append(w)
    return words


def _normalize(s: str) -> str:
    """去掉非字母数字字符并转小写，用于话题模糊匹配（kpop == K-pop）。"""
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _topic_category(topic_norm: str) -> str | None:
    """根据主题归一化结果，返回要筛选的新闻分类；无法判断时返回 None（用全部来源）。"""
    if not topic_norm:
        return None
    kpop_kw = ("kpop", "bts", "blackpink", "seventeen", "twice", "idol", "hallyu", "aespa", "newjeans")
    if any(k in topic_norm for k in kpop_kw):
        return "kpop"
    ent_kw = ("影视剧", "娱乐", "电影", "电视剧", "movie", "drama", "music", "音乐", "tv")
    if any(k in topic_norm for k in ent_kw):
        return "entertainment"
    return None


@router.get("/news/word-options")
async def word_options():
    """返回可选的单词（今日已确认 + 错题本），供新闻板块勾选。"""
    today = datetime.date.today().isoformat()
    return {"today": db.list_words(today), "wrongbook": db.get_wrong_words()}


@router.post("/news/search")
async def search_news(req: NewsSearchRequest):
    words = _split_words(req.words)
    if not words:
        raise HTTPException(status_code=400, detail="请至少选择一个单词。")

    cat = _topic_category(_normalize(req.topic))
    info_map = db.get_words_info(words)
    entries, status = await rss_fetcher.fetch_all_cached()

    # 附加 Google News 关键词搜索（需代理，失败不影响，帮助覆盖 dance/producer 这类词）
    query = " ".join(words[:2])
    if req.topic:
        query = (query + " " + req.topic).strip()
    try:
        gnews = await rss_fetcher.search_google_news(query)
        if gnews:
            if cat:
                for g in gnews:
                    g["category"] = cat  # 让 Google News 结果通过话题分类筛选
            entries = list(entries) + gnews
            status["Google News"] = "ok"
    except Exception:
        status["Google News"] = "fail"

    results: list[dict] = []
    for e in entries:
        # 主题分类筛选：K-pop 主题只用 kpop 来源，娱乐主题只用娱乐/音乐来源（不做关键词硬过滤）
        if cat and e.get("category") != cat:
            continue
        text = f"{e['title']}. {e['summary']}"
        matches = []
        for w in words:
            forms = morphology.generate_forms(w)
            found = morphology.find_sentences_with_forms(text, forms, limit=3)
            if found:
                info = info_map.get(w, {})
                matches.append({
                    "word": w,
                    "phonetic": info.get("phonetic", ""),
                    "pos": info.get("pos", ""),
                    "meaning_cn": info.get("meaning_cn", ""),
                    "sentences": [{"text": s, "matched": m} for s, m in found],
                })
        if matches:
            results.append({
                "title": e["title"], "source": e["source"], "link": e["link"],
                "published": e["published"], "matches": matches,
                "hit_count": len(matches),
            })

    # 按命中词数量从多到少排序
    results.sort(key=lambda r: -r["hit_count"])

    ok_count = sum(1 for s in status.values() if s == "ok")
    fail_sources = [n for n, s in status.items() if s == "fail"]
    stats = {"total_sources": len(status), "ok": ok_count, "fail": fail_sources, "articles": len(entries)}

    note = None
    if not results:
        note = (f"已检索 {len(status)} 个来源（成功 {ok_count}，失败 {len(fail_sources)}），"
                f"共 {len(entries)} 篇，命中 0 篇。")
        if fail_sources:
            note += f" 失败来源：{'、'.join(fail_sources)}。"
        note += " 建议换词或减少单词数量。"

    results = results[:50]
    return {"topic": req.topic, "words": words, "note": note, "count": len(results),
            "source_stats": stats, "results": results}
