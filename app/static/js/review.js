// 错题本
let wrongbookCache = {};

async function loadWrongbook() {
  const box = document.getElementById("wrongbookList");
  try {
    const data = await api("/api/wrongbook");
    const q = (document.getElementById("wrongbookSearch").value || "").trim().toLowerCase();
    let words = data.words || [];
    if (q) words = words.filter((w) => w.word.toLowerCase().includes(q));
    renderWrongbook(words);
  } catch (err) {
    box.innerHTML = '<p class="status error">加载失败：' + escapeHtml(err.message) + '</p>';
  }
}

function renderWrongbook(words) {
  const box = document.getElementById("wrongbookList");
  if (!words.length) {
    box.innerHTML = '<p class="status">错题本是空的，或没有匹配的单词。</p>';
    return;
  }
  box.innerHTML = words.map((w) => {
    const meanings = (w.meanings && w.meanings.length) ? w.meanings : [{ pos: w.pos, meaning: w.meaning_cn }];
    const meaningText = meanings.map((m) => `${m.pos ? m.pos + " " : ""}${m.meaning || "（无释义）"}`).join("；");
    return `
    <div class="wrongbook-item" data-word="${escapeHtml(w.word)}">
      <div class="wb-head">
        <span class="w-word">${escapeHtml(w.word)}</span>
        <span class="w-phonetic">${escapeHtml(w.phonetic || "")}</span>
        <button class="icon-btn wb-speak" data-word="${escapeHtml(w.word)}" aria-label="发音">${icon("volume", 16)}</button>
      </div>
      <div class="w-meaning">${escapeHtml(meaningText)}</div>
      <div class="wb-meta">${escapeHtml(w.source || "未知来源")} · ${escapeHtml(w.first_seen_date || "未知日期")} · 错 ${w.wrong_count || 0} 次</div>
      <div class="wb-detail hidden"></div>
      <div class="w-actions">
        <button class="btn btn-outline btn-sm wb-expand">详情</button>
        <button class="btn btn-outline btn-sm" data-master="${escapeHtml(w.word)}">已掌握</button>
        <button class="btn btn-outline btn-sm" data-del="${escapeHtml(w.word)}" title="删除">${icon("trash", 14)}</button>
      </div>
    </div>`;
  }).join("");

  box.querySelectorAll(".wb-speak").forEach((b) => b.addEventListener("click", () => speakWord(b.dataset.word)));
  box.querySelectorAll("[data-master]").forEach((b) => b.addEventListener("click", async () => {
    await api("/api/reviews", { method: "POST", body: { word: b.dataset.master, known: true } });
    loadWrongbook();
  }));
  box.querySelectorAll("[data-del]").forEach((b) => b.addEventListener("click", async () => {
    await api("/api/words/" + encodeURIComponent(b.dataset.del), { method: "DELETE" });
    loadWrongbook();
  }));
  box.querySelectorAll(".wb-expand").forEach((b) => b.addEventListener("click", async () => {
    const item = b.closest(".wrongbook-item");
    const detail = item.querySelector(".wb-detail");
    const word = item.dataset.word;
    if (detail.classList.contains("hidden")) {
      detail.classList.remove("hidden");
      if (wrongbookCache[word]) { detail.innerHTML = wrongbookCache[word]; }
      else {
        detail.innerHTML = '<span class="status">查询中…</span>';
        try {
          const d = await api("/api/lookup?word=" + encodeURIComponent(word));
          const html = `
            <div class="wb-row"><span class="k">英文释义</span>${escapeHtml(d.meaning_en || "（无）")}</div>
            <div class="wb-row"><span class="k">例句</span>${escapeHtml(d.example || "（无）")}</div>
            <div class="wb-row"><span class="k">搭配 / 词根</span>${escapeHtml(d.collocations || "（无）")}</div>`;
          wrongbookCache[word] = html;
          detail.innerHTML = html;
        } catch (err) {
          detail.innerHTML = '<span class="status error">查询失败</span>';
        }
      }
      b.textContent = "收起";
    } else {
      detail.classList.add("hidden");
      b.textContent = "详情";
    }
  }));
}

function initReview() {
  loadWrongbook();
  document.getElementById("wrongbookSearch").addEventListener("input", loadWrongbook);
  document.getElementById("clearWrongbook").addEventListener("click", async () => {
    if (!confirm("确定清空错题本吗？此操作不可撤销。")) return;
    await api("/api/wrongbook", { method: "DELETE" });
    loadWrongbook();
  });
}
