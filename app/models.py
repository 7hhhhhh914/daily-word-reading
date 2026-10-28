"""数据库表结构（SQLite）。功能三暂未用到，为功能一/二预留。"""

SCHEMA = """
CREATE TABLE IF NOT EXISTS words (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    word            TEXT    NOT NULL UNIQUE,      -- 单词（小写）
    phonetic        TEXT,                         -- 音标
    pos             TEXT,                         -- 词性（旧字段，兼容）
    meaning_cn      TEXT,                         -- 中文释义（旧字段，兼容）
    meanings        TEXT,                         -- 词性+释义数组 JSON：[{pos, meaning}]
    note            TEXT,                         -- 用户自己补充的释义（中文或英文）
    first_seen_date TEXT    NOT NULL,             -- 首次录入日期 YYYY-MM-DD
    source          TEXT,                         -- 来源：screenshot / text / csv / txt
    created_at      TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS articles (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT,
    topic        TEXT,
    duration_min INTEGER,
    target       TEXT,                            -- 四六级 / 考研 / 雅思 / 托福
    content_json TEXT,                            -- 结构化文章内容（含高亮标记）
    created_at   TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS article_words (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id INTEGER NOT NULL,
    word_id    INTEGER NOT NULL,
    kind       TEXT    NOT NULL,                  -- 'new' 今日新词 / 'hard' 偏难词
    FOREIGN KEY (article_id) REFERENCES articles (id),
    FOREIGN KEY (word_id) REFERENCES words (id)
);

CREATE TABLE IF NOT EXISTS reviews (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    word_id    INTEGER NOT NULL,
    article_id INTEGER,
    known      INTEGER NOT NULL,                  -- 1 认识 / 0 不认识
    created_at TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (word_id) REFERENCES words (id)
);

CREATE INDEX IF NOT EXISTS idx_words_date ON words (first_seen_date);
CREATE INDEX IF NOT EXISTS idx_reviews_word ON reviews (word_id);
"""
