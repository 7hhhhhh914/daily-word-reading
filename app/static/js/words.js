// 页面1：上传截图 + 页面2：确认单词
let pendingWords = [];   // 识别出的单词 [{word, phonetic, meanings:[{pos,meaning}], inferred}]
let uploadFiles = [];    // 选中的图片文件
const IMG_TYPES = ["image/jpeg", "image/png", "image/webp"];
const MAX_SIZE = 10 * 1024 * 1024;   // 10MB

// 压缩图片：长边超过 maxDim 时用 canvas 缩到 maxDim，输出 jpeg，加快识图
function compressImage(file, maxDim = 1280) {
  return new Promise((resolve) => {
    const img = new Image();
    const url = URL.createObjectURL(file);
    img.onload = () => {
      const w = img.width, h = img.height;
      if (Math.max(w, h) <= maxDim) { URL.revokeObjectURL(url); resolve(file); return; }
      const scale = maxDim / Math.max(w, h);
      const cw = Math.round(w * scale), ch = Math.round(h * scale);
      const canvas = document.createElement("canvas");
      canvas.width = cw; canvas.height = ch;
      canvas.getContext("2d").drawImage(img, 0, 0, cw, ch);
      URL.revokeObjectURL(url);
      canvas.toBlob((blob) => resolve(new File([blob], file.name, { type: "image/jpeg" })), "image/jpeg", 0.85);
    };
    img.onerror = () => { URL.revokeObjectURL(url); resolve(file); };
    img.src = url;
  });
}

// ---- 页面1：上传 ----
function initUpload() {
  const dropZone = document.getElementById("dropZone");
  const input = document.getElementById("shotInput");
  const recognizeBtn = document.getElementById("recognizeBtn");

  function showUploadMsg(msg, isError) {
    const el = document.getElementById("uploadStatus");
    el.textContent = msg;
    el.classList.toggle("error", !!isError);
    el.classList.remove("hidden");
  }

  async function addFiles(files) {
    for (const f of files) {
      if (!IMG_TYPES.includes(f.type)) { showUploadMsg(`不支持的格式：${f.name || "未知文件"}（仅支持 jpg / png / webp）`, true); continue; }
      if (f.size > MAX_SIZE) { showUploadMsg(`图片过大：${f.name}（请控制在 10MB 以内）`, true); continue; }
      showUploadMsg("正在压缩图片…", false);
      const compressed = await compressImage(f);
      uploadFiles.push(compressed);
      showUploadMsg("", false);
    }
    renderThumbs();
  }

  input.addEventListener("change", async () => { await addFiles(input.files); input.value = ""; });
  dropZone.addEventListener("dragover", (e) => { e.preventDefault(); dropZone.classList.add("dragover"); });
  dropZone.addEventListener("dragleave", () => dropZone.classList.remove("dragover"));
  dropZone.addEventListener("drop", (e) => { e.preventDefault(); dropZone.classList.remove("dragover"); addFiles(e.dataTransfer.files); });

  recognizeBtn.addEventListener("click", async () => {
    if (!uploadFiles.length) return;
    const status = document.getElementById("uploadStatus");
    recognizeBtn.disabled = true;
    status.classList.remove("hidden", "error");
    status.textContent = "正在识别…（可多张，请稍候）";
    try {
      const form = new FormData();
      uploadFiles.forEach((f) => form.append("files", f));
      const resp = await fetch("/api/words/recognize", { method: "POST", body: form });
      if (!resp.ok) throw new Error((await resp.json()).detail || "识别失败");
      const data = await resp.json();
      status.classList.add("hidden");
      pendingWords = (data.words || []).map((w) => ({ word: w.word, phonetic: w.phonetic || "", meanings: w.meanings || [], inferred: w.inferred || [] }));
      if (!pendingWords.length) { alert("没识别出单词，请换更清晰的截图"); return; }
      showView("confirm");
    } catch (err) {
      status.textContent = "识别失败：" + err.message;
      status.classList.add("error");
    } finally { recognizeBtn.disabled = false; }
  });
}

function renderThumbs() {
  const box = document.getElementById("thumbList");
  document.getElementById("recognizeBtn").disabled = uploadFiles.length === 0;
  box.innerHTML = uploadFiles.map((f, i) => `
    <div class="thumb"><img src="${URL.createObjectURL(f)}" alt=""><span class="rm" data-i="${i}">${icon("x", 12)}</span></div>`).join("");
  box.querySelectorAll(".rm").forEach((el) => {
    el.addEventListener("click", () => { uploadFiles.splice(parseInt(el.dataset.i, 10), 1); renderThumbs(); });
  });
}

// ---- 页面2：确认单词 ----
function renderConfirmWords() {
  const box = document.getElementById("confirmWords");
  if (!pendingWords.length) {
    box.innerHTML = '<p class="status">没有单词，点左上角返回重新上传</p>';
    return;
  }
  box.innerHTML = pendingWords.map((w, i) => {
    const uncertain = w.inferred && w.inferred.length;
    const meanings = (w.meanings && w.meanings.length) ? w.meanings : [{ pos: "", meaning: "" }];
    const rows = meanings.map((m, j) => `
      <div class="meaning-row">
        <input data-field="pos" data-i="${i}" data-j="${j}" value="${escapeHtml(m.pos || "")}" placeholder="词性" style="width:80px">
        <input data-field="meaning" data-i="${i}" data-j="${j}" value="${escapeHtml(m.meaning || "")}" placeholder="释义" style="flex:1">
        <button class="btn btn-outline btn-sm rm-meaning" data-i="${i}" data-j="${j}">${icon("x", 12)}</button>
      </div>`).join("");
    return `
    <div class="word-card ${uncertain ? "uncertain" : ""}">
      <div class="word-head">
        <input data-field="word" data-i="${i}" value="${escapeHtml(w.word)}" placeholder="单词">
        <input data-field="phonetic" data-i="${i}" value="${escapeHtml(w.phonetic || "")}" placeholder="音标" style="flex:1">
      </div>
      ${rows}
      <input data-field="note" data-i="${i}" value="${escapeHtml(w.note || "")}" placeholder="补充释义（可选，中文或英文）">
      ${uncertain ? `<span class="uncertain-tag">已补全 ${w.inferred.join("、")}，请重点检查</span>` : ""}
      <div class="w-actions"><button class="btn btn-outline btn-sm del-word" data-i="${i}">${icon("trash", 14)} 删除</button></div>
    </div>`;
  }).join("");

  box.querySelectorAll("input[data-field]").forEach((inp) => {
    inp.addEventListener("input", () => {
      const i = parseInt(inp.dataset.i, 10);
      const f = inp.dataset.field;
      if (f === "word" || f === "phonetic" || f === "note") { pendingWords[i][f] = inp.value.trim(); return; }
      const j = parseInt(inp.dataset.j, 10);
      if (!pendingWords[i].meanings[j]) pendingWords[i].meanings[j] = { pos: "", meaning: "" };
      pendingWords[i].meanings[j][f] = inp.value.trim();
    });
  });
  box.querySelectorAll(".rm-meaning").forEach((btn) => {
    btn.addEventListener("click", () => {
      const i = parseInt(btn.dataset.i, 10), j = parseInt(btn.dataset.j, 10);
      pendingWords[i].meanings.splice(j, 1);
      renderConfirmWords();
    });
  });
  box.querySelectorAll(".del-word").forEach((btn) => {
    btn.addEventListener("click", () => {
      pendingWords.splice(parseInt(btn.dataset.i, 10), 1);
      renderConfirmWords();
    });
  });
}

function initConfirm() {
  document.getElementById("addWordBtn").addEventListener("click", () => {
    pendingWords.push({ word: "", phonetic: "", note: "", meanings: [{ pos: "", meaning: "" }], inferred: [] });
    renderConfirmWords();
  });
  document.getElementById("confirmNext").addEventListener("click", async () => {
    const words = pendingWords
      .filter((w) => w.word && w.word.trim())
      .map((w) => ({ word: w.word.trim(), phonetic: w.phonetic, note: w.note || "", meanings: (w.meanings || []).filter((m) => m.pos || m.meaning) }));
    if (!words.length) { alert("至少保留一个单词"); return; }
    const status = document.getElementById("confirmStatus");
    status.classList.remove("hidden", "error");
    status.textContent = "正在保存…";
    try {
      await api("/api/words/save", { method: "POST", body: { words } });
      status.classList.add("hidden");
      showView("setup");
    } catch (err) {
      status.textContent = "保存失败：" + err.message;
      status.classList.add("error");
    }
  });
}
