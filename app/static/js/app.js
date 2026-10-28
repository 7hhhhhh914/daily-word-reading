// 导航 + 步骤指示 + 主题 + 首页按钮
const WIZARD = ["upload", "confirm", "setup", "article"];
const VIEWS = ["home", "upload", "confirm", "setup", "article", "news", "review"];
const BACK_TO = { upload: "home", confirm: "upload", setup: "confirm", article: "setup", news: "home", review: "home" };
const TITLES = { home: "每日单词阅读", upload: "上传截图", confirm: "确认单词", setup: "文章要求", article: "阅读文章", news: "单词语境查询", review: "错题本" };
let currentView = "home";

function showView(name) {
  currentView = name;
  VIEWS.forEach((v) => document.getElementById("view-" + v).classList.toggle("hidden", v !== name));
  document.getElementById("pageTitle").textContent = TITLES[name] || "每日单词阅读";
  document.getElementById("backBtn").classList.toggle("hidden", name === "home");
  document.getElementById("homeBtn").classList.toggle("hidden", name === "home");

  const stepIdx = WIZARD.indexOf(name);
  document.getElementById("stepsBar").classList.toggle("hidden", stepIdx === -1);
  if (stepIdx >= 0) {
    document.querySelectorAll(".step").forEach((el) => {
      const i = parseInt(el.dataset.step, 10);
      el.classList.toggle("active", i === stepIdx);
      el.classList.toggle("done", i < stepIdx);
    });
  }

  if (name === "confirm") renderConfirmWords();
  if (name === "setup") loadSetupWords();
  if (name === "review") loadWrongbook();
}

function isInProgress() {
  if (currentView === "upload" && typeof uploadFiles !== "undefined" && uploadFiles.length) return true;
  if (currentView === "confirm" && typeof pendingWords !== "undefined" && pendingWords.length) return true;
  if (currentView === "article") {
    const el = document.getElementById("articleResult");
    if (el && el.innerHTML.trim()) return true;
  }
  return false;
}

function goHome() {
  if (isInProgress() && !confirm("离开后当前内容将不会保留，确定返回首页吗？")) return;
  showView("home");
}

function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  document.getElementById("themeToggle").innerHTML = theme === "dark"
    ? '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/></svg>'
    : '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/></svg>';
}

function initTheme() {
  const saved = localStorage.getItem("theme");
  const theme = saved || (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  applyTheme(theme);
  document.getElementById("themeToggle").addEventListener("click", () => {
    const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
    localStorage.setItem("theme", next);
    applyTheme(next);
  });
}

function initNav() {
  document.querySelectorAll(".card").forEach((card) => {
    card.addEventListener("click", () => showView(card.dataset.view));
  });
  document.getElementById("backBtn").addEventListener("click", () => showView(BACK_TO[currentView] || "home"));
  document.getElementById("homeBtn").addEventListener("click", goHome);
}

[initTheme, initNav, initUpload, initConfirm, initSetup, initArticles, initReview, initNews].forEach((fn) => {
  try { if (typeof fn === "function") fn(); } catch (e) { console.error("初始化失败：", e); }
});
showView("home");
