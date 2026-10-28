"""SQLite 连接与基础操作。"""
import datetime
import json
import os
import sqlite3

from . import config
from .models import SCHEMA


def get_conn() -> sqlite3.Connection:
    os.makedirs(config.DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_conn()
    try:
        conn.executescript(SCHEMA)
        # 迁移：为旧库补列（CREATE TABLE IF NOT EXISTS 不会给已有表加列）
        for col in ("phonetic", "pos", "meaning_cn", "meanings", "note"):
            try:
                conn.execute(f"ALTER TABLE words ADD COLUMN {col} TEXT")
            except sqlite3.OperationalError:
                pass
        conn.commit()
    finally:
        conn.close()


def get_words_by_date(date_str: str) -> list[str]:
    """返回某日期录入的所有单词（用于「今日单词」匹配）。"""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT word FROM words WHERE first_seen_date = ? ORDER BY id", (date_str,)
        ).fetchall()
        return [r["word"] for r in rows]
    finally:
        conn.close()


def _to_meanings(e: dict) -> list[dict]:
    """把条目统一成 [{pos, meaning}]：优先用 meanings 字段，否则由 pos/meaning_cn 构造。"""
    if e.get("meanings"):
        return e["meanings"]
    if e.get("pos") or e.get("meaning_cn"):
        return [{"pos": e.get("pos") or "", "meaning": e.get("meaning_cn") or ""}]
    return []


def _parse_meanings(raw: str) -> list[dict]:
    try:
        m = json.loads(raw) if raw else []
        return m if isinstance(m, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def upsert_words(entries: list[dict], source: str, date_str: str) -> tuple[int, int]:
    """批量写入单词，返回 (新增数, 处理总数)。

    entries: [{word, phonetic, meanings:[{pos,meaning}]}]。已存在的词只补缺失字段，不改首次日期。
    """
    conn = get_conn()
    new = 0
    total = 0
    try:
        for e in entries:
            word = (e.get("word") or "").strip().lower()
            if not word:
                continue
            total += 1
            phonetic = (e.get("phonetic") or "").strip()
            note = (e.get("note") or "").strip()
            meanings = _to_meanings(e)
            meanings_json = json.dumps(meanings, ensure_ascii=False) if meanings else ""
            first_pos = meanings[0].get("pos", "") if meanings else ""
            first_meaning = meanings[0].get("meaning", "") if meanings else ""

            exists = conn.execute("SELECT 1 FROM words WHERE word = ?", (word,)).fetchone()
            if exists:
                conn.execute(
                    "UPDATE words SET "
                    "phonetic = CASE WHEN ? != '' THEN ? ELSE phonetic END, "
                    "meanings = CASE WHEN ? != '' THEN ? ELSE meanings END, "
                    "note = CASE WHEN ? != '' THEN ? ELSE note END, "
                    "pos = CASE WHEN ? != '' THEN ? ELSE pos END, "
                    "meaning_cn = CASE WHEN ? != '' THEN ? ELSE meaning_cn END "
                    "WHERE word = ?",
                    (phonetic, phonetic, meanings_json, meanings_json, note, note,
                     first_pos, first_pos, first_meaning, first_meaning, word),
                )
            else:
                conn.execute(
                    "INSERT INTO words (word, phonetic, pos, meaning_cn, meanings, note, first_seen_date, source) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (word, phonetic, first_pos, first_meaning, meanings_json, note, date_str, source),
                )
                new += 1
        conn.commit()
    finally:
        conn.close()
    return new, total


def list_words(date_str: str) -> list[dict]:
    """返回某日期录入的单词详情列表（含 meanings 数组）。"""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT id, word, phonetic, pos, meaning_cn, meanings, first_seen_date, source "
            "FROM words WHERE first_seen_date = ? ORDER BY id",
            (date_str,),
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            raw = d.pop("meanings", None)
            m = _parse_meanings(raw)
            d["meanings"] = m or [{"pos": d.get("pos") or "", "meaning": d.get("meaning_cn") or ""}]
            out.append(d)
        return out
    finally:
        conn.close()


def delete_word(word: str) -> bool:
    """删除单词，返回是否删除成功。"""
    conn = get_conn()
    try:
        cur = conn.execute("DELETE FROM words WHERE word = ?", (word,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def get_word_meanings(words: list[str]) -> dict[str, str]:
    """批量查询单词释义，返回 {word: meaning_cn}（取第一个释义）。"""
    if not words:
        return {}
    conn = get_conn()
    try:
        q = ",".join("?" * len(words))
        rows = conn.execute(
            f"SELECT word, meaning_cn, meanings FROM words WHERE word IN ({q})", words
        ).fetchall()
        out = {}
        for r in rows:
            m = _parse_meanings(r["meanings"])
            if m:
                out[r["word"]] = m[0].get("meaning", "") or r["meaning_cn"] or ""
            else:
                out[r["word"]] = r["meaning_cn"] or ""
        return out
    finally:
        conn.close()


def add_article(title: str, topic: str, duration_min: int, target: str, content: dict) -> int:
    """保存生成的文章，返回 article_id。"""
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO articles (title, topic, duration_min, target, content_json) "
            "VALUES (?, ?, ?, ?, ?)",
            (title, topic, duration_min, target, json.dumps(content, ensure_ascii=False)),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def link_article_word(article_id: int, word: str, kind: str) -> None:
    """把文章与其用到的目标单词关联起来（供后续认识/不认识标记）。"""
    conn = get_conn()
    try:
        row = conn.execute("SELECT id FROM words WHERE word = ?", (word,)).fetchone()
        if row:
            conn.execute(
                "INSERT INTO article_words (article_id, word_id, kind) VALUES (?, ?, ?)",
                (article_id, row["id"], kind),
            )
            conn.commit()
    finally:
        conn.close()


def record_review(word: str, known: bool, article_id: int | None = None) -> bool:
    """记录一次「认识/不认识」。词库没有就自动创建；同一(词,文章)只保留最新一条（去重计数）。"""
    conn = get_conn()
    try:
        row = conn.execute("SELECT id FROM words WHERE word = ?", (word,)).fetchone()
        if not row:
            cur = conn.execute(
                "INSERT INTO words (word, first_seen_date, source) VALUES (?, ?, ?)",
                (word, datetime.date.today().isoformat(), "lookup"),
            )
            word_id = cur.lastrowid
        else:
            word_id = row["id"]
        new_known = 1 if known else 0
        existing = conn.execute(
            "SELECT id FROM reviews WHERE word_id = ? AND article_id IS ? ORDER BY id DESC LIMIT 1",
            (word_id, article_id),
        ).fetchone()
        if existing:
            conn.execute("UPDATE reviews SET known = ? WHERE id = ?", (new_known, existing["id"]))
        else:
            conn.execute(
                "INSERT INTO reviews (word_id, article_id, known) VALUES (?, ?, ?)",
                (word_id, article_id, new_known),
            )
        conn.commit()
        return True
    finally:
        conn.close()


def clear_wrongbook() -> int:
    """清空错题本（删除所有 reviews）。"""
    conn = get_conn()
    try:
        cur = conn.execute("DELETE FROM reviews")
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def cleanup_wrongbook() -> list[str]:
    """清理脏数据：删除没有来源文章 id（NULL 或引用不存在文章）的 review，及其对应的无释义 lookup 空词。"""
    conn = get_conn()
    removed: list[str] = []
    try:
        rows = conn.execute(
            "SELECT w.word FROM reviews r JOIN words w ON w.id = r.word_id "
            "WHERE r.article_id IS NULL OR r.article_id NOT IN (SELECT id FROM articles)"
        ).fetchall()
        removed = [r["word"] for r in rows]
        conn.execute(
            "DELETE FROM reviews WHERE article_id IS NULL OR article_id NOT IN (SELECT id FROM articles)"
        )
        # 删除无释义、无引用、source=lookup 的空词（比如测试/查词自动建的）
        conn.execute(
            "DELETE FROM words WHERE source='lookup' AND (meaning_cn IS NULL OR meaning_cn='') "
            "AND (meanings IS NULL OR meanings='') AND id NOT IN (SELECT DISTINCT word_id FROM reviews)"
        )
        conn.commit()
    finally:
        conn.close()
    return removed


def get_wrong_words() -> list[dict]:
    """错题本：最近一次标记为「不认识」的单词（含完整信息）。"""
    conn = get_conn()
    try:
        rows = conn.execute(
            """
            SELECT w.id, w.word, w.phonetic, w.pos, w.meaning_cn, w.meanings,
                   w.first_seen_date, w.source,
                   (SELECT COUNT(*) FROM reviews r WHERE r.word_id = w.id AND r.known = 0)
                   AS wrong_count
            FROM words w
            WHERE (SELECT known FROM reviews r WHERE r.word_id = w.id
                   ORDER BY r.id DESC LIMIT 1) = 0
            ORDER BY w.id
            """
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            raw = d.pop("meanings", None)
            m = _parse_meanings(raw)
            d["meanings"] = m or [{"pos": d.get("pos") or "", "meaning": d.get("meaning_cn") or ""}]
            out.append(d)
        return out
    finally:
        conn.close()


def get_words_info(words: list[str]) -> dict[str, dict]:
    """批量查询单词的完整信息，返回 {word: {phonetic, pos, meaning_cn}}。"""
    if not words:
        return {}
    conn = get_conn()
    try:
        q = ",".join("?" * len(words))
        rows = conn.execute(
            f"SELECT word, phonetic, pos, meaning_cn, meanings, note FROM words WHERE word IN ({q})", words
        ).fetchall()
        out = {}
        for r in rows:
            m = _parse_meanings(r["meanings"]) or [{"pos": r["pos"] or "", "meaning": r["meaning_cn"] or ""}]
            out[r["word"]] = {
                "phonetic": r["phonetic"] or "",
                "pos": m[0].get("pos", "") if m else (r["pos"] or ""),
                "meaning_cn": m[0].get("meaning", "") if m else (r["meaning_cn"] or ""),
                "meanings": m,
                "note": r["note"] or "",
            }
        return out
    finally:
        conn.close()
