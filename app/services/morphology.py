"""词形变化匹配：给定基础词，生成常见词形，并在文本中定位命中句子。

用途：功能三需要在新闻标题/摘要里匹配「今日单词」的词形变化，
例如 dance -> danced / dancing / dances。
"""
import re

# 常见不规则词形（小写）
IRREGULAR = {
    "be": {"am", "is", "are", "was", "were", "been", "being"},
    "have": {"has", "had", "having"},
    "do": {"does", "did", "done", "doing"},
    "go": {"goes", "went", "gone", "going"},
    "see": {"sees", "saw", "seen", "seeing"},
    "say": {"says", "said", "saying"},
    "get": {"gets", "got", "gotten", "getting"},
    "make": {"makes", "made", "making"},
    "know": {"knows", "knew", "known", "knowing"},
    "take": {"takes", "took", "taken", "taking"},
    "come": {"comes", "came", "coming"},
    "give": {"gives", "gave", "given", "giving"},
    "think": {"thinks", "thought", "thinking"},
    "find": {"finds", "found", "finding"},
    "tell": {"tells", "told", "telling"},
    "become": {"becomes", "became", "becoming"},
    "show": {"shows", "showed", "shown", "showing"},
    "leave": {"leaves", "left", "leaving"},
    "feel": {"feels", "felt", "feeling"},
    "put": {"puts", "put", "putting"},
    "bring": {"brings", "brought", "bringing"},
    "begin": {"begins", "began", "begun", "beginning"},
    "keep": {"keeps", "kept", "keeping"},
    "hold": {"holds", "held", "holding"},
    "write": {"writes", "wrote", "written", "writing"},
    "stand": {"stands", "stood", "standing"},
    "hear": {"hears", "heard", "hearing"},
    "let": {"lets", "let", "letting"},
    "mean": {"means", "meant", "meaning"},
    "set": {"sets", "set", "setting"},
    "meet": {"meets", "met", "meeting"},
    "run": {"runs", "ran", "running"},
    "pay": {"pays", "paid", "paying"},
    "sit": {"sits", "sat", "sitting"},
    "speak": {"speaks", "spoke", "spoken", "speaking"},
    "lead": {"leads", "led", "leading"},
    "read": {"reads", "read", "reading"},
    "grow": {"grows", "grew", "grown", "growing"},
    "lose": {"loses", "lost", "losing"},
    "fall": {"falls", "fell", "fallen", "falling"},
    "send": {"sends", "sent", "sending"},
    "build": {"builds", "built", "building"},
    "understand": {"understands", "understood", "understanding"},
    "break": {"breaks", "broke", "broken", "breaking"},
    "spend": {"spends", "spent", "spending"},
    "rise": {"rises", "rose", "risen", "rising"},
    "drive": {"drives", "drove", "driven", "driving"},
    "buy": {"buys", "bought", "buying"},
    "wear": {"wears", "wore", "worn", "wearing"},
    "choose": {"chooses", "chose", "chosen", "choosing"},
    "sing": {"sings", "sang", "sung", "singing"},
    "win": {"wins", "won", "winning"},
    "swim": {"swims", "swam", "swum", "swimming"},
}

_VOWELS = "aeiou"


def generate_forms(word: str) -> set[str]:
    """生成一个基础词的所有常见词形（含原词）。结果均为小写。"""
    w = word.strip().lower()
    if not w:
        return set()
    forms = {w}
    forms.update(IRREGULAR.get(w, set()))

    # 名词复数 / 动词三单
    if w.endswith(("s", "x", "z", "ch", "sh", "o")):
        forms.add(w + "es")
    else:
        forms.add(w + "s")

    # -y 结尾 -> -ies / -ied（study -> studies/studied）
    if w.endswith("y") and len(w) > 1 and w[-2] not in _VOWELS:
        forms.add(w[:-1] + "ies")
        forms.add(w[:-1] + "ied")

    # 过去式 -ed
    if w.endswith("e"):
        forms.add(w + "d")
    else:
        forms.add(w + "ed")

    # 现在分词 -ing
    if w.endswith("ie"):
        forms.add(w[:-2] + "ying")  # die -> dying
    elif w.endswith("e"):
        forms.add(w[:-1] + "ing")  # make -> making
    else:
        forms.add(w + "ing")

    # 重读闭音节双写：辅音 + 元音 + 辅音 结尾（run -> running, stop -> stopped）
    if (
        len(w) >= 3
        and w[-1] not in _VOWELS + "wxy"
        and w[-2] in _VOWELS
        and w[-3] not in _VOWELS
    ):
        forms.add(w + w[-1] + "ed")
        forms.add(w + w[-1] + "ing")

    # 比较级 / 最高级 / 施动者名词（dance -> dancer, produce -> producer）
    forms.add(w + "er")
    if w.endswith("e"):
        forms.add(w + "r")
    forms.add(w + "est")

    return forms


_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def find_sentence_with_forms(text: str, forms: set[str]) -> tuple[str | None, str | None]:
    """在文本中查找包含任一词形的句子，返回 (句子, 实际命中词形)。

    找不到时返回 (None, None)。
    """
    if not text:
        return None, None
    for sentence in _SENT_SPLIT.split(text):
        for form in forms:
            # 词边界 + 大小写不敏感
            pattern = rf"(?<![A-Za-z]){re.escape(form)}(?![A-Za-z])"
            m = re.search(pattern, sentence, re.IGNORECASE)
            if m:
                return sentence.strip(), m.group(0)
    return None, None


def find_sentences_with_forms(text: str, forms: set[str], limit: int = 3) -> list[tuple[str, str]]:
    """返回最多 limit 个包含任一词形的句子，形如 [(句子, 命中词形)]（句子去重）。"""
    if not text:
        return []
    results: list[tuple[str, str]] = []
    seen: set[str] = set()
    for sentence in _SENT_SPLIT.split(text):
        for form in forms:
            pattern = rf"(?<![A-Za-z]){re.escape(form)}(?![A-Za-z])"
            m = re.search(pattern, sentence, re.IGNORECASE)
            if m:
                s = sentence.strip()
                if s not in seen:
                    seen.add(s)
                    results.append((s, m.group(0)))
                break
        if len(results) >= limit:
            break
    return results


# ---- 词形还原与归一化（form -> base）----
_IRREGULAR_REVERSE: dict[str, str] = {}
for _base, _forms in IRREGULAR.items():
    _IRREGULAR_REVERSE.setdefault(_base, _base)
    for _f in _forms:
        _IRREGULAR_REVERSE.setdefault(_f, _base)


def lemmatize(word: str) -> str:
    """词形还原：dancing/ran/studies -> dance/run/study。"""
    w = word.lower()
    if w in _IRREGULAR_REVERSE:
        return _IRREGULAR_REVERSE[w]
    if w.endswith("ies") and len(w) > 3:
        return w[:-3] + "y"                # studies -> study
    if w.endswith("ing") and len(w) > 4:
        base = w[:-3]
        if base and base[-1] not in "aeiouy" and len(base) > 1:
            base += "e"                    # dancing -> dance
        return base
    if w.endswith("ed") and len(w) > 3:
        if w.endswith("ied"):
            return w[:-3] + "y"           # studied -> study
        base = w[:-2]
        if base and base[-1] not in "aeiouy" and len(base) > 1:
            base += "e"                   # danced -> dance
        return base
    if w.endswith("es") and len(w) > 3 and w[-3] in "xszho":
        return w[:-2]                     # boxes -> box
    if w.endswith("s") and len(w) > 2 and not w.endswith("ss"):
        return w[:-1]                     # dances -> dance, fans -> fan
    return w


def normalize_word(word: str) -> str:
    """把用户点击/输入的词规整成词库 key：去前后标点、转小写、去 's、词形还原。"""
    if not word:
        return ""
    w = word.strip().lower()
    w = re.sub(r"^[^a-z]+|[^a-z]+$", "", w)   # 去前后非字母（标点粘连）
    if not w:
        return ""
    w = re.sub(r"'s$", "", w)                   # idol's -> idol
    return lemmatize(w)
