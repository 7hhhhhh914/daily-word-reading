"""自检脚本：用常见词跑一遍新闻检索，打印每个词命中的文章数。

用法：cd 到项目根目录后运行
    .venv/bin/python scripts/check_news.py
"""
import asyncio
import sys

sys.path.insert(0, ".")  # 让脚本能 import app

from app.services import morphology, rss_fetcher

WORDS = ["producer", "stray kids", "dance", "comeback", "debut", "tour",
         "fans", "album", "award", "release"]


def hit(text: str, word: str) -> bool:
    w = word.lower()
    if " " in w:
        return w in text.lower()
    sent, _ = morphology.find_sentence_with_forms(text, morphology.generate_forms(w))
    return sent is not None


async def main():
    entries, status = await rss_fetcher.fetch_all_cached()
    print(f"缓存共 {len(entries)} 篇文章（源状态: {status}）")
    print("=" * 46)
    all_ok = True
    for w in WORDS:
        cnt = sum(1 for e in entries if hit(f"{e['title']}. {e['summary']}", w))
        mark = "✓" if cnt > 0 else "✗ 需排查"
        if cnt == 0:
            all_ok = False
        print(f"{w:12s} -> {cnt:3d} 篇  {mark}")
    print("=" * 46)
    print("全部有命中" if all_ok else "有 0 命中的词，需排查")


if __name__ == "__main__":
    asyncio.run(main())
