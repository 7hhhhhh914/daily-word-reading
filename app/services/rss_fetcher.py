"""抓取英文媒体 RSS，带小时级缓存（存 data/news_cache.json）。

版权约定：只取标题、短摘要（单句）和原文链接，不转载全文。
"""
import asyncio
import json
import os
import re
import time
from urllib.parse import quote

import feedparser
import httpx

from .. import config

_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) DailyWordReader/0.1"
_TAG_RE = re.compile(r"<[^>]+>")

_CACHE_FILE = os.path.join(config.DATA_DIR, "news_cache.json")
_CACHE_TTL = 3600  # 1 小时


def _strip_html(s: str) -> str:
    return re.sub(_TAG_RE, "", s or "").strip()


def _summary_of(entry) -> str:
    """优先取 summary/description，兜底取 content 片段。"""
    raw = getattr(entry, "summary", "") or getattr(entry, "description", "") or ""
    raw = _strip_html(raw)
    if raw:
        return raw
    content = getattr(entry, "content", None)
    if content:
        return _strip_html(content[0].get("value", ""))
    return ""


async def fetch_source(source: dict, timeout: int | None = None) -> list[dict]:
    """抓取单个 RSS 源，返回条目列表（失败抛异常，由调用方决定是否忽略）。"""
    timeout = timeout or config.RSS_TIMEOUT
    async with httpx.AsyncClient(follow_redirects=True, timeout=timeout, proxy=config.PROXY or None) as client:
        resp = await client.get(source["url"], headers={"User-Agent": _UA})
        resp.raise_for_status()

    feed = feedparser.parse(resp.text)
    entries: list[dict] = []
    for e in feed.entries[: config.RSS_MAX_ENTRIES]:
        entries.append(
            {
                "title": getattr(e, "title", "").strip(),
                "summary": _summary_of(e),
                "link": getattr(e, "link", "").strip(),
                "published": getattr(e, "published", "")
                or getattr(e, "updated", ""),
                "source": source["name"],
                "category": source.get("category", "general"),
            }
        )
    return entries


async def fetch_all() -> tuple[list[dict], dict[str, str]]:
    """并行抓取所有源，单个源失败不影响整体。返回 (条目列表, {源名: ok/fail})。"""
    async def _one(src):
        try:
            return src["name"], await fetch_source(src), "ok"
        except Exception:
            return src["name"], [], "fail"

    outcomes = await asyncio.gather(*[_one(src) for src in config.RSS_SOURCES])
    results: list[dict] = []
    status: dict[str, str] = {}
    for name, entries, st in outcomes:
        status[name] = st
        results.extend(entries)
    return results, status


def _load_cache() -> dict | None:
    try:
        with open(_CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _save_cache(entries: list[dict], status: dict[str, str]) -> None:
    os.makedirs(config.DATA_DIR, exist_ok=True)
    with open(_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump({"fetched_at": time.time(), "entries": entries, "status": status}, f, ensure_ascii=False)


async def search_google_news(query: str) -> list[dict]:
    """Google News RSS 关键词搜索（需代理，否则超时）。返回统一格式条目。"""
    url = f"https://news.google.com/rss/search?q={quote(query)}&hl=en-US&gl=US&ceid=US:en"
    async with httpx.AsyncClient(follow_redirects=True, timeout=config.RSS_TIMEOUT, proxy=config.PROXY or None) as client:
        resp = await client.get(url, headers={"User-Agent": _UA})
        resp.raise_for_status()
    feed = feedparser.parse(resp.text)
    entries = []
    for e in feed.entries[: config.RSS_MAX_ENTRIES]:
        entries.append({
            "title": getattr(e, "title", "").strip(),
            "summary": _summary_of(e),
            "link": getattr(e, "link", "").strip(),
            "published": getattr(e, "published", "") or getattr(e, "updated", ""),
            "source": "Google News",
            "category": "general",
        })
    return entries


async def fetch_all_cached() -> tuple[list[dict], dict[str, str]]:
    """带缓存的抓取：1 小时内直接返回缓存，否则并行重新抓取并写缓存。"""
    cache = _load_cache()
    if cache and (time.time() - cache.get("fetched_at", 0)) < _CACHE_TTL:
        return cache.get("entries", []), cache.get("status", {})
    entries, status = await fetch_all()
    if entries:
        _save_cache(entries, status)
    return entries, status
