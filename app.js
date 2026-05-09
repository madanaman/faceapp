const DB_NAME = "local-face-library";
const DB_VERSION = 1;
const STORE = "files";
const VIDEO_TYPES = new Set(["video/mp4", "video/webm", "video/quicktime"]);

const state = {
  db: null,
  files: new Map(),
  filteredIds: [],
  lightboxIndex: 0,
  currentView: { type: "all", title: "All Indexed Files", hint: "Search uses AND matching for multiple names.", terms: [] },
  objectUrls: new Map(),
  support: {
    backend: false,
    backendError: "",
    engine: "",
  },
};

const els = {
  clearDbBtn: document.querySelector("#clearDbBtn"),
  supportBadge: document.querySelector("#supportBadge"),
  folderLabel: document.querySelector("#folderLabel"),
  pathInput: document.querySelector("#pathInput"),
  scanPathBtn: document.querySelector("#scanPathBtn"),
  searchInput: document.querySelector("#searchInput"),
  searchBtn: document.querySelector("#searchBtn"),
  showAllBtn: document.querySelector("#showAllBtn"),
  untaggedBtn: document.querySelector("#untaggedBtn"),
  fileCount: document.querySelector("#fileCount"),
  faceCount: document.querySelector("#faceCount"),
  tagCount: document.querySelector("#tagCount"),
  matchCount: document.querySelector("#matchCount"),
  progressText: document.querySelector("#progressText"),
  progressPercent: document.querySelector("#progressPercent"),
  scanProgress: document.querySelector("#scanProgress"),
  peopleList: document.querySelector("#peopleList"),
  gallery: document.querySelector("#gallery"),
  galleryTitle: document.querySelector("#galleryTitle"),
  galleryHint: document.querySelector("#galleryHint"),
  yearFilter: document.querySelector("#yearFilter"),
  monthFilter: document.querySelector("#monthFilter"),
  dateFilter: document.querySelector("#dateFilter"),
  sortDirection: document.querySelector("#sortDirection"),
  lightbox: document.querySelector("#lightbox"),
  lightboxImage: document.querySelector("#lightboxImage"),
  lightboxName: document.querySelector("#lightboxName"),
  lightboxMeta: document.querySelector("#lightboxMeta"),
  lightboxClose: document.querySelector("#lightboxClose"),
  lightboxPrev: document.querySelector("#lightboxPrev"),
  lightboxNext: document.querySelector("#lightboxNext"),
  photoTemplate: document.querySelector("#photoTemplate"),
  faceTemplate: document.querySelector("#faceTemplate"),
};

init();

async function init() {
  state.db = await openDb();
  await checkBackend();

  if (state.support.backend) {
    await restoreBackendIndex();
  } else {
    await restoreIndex();
  }
  bindEvents();
  setSupportBadge();
  showAll();
}

function bindEvents() {
  els.scanPathBtn.addEventListener("click", scanPath);
  els.clearDbBtn.addEventListener("click", clearIndex);
  els.searchBtn.addEventListener("click", search);
  els.showAllBtn.addEventListener("click", showAll);
  els.untaggedBtn.addEventListener("click", showUntagged);
  els.yearFilter.addEventListener("change", renderCurrentView);
  els.monthFilter.addEventListener("change", renderCurrentView);
  els.dateFilter.addEventListener("change", renderCurrentView);
  els.sortDirection.addEventListener("change", renderCurrentView);
  els.lightboxClose.addEventListener("click", closeLightbox);
  els.lightboxPrev.addEventListener("click", () => stepLightbox(-1));
  els.lightboxNext.addEventListener("click", () => stepLightbox(1));
  els.lightbox.addEventListener("click", (event) => {
    if (event.target === els.lightbox) closeLightbox();
  });
  document.addEventListener("keydown", handleLightboxKeys);
  els.searchInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") search();
  });
}

function setSupportBadge() {
  if (state.support.backend) {
    els.supportBadge.textContent = state.support.engine || "InsightEdge local engine";
    els.progressText.textContent = "Enter a local folder path and scan it with the local InsightEdge engine.";
    return;
  }

  if (state.support.backendError) {
    els.supportBadge.textContent = "InsightEdge missing";
    els.supportBadge.classList.add("warning");
    els.scanPathBtn.disabled = true;
    els.progressText.textContent = state.support.backendError;
    return;
  }

  els.supportBadge.textContent = "Start server.py";
  els.supportBadge.classList.add("warning");
  els.scanPathBtn.disabled = true;
  els.progressText.textContent = "Run `python3 server.py` to use the InsightEdge local engine.";
}

async function checkBackend() {
  try {
    const response = await fetch("/api/health");
    if (!response.ok) return;
    const payload = await response.json();
    state.support.backend = Boolean(payload.ok);
    const providers = payload.requestedProviders?.filter((provider) => payload.providers?.includes(provider)) || [];
    state.support.engine = payload.engine
      ? `${payload.engine}${providers.length ? ` (${providers.join(" + ")})` : ""}`
      : "";
    state.support.backendError = payload.ok ? "" : payload.error || "";
  } catch {
    state.support.backend = false;
  }
}

async function restoreBackendIndex() {
  const response = await fetch("/api/files");
  const records = await response.json();
  state.files.clear();
  for (const record of records) {
    state.files.set(record.id, record);
  }
  populateYearFilter();
  if (records.length) {
    els.progressText.textContent = "Saved server index restored.";
  }
}

async function scanPath() {
  const path = els.pathInput.value.trim();
  if (!path) {
    setProgress("Enter a folder path first.", 0);
    return;
  }

  setProgress("Scanning with InsightEdge. Large libraries can take a while...", 8);
  els.scanPathBtn.disabled = true;
  try {
    const response = await fetch("/api/scan", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ path }),
    });
    const payload = await response.json();
    if (!payload.ok) throw new Error(payload.error || "Scan failed.");
    state.files.clear();
    for (const record of payload.files) {
      state.files.set(record.id, record);
    }
    populateYearFilter();
    els.folderLabel.textContent = path;
    const autoTagged = payload.autoTagged ? ` ${payload.autoTagged} faces auto-tagged.` : "";
    const warningText = payload.warnings?.length ? ` ${payload.warnings.length} files warned/skipped.` : "";
    setProgress(`Scan complete: ${payload.files.length} image files indexed.${autoTagged}${warningText}`, 100);
    showAll();
  } catch (error) {
    setProgress(error.message, 0);
  } finally {
    els.scanPathBtn.disabled = false;
  }
}

function squareCrop(box, width, height) {
  const size = Math.min(Math.max(box.width, box.height), width, height);
  const x = clamp(box.x + box.width / 2 - size / 2, 0, width - size);
  const y = clamp(box.y + box.height / 2 - size / 2, 0, height - size);
  return { x, y, size };
}

function renderGallery(ids, title = "Matches", hint = "Search uses AND matching for multiple names.") {
  state.filteredIds = ids;
  els.galleryTitle.textContent = title;
  els.galleryHint.textContent = hint;
  els.matchCount.textContent = ids.length;
  els.gallery.replaceChildren();

  if (!ids.length) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = state.files.size
      ? "No matching photos yet."
      : "Choose a folder to build your local face index.";
    els.gallery.append(empty);
    updateStats();
    return;
  }

  for (const id of ids) {
    const fileRecord = state.files.get(id);
    if (!fileRecord) continue;
    els.gallery.append(renderPhoto(fileRecord));
  }

  updateStats();
}

function renderCurrentView({ preserveScroll = false } = {}) {
  const scrollY = window.scrollY;
  if (state.currentView.type === "untagged") {
    showUntagged();
  } else if (state.currentView.type === "search") {
    search();
  } else {
    applyGalleryFilters();
  }
  if (preserveScroll) {
    requestAnimationFrame(() => window.scrollTo({ top: scrollY }));
  }
}

function renderPhoto(fileRecord) {
  const fragment = els.photoTemplate.content.cloneNode(true);
  const card = fragment.querySelector(".photo-card");
  const mediaWrap = fragment.querySelector(".media-wrap");
  const name = fragment.querySelector(".file-name");
  const path = fragment.querySelector(".file-path");
  const faces = fragment.querySelector(".faces");
  const rescanButton = fragment.querySelector(".rescan-photo");
  const resetIgnoredButton = fragment.querySelector(".reset-ignored");

  name.textContent = fileRecord.name;
  path.textContent = fileRecord.path;
  if (rescanButton) {
    rescanButton.addEventListener("click", () => rescanPhoto(fileRecord, false, rescanButton));
  }
  if (resetIgnoredButton) {
    resetIgnoredButton.addEventListener("click", () => {
      if (!confirm("Bring back ignored faces for this photo and rescan it?")) return;
      rescanPhoto(fileRecord, true, resetIgnoredButton);
    });
  }
  mediaWrap.style.aspectRatio = `${fileRecord.width || 4} / ${fileRecord.height || 3}`;

  const media = createMediaElement(fileRecord);
  mediaWrap.append(media);
  mediaWrap.addEventListener("click", () => openLightbox(fileRecord.id));

  for (const face of sortedFaces(fileRecord.faces)) {
    mediaWrap.append(renderFaceBox(face, fileRecord));
    faces.append(renderFaceEditor(fileRecord, face));
  }

  if (!fileRecord.faces.length) {
    const empty = document.createElement("p");
    empty.className = "file-path";
    empty.textContent = "No faces detected in this file.";
    faces.append(empty);
  }

  return card;
}

function sortedFaces(faces) {
  return [...faces].sort((a, b) => {
    const aTag = normalizeName(a.tag);
    const bTag = normalizeName(b.tag);
    if (aTag && !bTag) return -1;
    if (!aTag && bTag) return 1;
    if (aTag || bTag) return aTag.localeCompare(bTag);
    return a.id.localeCompare(b.id);
  });
}

function createMediaElement(fileRecord) {
  const url = getObjectUrl(fileRecord);
  if (VIDEO_TYPES.has(fileRecord.type)) {
    const video = document.createElement("video");
    video.src = url;
    video.controls = true;
    video.preload = "metadata";
    return video;
  }

  const img = document.createElement("img");
  img.src = url;
  img.alt = fileRecord.name;
  return img;
}

function getObjectUrl(fileRecord) {
  if (state.support.backend) {
    return `/api/media?path=${encodeURIComponent(fileRecord.path)}`;
  }

  if (!fileRecord.file) {
    return "";
  }

  if (!state.objectUrls.has(fileRecord.id)) {
    state.objectUrls.set(fileRecord.id, URL.createObjectURL(fileRecord.file));
  }
  return state.objectUrls.get(fileRecord.id);
}

function renderFaceBox(face, fileRecord) {
  const box = document.createElement("span");
  box.className = "face-box";
  box.title = face.tag || "Untagged face";
  box.style.left = `${(face.box.x / fileRecord.width) * 100}%`;
  box.style.top = `${(face.box.y / fileRecord.height) * 100}%`;
  box.style.width = `${(face.box.width / fileRecord.width) * 100}%`;
  box.style.height = `${(face.box.height / fileRecord.height) * 100}%`;
  return box;
}

function renderFaceEditor(fileRecord, face) {
  const fragment = els.faceTemplate.content.cloneNode(true);
  const chip = fragment.querySelector(".face-chip");
  const canvas = fragment.querySelector("canvas");
  const input = fragment.querySelector("input");
  let removeButton = fragment.querySelector(".remove-face");
  const image = new Image();

  if (!removeButton) {
    removeButton = document.createElement("button");
    removeButton.className = "remove-face";
    removeButton.type = "button";
    removeButton.setAttribute("aria-label", "Ignore this face");
    removeButton.title = "Ignore this face";
    removeButton.textContent = "−";
    chip.append(removeButton);
  }
  removeButton.textContent = "−";

  input.value = face.tag || "";
  input.addEventListener("change", async () => {
    face.tag = input.value.trim();
    face.__changed = true;
    await saveFile(fileRecord);
    updateStats();
    renderPeople();
  });

  image.onload = () => drawFaceCrop(canvas, image, face, fileRecord);
  image.src = face.thumbnail || getObjectUrl(fileRecord);
  removeButton.addEventListener("click", async () => {
    if (face.tag && !confirm(`Ignore this face tagged as "${face.tag}"?`)) {
      return;
    }
    removeButton.disabled = true;
    try {
      await ignoreFace(fileRecord, face);
    } catch (error) {
      setProgress(error.message, 0);
      removeButton.disabled = false;
    }
  });

  return chip;
}

function drawFaceCrop(canvas, image, face, fileRecord) {
  const context = canvas.getContext("2d");
  context.clearRect(0, 0, canvas.width, canvas.height);
  if (!face.box || !fileRecord.width || !fileRecord.height) {
    context.drawImage(image, 0, 0, canvas.width, canvas.height);
    return;
  }

  const square = squareCrop(face.box, fileRecord.width, fileRecord.height);
  context.drawImage(
    image,
    square.x,
    square.y,
    square.size,
    square.size,
    0,
    0,
    canvas.width,
    canvas.height,
  );
}

function search() {
  const terms = parseSearch(els.searchInput.value);
  state.currentView = {
    type: terms.length ? "search" : "all",
    title: terms.length ? `Search: ${terms.join(" + ")}` : "All Indexed Files",
    hint: terms.length
      ? "Multiple names require every person to appear in the same file."
      : "Search uses AND matching for multiple names.",
    terms,
  };
  applyGalleryFilters();
}

function applyGalleryFilters() {
  const terms = state.currentView.terms || [];
  const ids = [...state.files.values()]
    .filter((fileRecord) => matchesPeople(fileRecord, terms))
    .filter(matchesDateFilters)
    .sort(comparePhotos)
    .map((fileRecord) => fileRecord.id);

  renderGallery(ids, state.currentView.title, state.currentView.hint);
}

function showAll() {
  els.searchInput.value = "";
  els.yearFilter.value = "";
  els.monthFilter.value = "";
  els.dateFilter.value = "";
  state.currentView = { type: "all", title: "All Indexed Files", hint: "Search uses AND matching for multiple names.", terms: [] };
  applyGalleryFilters();
}

function showUntagged() {
  state.currentView = {
    type: "untagged",
    title: "Untagged Faces",
    hint: "Tag the cropped faces, then search by one name or several names.",
    terms: [],
  };
  const ids = [...state.files.values()]
    .filter((fileRecord) => fileRecord.faces.some((face) => !normalizeName(face.tag)))
    .filter(matchesDateFilters)
    .sort(comparePhotos)
    .map((fileRecord) => fileRecord.id);
  renderGallery(ids, state.currentView.title, state.currentView.hint);
}

function matchesPeople(fileRecord, terms) {
  if (!terms.length) return true;
  const tags = new Set(fileRecord.faces.map((face) => normalizeName(face.tag)).filter(Boolean));
  return terms.every((term) => tags.has(term));
}

function matchesDateFilters(fileRecord) {
  const taken = photoTakenDate(fileRecord);
  const exactDate = els.dateFilter.value;
  const year = els.yearFilter.value;
  const month = els.monthFilter.value;
  if (exactDate) return taken?.slice(0, 10) === exactDate;
  if (year && taken?.slice(0, 4) !== year) return false;
  if (month && taken?.slice(5, 7) !== month) return false;
  return true;
}

function comparePhotos(a, b) {
  const direction = els.sortDirection.value === "asc" ? 1 : -1;
  const aKey = photoSortKey(a);
  const bKey = photoSortKey(b);
  if (aKey === bKey) return a.name.localeCompare(b.name);
  return aKey > bKey ? direction : -direction;
}

function photoSortKey(fileRecord) {
  return photoTakenDate(fileRecord) || fileRecord.name || "";
}

function photoTakenDate(fileRecord) {
  return fileRecord.metadata?.taken_at || "";
}

function populateYearFilter() {
  const current = els.yearFilter.value;
  const years = [...new Set([...state.files.values()]
    .map((fileRecord) => photoTakenDate(fileRecord)?.slice(0, 4))
    .filter(Boolean))]
    .sort((a, b) => b.localeCompare(a));
  els.yearFilter.replaceChildren(new Option("Any", ""));
  for (const year of years) {
    els.yearFilter.append(new Option(year, year));
  }
  if (years.includes(current)) {
    els.yearFilter.value = current;
  }
}

function parseSearch(value) {
  const raw = value.includes(",") ? value.split(",") : value.split(/\s+/);
  return raw.map(normalizeName).filter(Boolean);
}

function renderPeople() {
  const counts = new Map();
  for (const fileRecord of state.files.values()) {
    for (const face of fileRecord.faces) {
      const tag = face.tag?.trim();
      if (!tag) continue;
      counts.set(tag, (counts.get(tag) || 0) + 1);
    }
  }

  els.peopleList.replaceChildren();
  if (!counts.size) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "No people tagged yet.";
    els.peopleList.append(empty);
    return;
  }

  [...counts.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .forEach(([person, count]) => {
      const button = document.createElement("button");
      button.className = "person-button";
      button.innerHTML = `<strong></strong><span></span>`;
      button.querySelector("strong").textContent = person;
      button.querySelector("span").textContent = count;
      button.addEventListener("click", () => {
        els.searchInput.value = person;
        search();
      });
      els.peopleList.append(button);
    });
}

function updateStats() {
  const files = [...state.files.values()];
  const faces = files.flatMap((fileRecord) => fileRecord.faces);
  const tags = new Set(faces.map((face) => normalizeName(face.tag)).filter(Boolean));
  els.fileCount.textContent = files.length;
  els.faceCount.textContent = faces.length;
  els.tagCount.textContent = tags.size;
  renderPeople();
}

function setProgress(text, percent) {
  els.progressText.textContent = text;
  els.progressPercent.textContent = `${percent}%`;
  els.scanProgress.value = percent;
}

async function openDb() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      request.result.createObjectStore(STORE, { keyPath: "id" });
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function restoreIndex() {
  const files = await getAllFiles();
  for (const fileRecord of files) {
    state.files.set(fileRecord.id, fileRecord);
  }
  populateYearFilter();
  if (files.length) {
    els.progressText.textContent = "Saved tag index restored. Choose the same folder to display local files.";
  }
}

async function getAllFiles() {
  return new Promise((resolve, reject) => {
    const transaction = state.db.transaction(STORE, "readonly");
    const request = transaction.objectStore(STORE).getAll();
    request.onsuccess = () => resolve(request.result || []);
    request.onerror = () => reject(request.error);
  });
}

async function saveFile(fileRecord) {
  if (state.support.backend) {
    const changed = fileRecord.faces.find((face) => face.__changed);
    if (changed) {
      delete changed.__changed;
      const response = await fetch("/api/tag", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ fileId: fileRecord.id, faceId: changed.id, tag: changed.tag }),
      });
      const payload = await response.json();
      if (payload.files) {
        state.files.clear();
        for (const record of payload.files) {
          state.files.set(record.id, record);
        }
        populateYearFilter();
        if (payload.propagated) {
          setProgress(`Tagged ${payload.propagated + 1} matching faces.`, 100);
        }
        renderCurrentView({ preserveScroll: true });
      }
    }
    return;
  }

  const serializable = {
    id: fileRecord.id,
    name: fileRecord.name,
    path: fileRecord.path,
    type: fileRecord.type,
    signature: fileRecord.signature,
    width: fileRecord.width,
    height: fileRecord.height,
    faces: fileRecord.faces,
  };

  return new Promise((resolve, reject) => {
    const transaction = state.db.transaction(STORE, "readwrite");
    const request = transaction.objectStore(STORE).put(serializable);
    request.onsuccess = () => resolve();
    request.onerror = () => reject(request.error);
  });
}

async function clearIndex() {
  if (!confirm("Clear saved face boxes and tags from this browser?")) return;
  if (state.support.backend) {
    await fetch("/api/clear", { method: "POST" });
  }
  return new Promise((resolve, reject) => {
    const transaction = state.db.transaction(STORE, "readwrite");
    const request = transaction.objectStore(STORE).clear();
    request.onsuccess = () => {
      for (const url of state.objectUrls.values()) URL.revokeObjectURL(url);
      state.objectUrls.clear();
      state.files.clear();
      els.folderLabel.textContent = "No folder selected";
      setProgress("Index cleared.", 0);
      showAll();
      resolve();
    };
    request.onerror = () => reject(request.error);
  });
}

async function ignoreFace(fileRecord, face) {
  if (!state.support.backend) {
    fileRecord.faces = fileRecord.faces.filter((candidate) => candidate.id !== face.id);
    await saveFile(fileRecord);
    renderCurrentView({ preserveScroll: true });
    return;
  }

  const response = await fetch("/api/ignore-face", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ fileId: fileRecord.id, faceId: face.id }),
  });
  const payload = await response.json();
  if (!payload.ok) throw new Error(payload.error || "Could not remove face.");

  state.files.clear();
  for (const record of payload.files) {
    state.files.set(record.id, record);
  }
  populateYearFilter();
  setProgress("Face removed and will be ignored on future scans.", 100);
  renderCurrentView({ preserveScroll: true });
}

async function rescanPhoto(fileRecord, resetIgnored, button) {
  if (!state.support.backend) return;
  button.disabled = true;
  try {
    const response = await fetch(resetIgnored ? "/api/reset-ignored-faces" : "/api/rescan-photo", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ fileId: fileRecord.id }),
    });
    const payload = await response.json();
    if (!payload.ok) throw new Error(payload.error || "Could not rescan photo.");

    state.files.clear();
    for (const record of payload.files) {
      state.files.set(record.id, record);
    }
    populateYearFilter();
    const autoTagged = payload.autoTagged ? ` ${payload.autoTagged} faces auto-tagged.` : "";
    setProgress(`${resetIgnored ? "Ignored faces reset and photo rescanned." : "Photo rescanned."}${autoTagged}`, 100);
    renderCurrentView({ preserveScroll: true });
  } catch (error) {
    setProgress(error.message, 0);
  } finally {
    button.disabled = false;
  }
}

function openLightbox(fileId) {
  const index = state.filteredIds.indexOf(fileId);
  if (index < 0) return;
  state.lightboxIndex = index;
  renderLightbox();
  els.lightbox.hidden = false;
}

function closeLightbox() {
  els.lightbox.hidden = true;
}

function stepLightbox(delta) {
  if (!state.filteredIds.length) return;
  state.lightboxIndex = (state.lightboxIndex + delta + state.filteredIds.length) % state.filteredIds.length;
  renderLightbox();
}

function renderLightbox() {
  const fileRecord = state.files.get(state.filteredIds[state.lightboxIndex]);
  if (!fileRecord) return;
  els.lightboxImage.src = getObjectUrl(fileRecord);
  els.lightboxImage.alt = fileRecord.name;
  els.lightboxName.textContent = fileRecord.name;
  const people = [...new Set(fileRecord.faces.map((face) => face.tag).filter(Boolean))].sort();
  const date = photoTakenDate(fileRecord)?.slice(0, 10) || "Date unknown";
  els.lightboxMeta.textContent = `${date}${people.length ? ` · ${people.join(", ")}` : ""}`;
}

function handleLightboxKeys(event) {
  if (els.lightbox.hidden) return;
  if (event.key === "Escape") closeLightbox();
  if (event.key === "ArrowLeft") stepLightbox(-1);
  if (event.key === "ArrowRight") stepLightbox(1);
}

function normalizeName(name = "") {
  return name.trim().toLocaleLowerCase();
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}
