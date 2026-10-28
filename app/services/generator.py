"""功能二：生成文章 —— 提示词模板 + 高亮标记解析。"""
import re

# 考试等级 → 难度描述
TARGET_DESC = {
    "四级": "大学英语四级 CET-4，词汇约 4500，句式中等偏简单",
    "六级": "大学英语六级 CET-6，词汇约 6000，句式较复杂",
    "考研": "考研英语，词汇学术，句式复杂",
    "雅思": "雅思 IELTS，词汇学术，句式多样",
    "托福": "托福 TOEFL，词汇学术，句式复杂",
}

# 系统提示词（静态，不含需替换的占位符，避免花括号转义问题）
SYSTEM_PROMPT = """你是一位英语阅读材料编写者，为备考英语考试的中国学生编写英文阅读文章。

核心原则：先围绕主题写一篇自然流畅的文章，再把单词自然融入；塞不进去的单词宁可不用、列到末尾，也不要硬凑。

写作要求：
1. 写作前，先把下面「今日真实新闻事实」抽成事实要点（谁、何时、做了什么、来源），只写要点里出现过的事实，禁止添加要点以外的任何事实、数据、人名或引语。
2. 文章主体（约 70% 以上）必须围绕最新一条报道展开，开头注明「基于 X 月 X 日报道」；如果报道里提到旧事（上次回归、此前争议、出道经历等），另起一段「背景」，写明事件发生时间。新旧信息冲突时以新为准，旧的只作背景。
3. 写作过程中，把「目标单词」自然融入合适的位置：能用上就用，用上时尽量用惯用搭配或特殊时态帮助理解，并用 [[单词]] 标出来。某个词实在融入不了，就放进 unused_words，不要为了用词而硬塞。
4. 词汇量和句式复杂度严格按照用户给出的考试等级控制（四级最简单、六级和考研更难、雅思托福学术）。

输出格式（只输出 JSON，不要输出任何 JSON 以外的文字）：
- title：文章标题
- paragraphs：字符串数组，每个元素一个段落；段落中把用上的「目标单词」用 [[单词]] 包裹；把想让学生额外留意的偏难词用 {{单词}} 包裹（每个偏难词只标一次）
- translations：与 paragraphs 一一对应的中文翻译数组，每个元素是对应段落的自然通顺中文翻译，人名、地名、组合名、作品名等专有名词保持原文不译
- unused_words：没能自然融入、放弃使用的目标单词数组（可为空）
- hard_words：所有 {{}} 标出的偏难词的中文释义数组，形如 [{"word": "...", "meaning_cn": "中文释义"}]
"""

ARTICLE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "paragraphs": {"type": "array", "items": {"type": "string"}},
        "translations": {"type": "array", "items": {"type": "string"}},
        "unused_words": {"type": "array", "items": {"type": "string"}},
        "hard_words": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "word": {"type": "string"},
                    "meaning_cn": {"type": "string"},
                },
                "required": ["word", "meaning_cn"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["title", "paragraphs", "translations", "unused_words", "hard_words"],
    "additionalProperties": False,
}

# 匹配 [[目标词]] 或 {{偏难词}}
_MARK_RE = re.compile(r"\[\[([^\]]+)\]\]|\{\{([^}]+)\}\}")

# 常见停用词：模型误标成「偏难词」时，不当作链接，原样当普通文本
STOP_WORDS = {
    "the", "a", "an", "is", "am", "are", "was", "were", "be", "been", "being",
    "and", "or", "but", "of", "to", "in", "on", "at", "for", "with", "as", "by",
    "it", "he", "she", "they", "we", "you", "i", "this", "that", "these", "those",
    "his", "her", "their", "our", "its", "not", "no", "yes", "do", "does", "did",
    "have", "has", "had", "will", "would", "can", "could", "should", "may", "might",
    "must", "so", "if", "then", "than", "when", "where", "who", "what", "which",
    "how", "why", "very", "just", "also", "such", "from", "into", "about", "over",
    "under", "again", "once", "only", "up", "down", "out", "all", "any", "some",
    "other", "each", "both", "few", "more", "most", "own", "same", "new", "old",
    "first", "last", "next", "even", "back", "still", "well", "way", "time",
    "people", "year", "day", "one", "two", "three", "also", "after", "before",
}


def build_user_prompt(topic: str, target: str, word_count: int, words: list[str], facts: str) -> str:
    """拼用户消息：话题 + 目标 + 长度 + 目标单词 + 新闻事实。"""
    desc = TARGET_DESC.get(target, target)
    return (
        f"话题：{topic}\n"
        f"考试目标：{target}（{desc}）\n"
        f"文章长度：约 {word_count} 词\n\n"
        f"目标单词（必须全部自然用进文章）：\n{', '.join(words)}\n\n"
        f"今日真实新闻事实（文章要基于这些事实写）：\n{facts}\n"
    )


def parse_paragraphs(paragraphs: list[str], target_meanings: dict, hard_meanings: dict) -> list[list[dict]]:
    """把带 [[word]] / {{word}} 标记的段落解析成前端可渲染的分段列表。

    每个段落是一个 list，元素为：
      {"type": "text", "text": ...} / {"type": "target", "word", "meaning_cn"} / {"type": "hard", ...}
    """
    out: list[list[dict]] = []
    for para in paragraphs:
        segs: list[dict] = []
        pos = 0
        for m in _MARK_RE.finditer(para):
            if m.start() > pos:
                segs.append({"type": "text", "text": para[pos:m.start()]})
            if m.group(1) is not None:
                w = m.group(1).strip().lower()
                segs.append({"type": "target", "word": w, "meaning_cn": target_meanings.get(w, "")})
            else:
                w = m.group(2).strip().lower()
                if w in STOP_WORDS:
                    # 停用词不当难词链接，原样当普通文本
                    segs.append({"type": "text", "text": m.group(0)})
                else:
                    segs.append({"type": "hard", "word": w, "meaning_cn": hard_meanings.get(w, "")})
            pos = m.end()
        if pos < len(para):
            segs.append({"type": "text", "text": para[pos:]})
        out.append(segs)
    return out
