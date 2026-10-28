"""认识/不认识标记 + 错题本 + 复习文章。"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import db
from ..services import morphology
from .articles import TARGETS, generate_article_core

router = APIRouter()


class ReviewRequest(BaseModel):
    word: str
    known: bool
    article_id: int | None = None


class ReviewGenerateRequest(BaseModel):
    topic: str = "K-pop"
    duration_min: int = 5
    target: str = "四级"


@router.post("/reviews")
async def record_review(req: ReviewRequest):
    w = morphology.normalize_word(req.word)
    if not w:
        raise HTTPException(status_code=400, detail="无效单词。")
    db.record_review(w, req.known, req.article_id)
    return {"word": w, "original": req.word, "known": req.known}


@router.get("/wrongbook")
async def wrongbook():
    return {"words": db.get_wrong_words()}


@router.delete("/wrongbook")
async def clear_wrongbook():
    n = db.clear_wrongbook()
    return {"cleared": n}


@router.post("/review/generate")
async def generate_review(req: ReviewGenerateRequest):
    if req.target not in TARGETS:
        raise HTTPException(status_code=400, detail="target 必须是 四级/六级/考研/雅思/托福 之一。")
    rows = db.get_wrong_words()
    if not rows:
        raise HTTPException(status_code=400, detail="错题本是空的，先去「生成文章」里把不认识的词标记出来吧。")
    word_list = [r["word"] for r in rows]
    target_meanings = {r["word"]: (r["meaning_cn"] or "") for r in rows}
    duration = max(1, min(req.duration_min or 5, 30))
    return await generate_article_core(req.topic, duration, req.target, word_list, target_meanings)
