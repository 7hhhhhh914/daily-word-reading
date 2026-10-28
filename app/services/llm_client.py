"""通用大模型客户端（OpenAI 兼容接口）。

适配国内大模型：阿里通义千问 / DeepSeek / 智谱 / Kimi 等，
只需在 .env 里改 LLM_BASE_URL / LLM_API_KEY / MODEL_OCR / MODEL_ARTICLE。
"""
import base64
import json
import re

import httpx

from .. import config

TIMEOUT = 120.0  # 生成文章可能较久

OCR_PROMPT = (
    "这是「不背单词」App 的单词详情截图。"
    "请提取图中每个英文单词的信息，输出 JSON："
    "{\"words\":[{\"word\":\"英文单词\",\"phonetic\":\"音标\",\"pos\":\"词性\",\"meaning_cn\":\"中文释义\"}]}。"
    "看不清或截图里没有的字段（音标/词性）就留空字符串 \"\"，不要瞎编。"
    "忽略界面按钮、图标、例句等无关内容。"
    "只输出 JSON，不要其他文字。如果图中没有单词，输出 {\"words\":[]}。"
)


def _check_key() -> None:
    if not config.LLM_API_KEY:
        raise RuntimeError("未配置 LLM_API_KEY，请在 .env 里填入国内大模型的 API Key。")


def _post(messages: list, model: str, max_tokens: int, temperature: float) -> dict:
    _check_key()
    url = config.LLM_BASE_URL.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }
    resp = httpx.post(
        url,
        json=payload,
        headers={"Authorization": f"Bearer {config.LLM_API_KEY}"},
        timeout=TIMEOUT,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"模型接口返回 {resp.status_code}：{resp.text[:300]}")
    return resp.json()


def _extract_text(data: dict) -> str:
    try:
        return data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError):
        return ""


def _parse_json(text: str) -> dict:
    """从模型输出里尽量抽出 JSON（容忍 markdown 代码块 / 前后缀）。"""
    text = (text or "").strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if m:
        text = m.group(1).strip()
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        return json.loads(text[start : end + 1])
    raise ValueError("模型输出不是有效 JSON")


def complete_json(system: str, user: str, model: str, max_tokens: int) -> dict:
    """文本结构化生成：返回解析后的 dict。"""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user})
    data = _post(messages, model, max_tokens, temperature=0.7)
    return _parse_json(_extract_text(data))


def ocr_image(image_bytes: bytes, media_type: str) -> list[dict]:
    """第一步：视觉模型读图，返回原始 [{word, phonetic, pos, meaning_cn}]。"""
    b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
    data_url = f"data:{media_type};base64,{b64}"
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": OCR_PROMPT},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        }
    ]
    data = _post(messages, config.MODEL_OCR, 2000, temperature=0.1)
    try:
        return _parse_json(_extract_text(data)).get("words", [])
    except (ValueError, AttributeError):
        return []


def structure_words(raw_words: list[dict]) -> list[dict]:
    """第二步：文本模型补全缺失字段，返回 [{word, phonetic, meanings:[{pos,meaning}], inferred}]。"""
    if not raw_words:
        return []
    raw_json = json.dumps({"words": raw_words}, ensure_ascii=False)
    prompt = (
        "下面是从背单词截图提取的原始单词数据。请为每个单词补全缺失字段：\n"
        "- word 保持小写不变\n"
        "- phonetic 为空则补英式音标（如 /əˈbændən/）\n"
        "- 为每个单词给出词性和中文释义，放在 meanings 数组里；一个单词有多个词性就分行列出\n"
        "输出 JSON：{\"words\":[{\"word\":\"...\",\"phonetic\":\"...\","
        "\"meanings\":[{\"pos\":\"v.\",\"meaning\":\"提升；增进\"},{\"pos\":\"n.\",\"meaning\":\"提升\"}],"
        "\"inferred\":[\"phonetic\",\"meanings\"]}]}\n"
        "inferred 列出你补全（原本缺失）的字段名；没补全则为空数组。只输出 JSON，不要其他文字。\n\n"
        f"原始数据：\n{raw_json}"
    )
    data = _post([{"role": "user", "content": prompt}], config.MODEL_ARTICLE, 3000, temperature=0.1)
    try:
        words = _parse_json(_extract_text(data)).get("words", [])
    except (ValueError, AttributeError):
        words = raw_words
    out = []
    for w in words:
        m = w.get("meanings")
        if not m and (w.get("pos") or w.get("meaning_cn")):
            m = [{"pos": w.get("pos", ""), "meaning": w.get("meaning_cn", "")}]
        w["meanings"] = m or []
        out.append(w)
    return out


def lookup_word(word: str) -> dict:
    """即时查词：返回英文单词的完整信息（音标/词性/释义/例句/搭配等）。"""
    prompt = (
        f"请查英文单词「{word}」的完整信息，输出 JSON："
        "{\"phonetic\":\"音标\",\"meanings\":[{\"pos\":\"词性\",\"meaning\":\"中文释义\"}],"
        "\"meaning_en\":\"英文释义\",\"example\":\"英文例句（附中文翻译）\","
        "\"collocations\":\"常见搭配、词根、近反义词（中文说明）\"}。"
        "一个单词有多个词性时 meanings 数组列出多条。只输出 JSON，不要其他文字。"
    )
    data = _post([{"role": "user", "content": prompt}], config.MODEL_ARTICLE, 500, temperature=0.1)
    try:
        return _parse_json(_extract_text(data))
    except (ValueError, AttributeError):
        return {}
