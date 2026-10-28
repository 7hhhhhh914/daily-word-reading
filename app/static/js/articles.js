// 页面3：文章要求 + 页面4：阅读文章
let articleState = { duration: 5, target: "四级", topic: "" };
let knownCount = 0, unknownCount = 0;
let currentArticleId = null;
let currentWord = null;
let translateOn = false;

function initSetup() {
  const durChips = document.getElementById("durationChips");
  const durCustom = document.getElementById("durationCustom");
  durChips.querySelectorAll(".chip").forEach((c) => c.addEventListener("click", () => {
    durChips.querySelectorAll(".chip").forEach((x) => x.classList.remove("active"));
    c.classList.add("active");
    durCustom.classList.toggle("hidden", c.dataset.dur !== "custom");
    if (c.dataset.dur !== "custom") articleState.duration = parseInt(c.dataset.dur, 10);
  }));
  durCustom.addEventListener("input", () => { articleState.duration = parseInt(durCustom.value, 10) || 5; });

  const targetChips = document.getElementById("targetChips");
  targetChips.querySelectorAll(".chip").forEach((c) => c.addEventListener("click", () => {
    targetChips.querySelectorAll(".chip").forEach((x) => x.classList.remove("active"));
    c.classList.add("active");
    articleState.target = c.dataset.target;
  }));

  const topicChips = document.getElementById("topicChips");
  const topicInput = document.getElementById("topicInput");
  topicChips.querySelectorAll(".chip").forEach((c) => c.addEventListener("click", () => {
    topicChips.querySelectorAll(".chip").forEach((x) => x.classList.remove("active"));
    c.classList.add("active");
    topicInput.value = "";
    articleState.topic = c.dataset.topic;
  }));
  topicInput.addEventListener("input", () => {
    topicChips.querySelectorAll(".chip").forEach((x) => x.classList.remove("active"));
    articleState.topic = topicInput.value.trim();
  });

  document.getElementById("generateBtn").addEventListener("click", () => {
    if (!articleState.topic) articleState.topic = "K-pop";
    showView("article");
    generateArticle();
  });
}

async function loadSetupWords() {
  const box = document.getElementById("setupWords");
  try {
    const data = await api("/api/words");
    if (!data.words.length) { box.innerHTML = '<span class="hint">今天还没录入单词，返回上一步添加</span>'; return; }
    const tags = data.words.map((w) => `<span class="tag">${escapeHtml(w.word)}</span>`).join("");
    box.innerHTML = `将用今日 ${data.words.length} 个单词：${tags}`;
  } catch (e) { box.innerHTML = ""; }
}

async function generateArticle() {
  const status = document.getElementById("articleStatus");
  status.classList.remove("hidden", "error");
  status.textContent = "正在检索今日新闻并生成文章…（约十几秒）";
  document.getElementById("articleResult").innerHTML = "";
  document.getElementById("articleFooter").classList.add("hidden");
  document.getElementById("articleEndButtons").classList.add("hidden");
  document.getElementById("articleToolbar").classList.add("hidden");
  try {
    // 第2步确认的单词（pendingWords）直接传给生成，不再依赖后端「按今天日期取词」
    const words = (typeof pendingWords !== "undefined" && pendingWords.length)
      ? pendingWords.map((w) => w.word).filter(Boolean)
      : [];
    const data = await api("/api/articles/generate", {
      method: "POST",
      body: { topic: articleState.topic, duration_min: articleState.duration, target: articleState.target, words },
      timeout: 180000,   // 生成文章较久，给足 3 分钟
    });
    status.classList.add("hidden");
    renderArticle(data);
  } catch (err) {
    status.textContent = "生成失败：" + err.message;
    status.classList.add("error");
  }
}

function renderSegments(segs) {
  return segs.map((s) => {
    if (s.type === "text") return escapeHtml(s.text);
    const cls = s.type === "target" ? "aw target" : "aw hard";
    return `<span class="${cls}" data-word="${escapeHtml(s.word)}">${escapeHtml(s.word)}</span>`;
  }).join("");
}

function renderArticle(data) {
  knownCount = 0; unknownCount = 0; translateOn = false;
  currentArticleId = data.article_id || null;
  const box = document.getElementById("articleResult");
  const paras = data.paragraphs.map((segs, i) => {
    const en = `<p>${renderSegments(segs)}</p>`;
    const zh = (data.translations && data.translations[i]) ? `<p class="trans hidden">${escapeHtml(data.translations[i])}</p>` : "";
    return en + zh;
  }).join("");
  const unused = data.unused_words && data.unused_words.length
    ? `<p class="status">未融入文章的单词：${data.unused_words.map(escapeHtml).join("、")}</p>` : "";
  const sourcesHtml = (data.sources && data.sources.length)
    ? `<div class="sources"><h3>来源</h3>${data.sources.map((s) => `<div class="src"><a href="${escapeHtml(s.link)}" target="_blank" rel="noopener">${escapeHtml(s.title)}</a><span class="src-meta">${escapeHtml(s.source)} · ${escapeHtml(shortDate(s.published))}</span></div>`).join("")}</div>`
    : "";
  const noFacts = data.no_facts ? `<p class="status">未找到近期报道，请换一个主题试试。</p>` : "";
  box.innerHTML = `
    <h2 class="article-title">${escapeHtml(data.title)}</h2>
    <div class="article-meta">${articleState.duration} 分钟 · 本次新词 ${data.target_words.length} 个 · 点高亮词查看并标记</div>
    <div class="article-body">${paras}</div>${unused}${sourcesHtml}${noFacts}`;
  document.getElementById("articleFooter").classList.remove("hidden");
  document.getElementById("articleEndButtons").classList.remove("hidden");
  document.getElementById("articleToolbar").classList.remove("hidden");
  document.getElementById("translateToggle").textContent = "全文翻译";
  document.getElementById("knownCount").textContent = "0";
  document.getElementById("unknownCount").textContent = "0";
}

function getWordAtPoint(x, y) {
  let range = null;
  if (document.caretRangeFromPoint) range = document.caretRangeFromPoint(x, y);
  else if (document.caretPositionFromPoint) {
    const pos = document.caretPositionFromPoint(x, y);
    if (pos) { range = document.createRange(); range.setStart(pos.offsetNode, pos.offset); range.setEnd(pos.offsetNode, pos.offset); }
  }
  if (!range || range.startContainer.nodeType !== Node.TEXT_NODE) return null;
  const text = range.startContainer.textContent;
  let start = range.startOffset, end = range.endOffset;
  while (start > 0 && /[a-zA-Z'’-]/.test(text[start - 1])) start--;
  while (end < text.length && /[a-zA-Z'’-]/.test(text[end])) end++;
  const word = text.slice(start, end);
  return /^[a-zA-Z][a-zA-Z'’-]*$/.test(word) ? word.toLowerCase() : null;
}

async function lookupWord(word) {
  document.getElementById("wpWord").textContent = word;
  document.getElementById("wpPhonetic").textContent = "";
  document.getElementById("wpMeanings").innerHTML = "查询中…";
  document.getElementById("wpMeaningEn").textContent = "";
  document.getElementById("wpExample").textContent = "";
  document.getElementById("wpCollocations").textContent = "";
  document.getElementById("wordPopup").classList.remove("hidden");
  try {
    const d = await api("/api/lookup?word=" + encodeURIComponent(word));
    document.getElementById("wpPhonetic").textContent = d.phonetic || "";
    const meanings = d.meanings || [{ pos: d.pos, meaning: d.meaning_cn }];
    const note = d.note ? `<div class="m-line note-line">我的释义：${escapeHtml(d.note)}</div>` : "";
    document.getElementById("wpMeanings").innerHTML = note + meanings
      .map((m) => `<div class="m-line">${escapeHtml(m.pos ? m.pos + " " : "")}${escapeHtml(m.meaning || "")}</div>`).join("");
    document.getElementById("wpMeaningEn").textContent = d.meaning_en || "";
    document.getElementById("wpExample").textContent = d.example || "";
    document.getElementById("wpCollocations").textContent = d.collocations || "";
  } catch (err) {
    document.getElementById("wpMeanings").textContent = "查词失败：" + err.message;
  }
}

function hideWordPopup() {
  document.getElementById("wordPopup").classList.add("hidden");
  currentWord = null;
}

async function markWord(word, known) {
  try {
    await api("/api/reviews", { method: "POST", body: { word, known, article_id: currentArticleId } });
    if (known) knownCount++; else unknownCount++;
    document.getElementById("knownCount").textContent = knownCount;
    document.getElementById("unknownCount").textContent = unknownCount;
    document.querySelectorAll(".aw.target").forEach((s) => {
      if (s.dataset.word === word) {
        s.classList.remove("marked-known", "marked-unknown");
        s.classList.add(known ? "marked-known" : "marked-unknown");
      }
    });
    hideWordPopup();
  } catch (err) { alert("标记失败：" + err.message); }
}

function speakWord(word) {
  if (!window.speechSynthesis) return;
  const u = new SpeechSynthesisUtterance(word);
  u.lang = "en-US";
  window.speechSynthesis.speak(u);
}

function initArticles() {
  document.getElementById("wpSpeak").addEventListener("click", () => { if (currentWord) speakWord(currentWord); });

  document.getElementById("translateToggle").addEventListener("click", () => {
    translateOn = !translateOn;
    document.querySelectorAll(".trans").forEach((p) => p.classList.toggle("hidden", !translateOn));
    document.getElementById("translateToggle").textContent = translateOn ? "收起翻译" : "全文翻译";
  });

  document.getElementById("goHomeBtn").addEventListener("click", () => goHome());
  document.getElementById("goReviewBtn").addEventListener("click", () => showView("review"));

  document.addEventListener("click", async (e) => {
    if (e.target.id === "wpKnown" || e.target.id === "wpUnknown") {
      if (currentWord) markWord(currentWord, e.target.id === "wpKnown");
      return;
    }
    const span = e.target.closest(".aw");
    let word = null, isTarget = false;
    if (span) { word = span.dataset.word; isTarget = span.classList.contains("target"); }
    else if (e.target.closest(".article-body")) word = getWordAtPoint(e.clientX, e.clientY);
    if (!word) { hideWordPopup(); return; }
    currentWord = word;
    document.getElementById("wpActions").classList.toggle("hidden", !isTarget);
    await lookupWord(word);
  });
}
