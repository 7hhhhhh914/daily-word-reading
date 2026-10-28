"""FastAPI 入口：注册路由 + 托管前端静态文件。"""
import os

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .db import cleanup_wrongbook, init_db
from .routes import articles, news, review, words

app = FastAPI(title="每日单词阅读")

# 启动时建表 + 清理无来源文章 id 的脏错题数据
init_db()
_removed = cleanup_wrongbook()
if _removed:
    print(f"[清理] 删除无来源文章id的错题条目：{_removed}", flush=True)

# API 路由
app.include_router(news.router, prefix="/api")
app.include_router(words.router, prefix="/api")
app.include_router(articles.router, prefix="/api")
app.include_router(review.router, prefix="/api")

# 静态资源
app.mount("/static", StaticFiles(directory=config.STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(os.path.join(config.STATIC_DIR, "index.html"))
