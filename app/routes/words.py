"""功能一：单词输入 —— 截图上传 / 文本粘贴 / txt·csv 导入。"""
import csv
import datetime
import re
import time

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from .. import db
from ..services import llm_client, morphology

router = APIRouter()

# Anthropic 支持的图片类型
ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}


class ImportRequest(BaseModel):
    text: str = ""          # 粘贴的文本内容
    source: str = "text"    # text / txt / csv


class SaveRequest(BaseModel):
    words: list[dict] = []  # [{word, phonetic, pos, meaning_cn}]


def parse_word_text(text: str, source: str) -> list[dict]:
    """把多行文本解析成 [{word, meaning_cn}]。

    支持两种常见格式：
      - 文本：每行「单词 释义」（用空白分隔，第一段是单词）
      - CSV： 每行「单词,释义」
    """
    words: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if source == "csv" or "," in line:
            parts = next(csv.reader([line]), [])
        else:
            parts = re.split(r"\s+", line, maxsplit=1)

        if not parts:
            continue
        word = parts[0].strip().strip("·*—").lower()
        meaning = parts[1].strip() if len(parts) > 1 else ""
        # 只保留看起来像英文单词的（过滤标题行、中文行等）
        if word and re.fullmatch(r"[a-zA-Z][a-zA-Z\-']*", word):
            words.append({"word": word, "meaning_cn": meaning})
    return words


@router.post("/words/upload")
async def upload_screenshot(file: UploadFile = File(...)):
    """上传不背单词截图，调用 Anthropic 图片识别提取单词。"""
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="只支持 PNG / JPEG / WebP / GIF 图片。")
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="图片内容为空。")

    try:
        raw = llm_client.ocr_image(image_bytes, file.content_type)
        words = llm_client.structure_words(raw)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="图片识别失败，请稍后重试。")

    today = datetime.date.today().isoformat()
    new, total = db.upsert_words(words, source="screenshot", date_str=today)
    return {"new": new, "total": total, "words": words}


@router.post("/words/recognize")
async def recognize_screenshots(files: list[UploadFile] = File(...)):
    """识别多张截图（不保存），返回去重后的 [{word, phonetic, pos, meaning_cn, inferred}]。"""
    all_words: list[dict] = []
    valid = 0
    for f in files:
        if f.content_type not in ALLOWED_IMAGE_TYPES:
            continue
        image_bytes = await f.read()
        if not image_bytes:
            continue
        valid += 1
        try:
            t0 = time.time()
            raw = llm_client.ocr_image(image_bytes, f.content_type)
            t1 = time.time()
            structured = llm_client.structure_words(raw)
            t2 = time.time()
            print(f"[计时] {f.filename}: 识图 {t1 - t0:.2f}s, 补全 {t2 - t1:.2f}s, 合计 {t2 - t0:.2f}s", flush=True)
            all_words.extend(structured)
        except Exception:
            continue  # 单张失败不影响整体
    if valid == 0:
        raise HTTPException(status_code=400, detail="没有有效的图片，请上传 jpg / png / webp 格式的截图。")
    seen: set[str] = set()
    deduped: list[dict] = []
    for w in all_words:
        word = (w.get("word") or "").strip().lower()
        if word and word not in seen:
            seen.add(word)
            deduped.append(w)
    return {"words": deduped}


@router.post("/words/save")
async def save_words(req: SaveRequest):
    """保存确认后的单词列表。"""
    if not req.words:
        raise HTTPException(status_code=400, detail="没有要保存的单词。")
    today = datetime.date.today().isoformat()
    new, total = db.upsert_words(req.words, source="screenshot", date_str=today)
    return {"new": new, "total": total}


@router.delete("/words/{word}")
async def delete_word(word: str):
    """删除某个单词。"""
    ok = db.delete_word(word.strip().lower())
    if not ok:
        raise HTTPException(status_code=404, detail="单词不存在。")
    return {"word": word, "deleted": True}


@router.post("/words/import")
async def import_words(req: ImportRequest):
    """从粘贴文本 / txt / csv 导入单词。"""
    words = parse_word_text(req.text, req.source)
    if not words:
        raise HTTPException(status_code=400, detail="没有解析到单词，请检查格式（每行：单词 释义）。")
    today = datetime.date.today().isoformat()
    new, total = db.upsert_words(words, source=req.source, date_str=today)
    return {"new": new, "total": total, "words": words}


@router.get("/words")
async def list_words(date: str | None = None):
    """按日期查看已录入的单词（默认今天）。"""
    date = date or datetime.date.today().isoformat()
    return {"date": date, "words": db.list_words(date)}


@router.get("/lookup")
async def lookup(word: str):
    """即时查词：归一化 + 本地词库优先 + 在线词典兜底，查不到也不报错。"""
    w = morphology.normalize_word(word)
    if not w:
        return {"word": word, "phonetic": "", "meanings": [], "meaning_en": "", "example": "", "collocations": ""}
    local = db.get_words_info([w]).get(w, {})
    info: dict = {}
    try:
        info = llm_client.lookup_word(w)
    except Exception:
        info = {}
    if not info.get("meanings"):
        info["meanings"] = local.get("meanings") or [{"pos": local.get("pos", ""), "meaning": local.get("meaning_cn", "")}]
    if not info.get("phonetic"):
        info["phonetic"] = local.get("phonetic", "")
    if local.get("note"):
        info["note"] = local["note"]
    info.setdefault("meaning_en", "")
    info.setdefault("example", "")
    info.setdefault("collocations", "")
    return {"word": w, "original": word, **info}
