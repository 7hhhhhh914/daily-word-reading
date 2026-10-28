// 单词语境查询：手动输入单词 + 可选主题 → 检索真实新闻里的用法
let newsWords = [];
let newsTopic = "";

function highlightSentence(sentence, matched) {
  const safe = escapeHtml(sentence);
  const re = new RegExp("(" + escapeRegex(escapeHtml(matched)) + ")", "gi");
  return safe.replace(re, "<mark>$1</mark>");
}
function shortDate(pub) {
  const m = /(\d{1,2} [A-Za-z]{3} \d{4})/.exec(pub || "");
  return m ? m[1] : (pub || "");
}

function renderNewsTags() {
  const box = document.getElementById("newsTags");
  box.innerHTML = newsWords.map((w, i) => `<span class="chip word-tag active">${escapeHtml(w)}<span class="tag-x" data-i="${i}">${icon("x", 11)}</span></span>`).join("");
  box.querySelectorAll(".tag-x").forEach((el) => {
    el.addEventListener("click", () => { newsWords.splice(parseInt(el.dataset.i, 10), 1); renderNewsTags(); });
  });
}
function addNewsWord(w) {
  w = (w || "").trim().toLowerCase().replace(/[^a-z' -]/g, "");
  if (w && !newsWords.includes(w)) { newsWords.push(w); renderNewsTags(); }
}

function renderNews(data) {
  const box = document.getElementById("newsResults");
  if (!data.results.length) {
    box.innerHTML = '<p class="status">' + escapeHtml(data.note || "没找到包含该单词的新闻，建议换词或放宽主题") + '</p>';
    return;
  }
  box.innerHTML = data.results.map((item) => {
    const meta = [item.source, shortDate(item.published)].filter(Boolean).join(" · ");
    const matches = item.matches.map((m) => {
      const lines = (m.sentences || []).map((s) => `<div class="match-line">${highlightSentence(s.text, s.matched)}</div>`).join("");
      return `<div class="match-block"><span class="match-word hit-word" data-word="${escapeHtml(m.word)}">${escapeHtml(m.word)}</span>${lines}</div>`;
    }).join("");
    return `
      <div class="news-item">
        <a class="title" href="${escapeHtml(item.link)}" target="_blank" rel="noopener">${escapeHtml(item.title)}</a>
        <div class="news-meta">${escapeHtml(meta)} · 命中 ${item.hit_count} 个词</div>
        ${matches}
      </div>`;
  }).join("");
  box.querySelectorAll(".hit-word").forEach((el) => {
    el.addEventListener("click", async () => {
      currentWord = el.dataset.word;
      document.getElementById("wpActions").classList.add("hidden");  // 新闻查词只看释义，不标记
      await lookupWord(el.dataset.word);
    });
  });
}

function initNews() {
  const input = document.getElementById("newsWordInput");
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === ",") { e.preventDefault(); addNewsWord(input.value); input.value = ""; }
  });
  input.addEventListener("blur", () => { addNewsWord(input.value); input.value = ""; });

  const topicChips = document.getElementById("newsTopicChips");
  const topicInput = document.getElementById("newsTopicInput");
  topicChips.querySelectorAll(".chip").forEach((c) => c.addEventListener("click", () => {
    topicChips.querySelectorAll(".chip").forEach((x) => x.classList.remove("active"));
    c.classList.add("active");
    topicInput.value = "";
    newsTopic = c.dataset.topic === "不限" ? "" : c.dataset.topic;
  }));
  topicInput.addEventListener("input", () => {
    topicChips.querySelectorAll(".chip").forEach((x) => x.classList.remove("active"));
    newsTopic = topicInput.value.trim();
  });

  const btn = document.getElementById("newsSearchBtn");
  const status = document.getElementById("newsStatus");
  btn.addEventListener("click", async () => {
    addNewsWord(document.getElementById("newsWordInput").value);
    if (!newsWords.length) { alert("请至少输入一个单词"); return; }
    btn.disabled = true;
    status.classList.remove("hidden", "error");
    status.textContent = "正在检索新闻…";
    document.getElementById("newsResults").innerHTML = "";
    try {
      const data = await api("/api/news/search", { method: "POST", body: { topic: newsTopic, words: newsWords } });
      if (data.note) { status.textContent = data.note; status.classList.remove("hidden"); }
      else status.classList.add("hidden");
      renderNews(data);
    } catch (err) {
      status.textContent = "出错：" + err.message;
      status.classList.add("error");
    } finally { btn.disabled = false; }
  });
}
