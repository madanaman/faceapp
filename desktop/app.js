const DB_NAME = "local-face-library";
const DB_VERSION = 1;
const STORE = "files";
const GALLERY_BATCH_SIZE = 50;
const ACTIVITY_LIMIT = 10;
const MIN_VIDEO_FACE_APPEARANCES = 2;
const VIDEO_TYPES = new Set(["video/mp4", "video/webm", "video/quicktime", "video/x-m4v", "video/x-msvideo"]);

const state = {
  db: null,
  files: new Map(),
  filteredIds: [],
  albums: [],
  photoTags: [],
  galleryCursor: 0,
  galleryObserver: null,
  lightboxIndex: 0,
  currentView: { type: "all", title: "All Indexed Files", hint: "Separate people, albums, and photo tags with commas. All terms must match.", terms: [] },
  activities: [],
  objectUrls: new Map(),
  backendBaseUrl: "",
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
  pickFolderBtn: document.querySelector("#pickFolderBtn"),
  scanMode: document.querySelector("#scanMode"),
  scanAlbumInput: document.querySelector("#scanAlbumInput"),
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
  albumNameInput: document.querySelector("#albumNameInput"),
  createAlbumBtn: document.querySelector("#createAlbumBtn"),
  albumList: document.querySelector("#albumList"),
  photoTagList: document.querySelector("#photoTagList"),
  activityToggle: document.querySelector("#activityToggle"),
  activityPanel: document.querySelector("#activityPanel"),
  activityClose: document.querySelector("#activityClose"),
  activityList: document.querySelector("#activityList"),
  personSuggestions: document.querySelector("#personSuggestions"),
  albumSuggestions: document.querySelector("#albumSuggestions"),
  gallery: document.querySelector("#gallery"),
  galleryTitle: document.querySelector("#galleryTitle"),
  galleryHint: document.querySelector("#galleryHint"),
  mediaFilter: document.querySelector("#mediaFilter"),
  showNoFaceVideos: document.querySelector("#showNoFaceVideos"),
  yearFilter: document.querySelector("#yearFilter"),
  monthFilter: document.querySelector("#monthFilter"),
  dateFilter: document.querySelector("#dateFilter"),
  sortDirection: document.querySelector("#sortDirection"),
  lightbox: document.querySelector("#lightbox"),
  lightboxImage: document.querySelector("#lightboxImage"),
  lightboxVideo: document.querySelector("#lightboxVideo"),
  lightboxName: document.querySelector("#lightboxName"),
  lightboxMeta: document.querySelector("#lightboxMeta"),
  lightboxClose: document.querySelector("#lightboxClose"),
  lightboxPrev: document.querySelector("#lightboxPrev"),
  lightboxNext: document.querySelector("#lightboxNext"),
  busyOverlay: document.querySelector("#busyOverlay"),
  busyText: document.querySelector("#busyText"),
  photoTemplate: document.querySelector("#photoTemplate"),
  faceTemplate: document.querySelector("#faceTemplate"),
};

init();

function desktopInvoke() {
  return window.__TAURI__?.core?.invoke || window.__TAURI__?.invoke;
}

function apiUrl(path) {
  return state.backendBaseUrl ? `${state.backendBaseUrl}${path}` : path;
}

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
  renderActivities();
  showAll();
}

function bindEvents() {
  els.scanPathBtn.addEventListener("click", scanPath);
  els.clearDbBtn.addEventListener("click", clearIndex);
  els.searchBtn.addEventListener("click", search);
  els.showAllBtn.addEventListener("click", showAll);
  els.untaggedBtn.addEventListener("click", showUntagged);
  els.createAlbumBtn.addEventListener("click", createAlbum);
  els.albumNameInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") createAlbum();
  });
  els.mediaFilter.addEventListener("change", renderCurrentView);
  els.showNoFaceVideos.addEventListener("change", renderCurrentView);
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
  els.activityToggle.addEventListener("click", toggleActivityPanel);
  els.activityClose.addEventListener("click", () => setActivityPanel(false));
  document.addEventListener("click", handleActivityOutsideClick);
  setupDesktopBridge();
  setupGalleryPaging();
}

function setupDesktopBridge() {
  const invoke = desktopInvoke();
  if (!els.pickFolderBtn || (!invoke && !state.support.backend)) return;

  document.body.classList.add("desktop-shell");
  els.pickFolderBtn.hidden = false;
  els.pickFolderBtn.addEventListener("click", async () => {
    try {
      const path = await pickFolder(invoke);
      if (!path) return;
      els.pathInput.value = path;
      els.folderLabel.textContent = displayFolderName(path);
      els.folderLabel.title = path;
      addActivity(`Selected folder ${displayFolderName(path)}`);
    } catch (error) {
      setProgress(error.message || "Could not open folder picker.", 0);
    }
  });
}

async function pickFolder(invoke) {
  if (invoke) {
    return invoke("pick_folder");
  }
  const response = await fetch(apiUrl("/api/pick-folder"), { method: "POST" });
  const payload = await response.json();
  if (!payload.ok) throw new Error(payload.error || "Could not open folder picker.");
  return payload.path || "";
}

function setupGalleryPaging() {
  if ("IntersectionObserver" in window) {
    state.galleryObserver = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          appendGalleryBatch();
        }
      },
      { rootMargin: "700px 0px" },
    );
    return;
  }

  window.addEventListener("scroll", () => {
    const nearBottom = window.innerHeight + window.scrollY >= document.body.offsetHeight - 700;
    if (nearBottom) appendGalleryBatch();
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
  const invoke = desktopInvoke();
  if (invoke) {
    try {
      state.backendBaseUrl = await invoke("backend_url");
    } catch (error) {
      state.support.backend = false;
      state.support.backendError = error.message || "The local backend did not start.";
      return;
    }
  }

  const attempts = state.backendBaseUrl ? 240 : 1;
  let lastError = "";
  try {
    for (let attempt = 0; attempt < attempts; attempt += 1) {
      try {
        const response = await fetch(apiUrl("/api/health"), { cache: "no-store" });
        if (!response.ok) {
          lastError = `Backend returned ${response.status}.`;
        } else {
          const payload = await response.json();
          state.support.backend = Boolean(payload.ok);
          const providers = payload.requestedProviders?.filter((provider) => payload.providers?.includes(provider)) || [];
          state.support.engine = payload.engine
            ? `${payload.engine}${providers.length ? ` (${providers.join(" + ")})` : ""}`
            : "";
          state.support.backendError = payload.ok ? "" : payload.error || "";
          return;
        }
      } catch (error) {
        lastError = error.message || "Backend is still starting.";
      }
      if (state.backendBaseUrl) {
        await new Promise((resolve) => setTimeout(resolve, 500));
      }
    }
  } finally {
    if (!state.support.backend && state.backendBaseUrl) {
      state.support.backendError = lastError || "The local backend did not become ready.";
    }
  }
  if (!state.support.backend) {
    state.support.backend = false;
  }
}

async function restoreBackendIndex() {
  const [filesResponse, albumsResponse, tagsResponse] = await Promise.all([
    fetch(apiUrl("/api/files")),
    fetch(apiUrl("/api/albums")),
    fetch(apiUrl("/api/photo-tags")),
  ]);
  const [records, albums, tags] = await Promise.all([
    filesResponse.json(),
    albumsResponse.json(),
    tagsResponse.json(),
  ]);
  state.files.clear();
  for (const record of records) {
    state.files.set(record.id, record);
  }
  state.albums = albums;
  state.photoTags = tags;
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

  const scanMode = els.scanMode.value;
  const modeLabel = els.scanMode.selectedOptions[0]?.textContent.toLowerCase() || "photos";
  const albumName = els.scanAlbumInput.value.trim();
  const activityId = startActivity(`Scan ${modeLabel}`, displayFolderName(path));
  setProgress(`Scanning ${modeLabel}${albumName ? ` into "${albumName}"` : ""} with InsightEdge. Large libraries can take a while...`, 8);
  els.scanPathBtn.disabled = true;
  try {
    const response = await fetch(apiUrl("/api/scan"), {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ path, scanMode, albumName }),
    });
    const payload = await response.json();
    if (!payload.ok) throw new Error(payload.error || "Scan failed.");
    state.files.clear();
    for (const record of payload.files) {
      state.files.set(record.id, record);
    }
    if (payload.albums) state.albums = payload.albums;
    if (payload.tags) state.photoTags = payload.tags;
    populateYearFilter();
    els.folderLabel.textContent = displayFolderName(path);
    els.folderLabel.title = path;
    const autoTagged = payload.autoTagged ? ` ${payload.autoTagged} faces auto-tagged.` : "";
    const warningText = payload.warnings?.length ? ` ${payload.warnings.length} files warned/skipped.` : "";
    const albumText = albumName ? ` Added to "${albumName}".` : "";
    setProgress(`Scan complete: ${payload.files.length} files indexed.${autoTagged}${warningText}${albumText}`, 100);
    finishActivity(activityId, "done", `${payload.files.length} files indexed${payload.warnings?.length ? `, ${payload.warnings.length} warnings` : ""}`);
    showAll();
  } catch (error) {
    setProgress(error.message, 0);
    finishActivity(activityId, "failed", error.message);
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

function renderGallery(
  ids,
  title = "Matches",
  hint = "Separate people, albums, and photo tags with commas. All terms must match.",
  initialBatchSize = GALLERY_BATCH_SIZE,
) {
  state.filteredIds = ids;
  state.galleryCursor = 0;
  els.galleryTitle.textContent = title;
  els.galleryHint.textContent = hint;
  els.matchCount.textContent = ids.length;
  state.galleryObserver?.disconnect();
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

  appendGalleryBatch(initialBatchSize);
  updateStats();
}

function appendGalleryBatch(batchSize = GALLERY_BATCH_SIZE) {
  if (state.galleryCursor >= state.filteredIds.length) return;

  els.gallery.querySelector(".gallery-sentinel")?.remove();
  const fragment = document.createDocumentFragment();
  const nextCursor = Math.min(state.galleryCursor + batchSize, state.filteredIds.length);

  for (const id of state.filteredIds.slice(state.galleryCursor, nextCursor)) {
    const fileRecord = state.files.get(id);
    if (!fileRecord) continue;
    if (!matchesCurrentGalleryFilters(fileRecord)) continue;
    fragment.append(renderPhoto(fileRecord));
  }

  state.galleryCursor = nextCursor;
  els.gallery.append(fragment);

  if (state.galleryCursor < state.filteredIds.length) {
    const sentinel = document.createElement("div");
    sentinel.className = "gallery-sentinel";
    sentinel.textContent = `Loading ${Math.min(GALLERY_BATCH_SIZE, state.filteredIds.length - state.galleryCursor)} more photos...`;
    els.gallery.append(sentinel);
    state.galleryObserver?.observe(sentinel);
  }
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
  const tagChips = fragment.querySelector(".photo-tag-chips");
  const albumSelect = fragment.querySelector(".album-select");
  const customTagInput = fragment.querySelector(".custom-tag-input");
  const addCustomTagButton = fragment.querySelector(".add-custom-tag");
  const bulkBar = fragment.querySelector(".bulk-face-actions");
  const bulkCount = fragment.querySelector(".bulk-face-count");
  const bulkRemoveButton = fragment.querySelector(".bulk-remove-face");
  const selectedFaces = new Map();

  const updateBulkBar = () => {
    const count = selectedFaces.size;
    bulkBar.hidden = count === 0;
    bulkCount.textContent = `${count} selected`;
  };

  card.dataset.fileId = fileRecord.id;
  name.textContent = fileRecord.name;
  path.textContent = displayFileLocation(fileRecord.path);
  path.title = fileRecord.path;
  renderPhotoCollectionControls(fileRecord, tagChips, albumSelect);
  albumSelect.addEventListener("change", () => addPhotoToAlbum(fileRecord, albumSelect));
  addCustomTagButton.addEventListener("click", () => addCustomPhotoTag(fileRecord, customTagInput, addCustomTagButton));
  customTagInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") addCustomPhotoTag(fileRecord, customTagInput, addCustomTagButton);
  });
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

  const visibleFaces = displayFaces(fileRecord);
  for (const face of visibleFaces) {
    if (!isVideoRecord(fileRecord)) {
      mediaWrap.append(renderFaceBox(face, fileRecord));
    }
    faces.append(renderFaceEditor(fileRecord, face, (isSelected) => {
      if (isSelected) {
        selectedFaces.set(face.id, face);
      } else {
        selectedFaces.delete(face.id);
      }
      updateBulkBar();
    }));
  }

  bulkRemoveButton.addEventListener("click", () => bulkRemoveFaces(fileRecord, [...selectedFaces.values()], bulkRemoveButton));

  if (!visibleFaces.length) {
    const empty = document.createElement("p");
    empty.className = "file-path";
    empty.textContent = fileRecord.faces.length
      ? "No main faces to tag. Try rescan after adjusting video filters."
      : "No faces detected in this file.";
    faces.append(empty);
  }

  return card;
}

function renderPhotoCollectionControls(fileRecord, tagChips, albumSelect) {
  const chips = [
    ...(fileRecord.albums || []).map((album) => ({ ...album, label: album.name, type: "album" })),
    ...(fileRecord.tags || []).map((tag) => ({ ...tag, label: tag.name, type: "tag" })),
  ];
  tagChips.replaceChildren(
    ...chips.map(({ id, label, type }) => {
      const chip = document.createElement("span");
      chip.className = `photo-tag-chip ${type}`;
      const text = document.createElement("span");
      text.textContent = type === "album" ? `Album: ${label}` : label;
      chip.append(text);
      if (type === "album" || type === "tag") {
        const removeButton = document.createElement("button");
        removeButton.className = "remove-collection-chip";
        removeButton.type = "button";
        const removeLabel = type === "album" ? `Remove from album ${label}` : `Remove photo tag ${label}`;
        removeButton.setAttribute("aria-label", removeLabel);
        removeButton.title = removeLabel;
        removeButton.textContent = "×";
        removeButton.addEventListener("click", () => {
          if (type === "album") {
            removePhotoFromAlbum(fileRecord, id, removeButton);
          } else {
            removeCustomPhotoTag(fileRecord, id, label, removeButton);
          }
        });
        chip.append(removeButton);
      }
      return chip;
    }),
  );

  const assignedAlbumIds = new Set((fileRecord.albums || []).map((album) => album.id));
  albumSelect.replaceChildren(new Option("Choose album", ""));
  for (const album of state.albums) {
    if (!assignedAlbumIds.has(album.id)) {
      albumSelect.append(new Option(album.name, String(album.id)));
    }
  }
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

function displayFaces(fileRecord) {
  const faces = sortedFaces(fileRecord.faces || []);
  if (!isVideoRecord(fileRecord)) return faces;

  const grouped = new Map();
  const result = [];
  for (const face of faces) {
    const tagKey = normalizeName(face.tag);
    if (!tagKey) {
      if (isLikelyMainVideoFace(face)) {
        result.push(face);
      }
      continue;
    }

    const existing = grouped.get(tagKey);
    if (!existing) {
      const copy = { ...face, groupedFaceIds: [face.id] };
      grouped.set(tagKey, copy);
      result.push(copy);
      continue;
    }

    existing.groupedFaceIds.push(face.id);
    existing.appearanceCount = (existing.appearanceCount || 1) + (face.appearanceCount || 1);
    const existingTime = existing.representativeTimestampSeconds ?? existing.timestampSeconds ?? Number.POSITIVE_INFINITY;
    const faceTime = face.representativeTimestampSeconds ?? face.timestampSeconds ?? Number.POSITIVE_INFINITY;
    if (faceTime < existingTime) {
      existing.timestampSeconds = face.timestampSeconds;
      existing.representativeTimestampSeconds = face.representativeTimestampSeconds;
      existing.thumbnail = face.thumbnail;
      existing.box = face.box;
    }
  }
  return sortedFaces(result);
}

function isLikelyMainVideoFace(face) {
  return (face.appearanceCount || 1) >= MIN_VIDEO_FACE_APPEARANCES;
}

function openLightbox(fileId) {
  const index = state.filteredIds.indexOf(fileId);
  if (index < 0) return;

  state.lightboxIndex = index;
  renderLightbox();
  els.lightbox.classList.add("open");
  els.lightbox.setAttribute("aria-hidden", "false");
  document.body.classList.add("lightbox-active");
}

function closeLightbox() {
  els.lightbox.classList.remove("open");
  els.lightbox.setAttribute("aria-hidden", "true");
  els.lightboxVideo.pause();
  document.body.classList.remove("lightbox-active");
}

function stepLightbox(direction) {
  if (!state.filteredIds.length) return;
  state.lightboxIndex = (state.lightboxIndex + direction + state.filteredIds.length) % state.filteredIds.length;
  renderLightbox();
}

function renderLightbox() {
  const fileRecord = state.files.get(state.filteredIds[state.lightboxIndex]);
  if (!fileRecord) return;

  const isVideo = VIDEO_TYPES.has(fileRecord.type);
  els.lightboxImage.style.display = isVideo ? "none" : "block";
  els.lightboxVideo.style.display = isVideo ? "block" : "none";
  if (isVideo) {
    els.lightboxVideo.src = getObjectUrl(fileRecord);
    els.lightboxImage.removeAttribute("src");
  } else {
    els.lightboxImage.src = getObjectUrl(fileRecord);
    els.lightboxImage.alt = fileRecord.name;
    els.lightboxVideo.pause();
    els.lightboxVideo.removeAttribute("src");
  }
  els.lightboxName.textContent = fileRecord.name;
  const people = [...new Set(fileRecord.faces.map((face) => face.tag).filter(Boolean))].sort();
  const date = photoTakenDate(fileRecord)?.slice(0, 10) || "Date unknown";
  els.lightboxMeta.textContent = `${state.lightboxIndex + 1} of ${state.filteredIds.length} · ${date}${people.length ? ` · ${people.join(", ")}` : ""}`;
}

function handleLightboxKeys(event) {
  if (!els.lightbox.classList.contains("open")) return;
  if (event.key === "Escape") closeLightbox();
  if (event.key === "ArrowLeft") stepLightbox(-1);
  if (event.key === "ArrowRight") stepLightbox(1);
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
    return apiUrl(`/api/media?path=${encodeURIComponent(fileRecord.path)}`);
  }

  if (!fileRecord.file) {
    return "";
  }

  if (!state.objectUrls.has(fileRecord.id)) {
    state.objectUrls.set(fileRecord.id, URL.createObjectURL(fileRecord.file));
  }
  return state.objectUrls.get(fileRecord.id);
}

function isVideoRecord(fileRecord) {
  return VIDEO_TYPES.has(fileRecord.type);
}

function displayFileLocation(path = "") {
  const parts = pathParts(path);
  if (parts.length >= 2) return `${parts.at(-2)}/${parts.at(-1)}`;
  return path || "Unknown location";
}

function displayFolderName(path = "") {
  return pathParts(path).at(-1) || path || "No folder selected";
}

function pathParts(path = "") {
  return path.split(/[\\/]+/).filter(Boolean);
}

function renderFaceBox(face, fileRecord) {
  const box = document.createElement("span");
  box.className = "face-box";
  box.dataset.faceId = face.id;
  box.title = face.tag || "Untagged face";
  box.style.left = `${(face.box.x / fileRecord.width) * 100}%`;
  box.style.top = `${(face.box.y / fileRecord.height) * 100}%`;
  box.style.width = `${(face.box.width / fileRecord.width) * 100}%`;
  box.style.height = `${(face.box.height / fileRecord.height) * 100}%`;
  return box;
}

function renderFaceEditor(fileRecord, face, onSelectionChange = () => {}) {
  const fragment = els.faceTemplate.content.cloneNode(true);
  const chip = fragment.querySelector(".face-chip");
  const checkbox = fragment.querySelector(".face-select");
  const canvas = fragment.querySelector("canvas");
  const input = fragment.querySelector('input[type="text"]');
  const faceExtra = fragment.querySelector(".face-extra");
  let removeButton = fragment.querySelector(".remove-face-btn") || fragment.querySelector(".remove-face");
  const image = new Image();

  chip.dataset.faceId = face.id;
  if (!removeButton) {
    removeButton = document.createElement("button");
    removeButton.className = "remove-face-btn";
    removeButton.type = "button";
    removeButton.setAttribute("aria-label", "Remove face");
    removeButton.title = "Remove face";
    removeButton.textContent = "−";
    chip.append(removeButton);
  }
  removeButton.textContent = "−";

  input.value = face.tag || "";
  let savedTag = input.value.trim();
  let tagSavePromise = null;
  checkbox.addEventListener("change", () => onSelectionChange(checkbox.checked));
  if (faceExtra) {
    const appearances = face.appearanceCount > 1 ? `${face.appearanceCount} appearances` : "";
    const timestamp = formatTimestamp(face.representativeTimestampSeconds ?? face.timestampSeconds);
    faceExtra.textContent = [appearances, timestamp].filter(Boolean).join(" · ");
  }
  const commitTag = async () => {
    const tag = input.value.trim();
    if (tag === savedTag) return;
    if (tagSavePromise) {
      await tagSavePromise;
      return;
    }
    face.tag = tag;
    face.__changed = true;
    tagSavePromise = (async () => {
      try {
        setBusy(true, "Applying tag...");
        await saveFaceTag(fileRecord, face, tag);
        input.value = tag;
        face.tag = tag;
        savedTag = tag;
        updateStats();
        renderPeople();
      } catch (error) {
        input.value = savedTag;
        face.tag = savedTag;
        setProgress(error.message, 0);
      } finally {
        tagSavePromise = null;
        setBusy(false);
      }
    })();
    await tagSavePromise;
  };
  input.addEventListener("blur", () => {
    commitTag();
  });
  input.addEventListener("change", () => {
    commitTag();
  });
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      commitTag();
    }
  });
  removeButton.addEventListener("click", () => removeFace(fileRecord, face));

  image.onload = () => {
    if (face.thumbnail) {
      drawFullCanvas(canvas, image);
    } else {
      drawFaceCrop(canvas, image, face, fileRecord);
    }
  };
  image.src = getFaceImageUrl(fileRecord, face);

  return chip;
}

async function removeFace(fileRecord, face) {
  if (face.tag && !confirm(`Remove face tagged "${face.tag}"?`)) return;

  const scrollTop = window.scrollY;
  const loadedCardCount = Math.max(state.galleryCursor, GALLERY_BATCH_SIZE);
  const activityId = startActivity("Remove face box", fileRecord.name);
  try {
    setBusy(true, "Removing face box...");
    await ignoreFaceIds(fileRecord, face.groupedFaceIds || [face.id]);
    renderGallery(
      state.filteredIds.filter((id) => state.files.has(id)),
      els.galleryTitle.textContent,
      els.galleryHint.textContent,
      loadedCardCount,
    );
    window.scrollTo({ top: scrollTop });
    finishActivity(activityId, "done", fileRecord.name);
  } catch (error) {
    setProgress(error.message, 0);
    finishActivity(activityId, "failed", error.message);
  } finally {
    setBusy(false);
  }
}

async function bulkRemoveFaces(fileRecord, faces, button) {
  if (!faces.length) return;
  const tagged = faces.filter((face) => face.tag).map((face) => face.tag);
  if (tagged.length && !confirm(`Remove ${faces.length} selected face boxes, including tagged faces?`)) return;

  const scrollTop = window.scrollY;
  const loadedCardCount = Math.max(state.galleryCursor, GALLERY_BATCH_SIZE);
  const faceIds = faces.flatMap((face) => face.groupedFaceIds || [face.id]);
  const activityId = startActivity("Remove selected faces", `${faces.length} selected in ${fileRecord.name}`);
  button.disabled = true;
  try {
    setBusy(true, "Removing selected faces...");
    await ignoreFaceIds(fileRecord, faceIds);
    renderGallery(
      state.filteredIds.filter((id) => state.files.has(id)),
      els.galleryTitle.textContent,
      els.galleryHint.textContent,
      loadedCardCount,
    );
    window.scrollTo({ top: scrollTop });
    finishActivity(activityId, "done", `${faces.length} face boxes removed`);
  } catch (error) {
    setProgress(error.message, 0);
    finishActivity(activityId, "failed", error.message);
  } finally {
    setBusy(false);
    button.disabled = false;
  }
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

function drawFullCanvas(canvas, image) {
  const context = canvas.getContext("2d");
  context.clearRect(0, 0, canvas.width, canvas.height);
  context.drawImage(image, 0, 0, canvas.width, canvas.height);
}

function getFaceImageUrl(fileRecord, face) {
  if (face.thumbnail && state.support.backend) {
    return apiUrl(`/api/media?path=${encodeURIComponent(face.thumbnail)}`);
  }
  return face.thumbnail || getObjectUrl(fileRecord);
}

function formatTimestamp(seconds) {
  if (seconds === null || seconds === undefined || Number.isNaN(Number(seconds))) return "";
  const total = Math.max(0, Math.floor(Number(seconds)));
  const minutes = Math.floor(total / 60);
  const remaining = total % 60;
  return `${minutes}:${String(remaining).padStart(2, "0")}`;
}

function search() {
  const terms = parseSearch(els.searchInput.value);
  state.currentView = {
    type: terms.length ? "search" : "all",
    title: terms.length ? `Search: ${terms.join(" + ")}` : "All Indexed Files",
    hint: terms.length
      ? "Every person, album, or photo tag must match the same file."
      : "Separate people, albums, and photo tags with commas. All terms must match.",
    terms,
  };
  applyGalleryFilters();
}

function applyGalleryFilters() {
  const ids = [...state.files.values()]
    .filter(matchesCurrentGalleryFilters)
    .sort(comparePhotos)
    .map((fileRecord) => fileRecord.id);

  renderGallery(ids, state.currentView.title, state.currentView.hint);
}

function matchesCurrentGalleryFilters(fileRecord) {
  return (
    matchesMediaFilter(fileRecord) &&
    matchesVisibleVideoFaces(fileRecord) &&
    matchesPeople(fileRecord, state.currentView.terms || []) &&
    matchesSelectedAlbum(fileRecord) &&
    matchesDateFilters(fileRecord)
  );
}

function replaceGalleryCard(fileId) {
  const fileRecord = state.files.get(fileId);
  if (!fileRecord) return false;

  for (const card of els.gallery.querySelectorAll(".photo-card")) {
    if (card.dataset.fileId === fileId) {
      card.replaceWith(renderPhoto(fileRecord));
      return true;
    }
  }
  return false;
}

function applyTagToFileRecord(fileRecord, faceIds, tag) {
  let updated = 0;
  for (const candidate of fileRecord.faces || []) {
    if (faceIds.includes(candidate.id)) {
      candidate.tag = tag;
      candidate.tagSource = tag ? "manual" : "";
      updated += 1;
    }
  }
  return updated;
}

function syncFileRecord(fileRecord, updatedFile) {
  if (!updatedFile) return fileRecord;
  Object.assign(fileRecord, updatedFile);
  state.files.set(fileRecord.id, fileRecord);
  return fileRecord;
}

function refreshRenderedFaceTags() {
  for (const card of els.gallery.querySelectorAll(".photo-card")) {
    const fileRecord = state.files.get(card.dataset.fileId);
    if (!fileRecord) continue;

    const tagsByFaceId = new Map((fileRecord.faces || []).map((face) => [face.id, face.tag || ""]));
    for (const chip of card.querySelectorAll(".face-chip")) {
      const input = chip.querySelector('input[type="text"]');
      const tag = tagsByFaceId.get(chip.dataset.faceId);
      if (input && tag !== undefined) {
        input.value = tag;
      }
    }

    for (const box of card.querySelectorAll(".face-box")) {
      const tag = tagsByFaceId.get(box.dataset.faceId);
      if (tag !== undefined) {
        box.title = tag || "Untagged face";
      }
    }
  }
}

function shouldRerenderAfterTag(fileRecord) {
  if (!fileRecord) return true;
  if (!matchesCurrentGalleryFilters(fileRecord)) return true;
  if (state.currentView.type === "untagged") {
    return !fileRecord.faces.some((face) => !normalizeName(face.tag));
  }
  return false;
}

function showAll() {
  els.searchInput.value = "";
  els.mediaFilter.value = "both";
  els.showNoFaceVideos.checked = false;
  els.yearFilter.value = "";
  els.monthFilter.value = "";
  els.dateFilter.value = "";
  state.currentView = { type: "all", title: "All Indexed Files", hint: "Separate people, albums, and photo tags with commas. All terms must match.", terms: [] };
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
    .filter(matchesMediaFilter)
    .filter(matchesVisibleVideoFaces)
    .filter((fileRecord) => fileRecord.faces.some((face) => !normalizeName(face.tag)))
    .filter(matchesDateFilters)
    .sort(comparePhotos)
    .map((fileRecord) => fileRecord.id);
  renderGallery(ids, state.currentView.title, state.currentView.hint);
}

function matchesPeople(fileRecord, terms) {
  if (!terms.length) return true;
  const searchableTerms = new Set([
    ...(fileRecord.faces || []).map((face) => normalizeName(face.tag)),
    ...(fileRecord.albums || []).map((album) => normalizeName(album.name)),
    ...(fileRecord.tags || []).map((tag) => normalizeName(tag.name)),
  ].filter(Boolean));
  return terms.every((term) => searchableTerms.has(term));
}

function matchesSelectedAlbum(fileRecord) {
  if (state.currentView.type !== "album") return true;
  return (fileRecord.albums || []).some((album) => album.id === state.currentView.albumId);
}

function matchesMediaFilter(fileRecord) {
  if (els.mediaFilter.value === "photos") return !isVideoRecord(fileRecord);
  if (els.mediaFilter.value === "videos") return isVideoRecord(fileRecord);
  return true;
}

function matchesVisibleVideoFaces(fileRecord) {
  if (!isVideoRecord(fileRecord)) return true;
  return els.showNoFaceVideos.checked || displayFaces(fileRecord).length > 0;
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
  return value.split(",").map(normalizeName).filter(Boolean);
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
  renderPersonSuggestions([...counts.keys()]);
  renderCollections();
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

function renderCollections() {
  renderAlbumSuggestions();
  renderCollectionButtons(els.albumList, state.albums, "No albums yet.", (album) => {
    state.currentView = {
      type: "album",
      albumId: album.id,
      title: `Album: ${album.name}`,
      hint: `${album.photoCount} saved file${album.photoCount === 1 ? "" : "s"}.`,
      terms: [],
    };
    applyGalleryFilters();
  });
  renderCollectionButtons(els.photoTagList, state.photoTags, "No photo tags yet.", (tag) => {
    els.searchInput.value = tag.name;
    search();
  });
}

function renderAlbumSuggestions() {
  els.albumSuggestions.replaceChildren(
    ...state.albums.map((album) => {
      const option = document.createElement("option");
      option.value = album.name;
      return option;
    }),
  );
}

function renderCollectionButtons(container, items, emptyText, onClick) {
  container.replaceChildren();
  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = emptyText;
    container.append(empty);
    return;
  }

  for (const item of items) {
    const button = document.createElement("button");
    button.className = "person-button";
    button.innerHTML = `<strong></strong><span></span>`;
    button.querySelector("strong").textContent = item.name;
    button.querySelector("span").textContent = item.photoCount;
    button.addEventListener("click", () => onClick(item));
    container.append(button);
  }
}

async function createAlbum() {
  const name = els.albumNameInput.value.trim();
  if (!name) return;
  const activityId = startActivity(`Create album ${name}`);
  try {
    setBusy(true, "Creating album...");
    const payload = await postLibraryMutation("/api/albums", { name });
    syncLibraryPayload(payload);
    els.albumNameInput.value = "";
    renderCurrentView({ preserveScroll: true });
    setProgress(`Album "${name}" is ready.`, 100);
    finishActivity(activityId, "done", name);
  } catch (error) {
    setProgress(error.message, 0);
    finishActivity(activityId, "failed", error.message);
  } finally {
    setBusy(false);
  }
}

async function addPhotoToAlbum(fileRecord, select) {
  const albumId = Number(select.value);
  if (!albumId) return;
  const album = state.albums.find((candidate) => candidate.id === albumId);
  const activityId = startActivity(`Add to album ${album?.name || ""}`, fileRecord.name);
  select.disabled = true;
  try {
    setBusy(true, "Adding photo to album...");
    const payload = await postLibraryMutation("/api/albums/photos", { albumId, fileId: fileRecord.id });
    syncLibraryPayload(payload);
    renderCurrentView({ preserveScroll: true });
    setProgress(`Added ${fileRecord.name} to ${album?.name || "album"}.`, 100);
    finishActivity(activityId, "done", fileRecord.name);
  } catch (error) {
    setProgress(error.message, 0);
    finishActivity(activityId, "failed", error.message);
  } finally {
    select.disabled = false;
    setBusy(false);
  }
}

async function removePhotoFromAlbum(fileRecord, albumId, button) {
  const album = state.albums.find((candidate) => candidate.id === albumId);
  const activityId = startActivity(`Remove from album ${album?.name || ""}`, fileRecord.name);
  button.disabled = true;
  try {
    setBusy(true, "Removing photo from album...");
    const payload = await deleteLibraryMutation("/api/albums/photos", { albumId, fileId: fileRecord.id });
    syncLibraryPayload(payload);
    renderCurrentView({ preserveScroll: true });
    setProgress(`Removed ${fileRecord.name} from ${album?.name || "album"}.`, 100);
    finishActivity(activityId, "done", fileRecord.name);
  } catch (error) {
    setProgress(error.message, 0);
    finishActivity(activityId, "failed", error.message);
  } finally {
    button.disabled = false;
    setBusy(false);
  }
}

async function addCustomPhotoTag(fileRecord, input, button) {
  const tag = input.value.trim();
  if (!tag) return;
  const activityId = startActivity(`Add photo tag ${tag}`, fileRecord.name);
  button.disabled = true;
  try {
    setBusy(true, "Adding photo tag...");
    const payload = await postLibraryMutation("/api/photos/tags", { fileId: fileRecord.id, tag });
    syncLibraryPayload(payload);
    input.value = "";
    renderCurrentView({ preserveScroll: true });
    setProgress(`Tagged ${fileRecord.name} with "${tag}".`, 100);
    finishActivity(activityId, "done", fileRecord.name);
  } catch (error) {
    setProgress(error.message, 0);
    finishActivity(activityId, "failed", error.message);
  } finally {
    button.disabled = false;
    setBusy(false);
  }
}

async function removeCustomPhotoTag(fileRecord, tagId, tagName, button) {
  const activityId = startActivity(`Remove photo tag ${tagName}`, fileRecord.name);
  button.disabled = true;
  try {
    setBusy(true, "Removing photo tag...");
    const payload = await deleteLibraryMutation("/api/photos/tags", { fileId: fileRecord.id, tagId });
    syncLibraryPayload(payload);
    renderCurrentView({ preserveScroll: true });
    setProgress(`Removed "${tagName}" from ${fileRecord.name}.`, 100);
    finishActivity(activityId, "done", fileRecord.name);
  } catch (error) {
    setProgress(error.message, 0);
    finishActivity(activityId, "failed", error.message);
  } finally {
    button.disabled = false;
    setBusy(false);
  }
}

async function postLibraryMutation(path, body) {
  return libraryMutation(path, "POST", body);
}

async function deleteLibraryMutation(path, body) {
  return libraryMutation(path, "DELETE", body);
}

async function libraryMutation(path, method, body) {
  const response = await fetch(apiUrl(path), {
    method,
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = await response.json();
  if (!payload.ok) throw new Error(payload.error || "Could not update library.");
  return payload;
}

function syncLibraryPayload(payload) {
  if (payload.files) {
    state.files.clear();
    for (const record of payload.files) {
      state.files.set(record.id, record);
    }
  }
  if (payload.albums) state.albums = payload.albums;
  if (payload.tags) state.photoTags = payload.tags;
  populateYearFilter();
  updateStats();
}

function renderPersonSuggestions(names) {
  els.personSuggestions.replaceChildren(
    ...names
      .sort((a, b) => a.localeCompare(b))
      .map((name) => {
        const option = document.createElement("option");
        option.value = name;
        return option;
      }),
  );
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

function setBusy(isBusy, text = "Applying changes...") {
  els.busyText.textContent = text;
  els.busyOverlay.classList.toggle("open", isBusy);
  els.busyOverlay.setAttribute("aria-hidden", String(!isBusy));
}

async function saveFaceTag(fileRecord, face, tag) {
  const cleanTag = tag.trim();
  const faceIds = face.groupedFaceIds || [face.id];
  const activityId = startActivity(cleanTag ? `Tag ${cleanTag}` : "Clear tag", fileRecord.name);
  try {
    if (!state.support.backend) {
      applyTagToFileRecord(fileRecord, faceIds, cleanTag);
      await saveFile(fileRecord);
      finishActivity(activityId, "done", `${faceIds.length} face${faceIds.length === 1 ? "" : "s"} updated`);
      return;
    }

    let payload = null;
    const response = await fetch(apiUrl("/api/tag"), {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ fileId: fileRecord.id, faceId: faceIds[0], tag: cleanTag }),
    });
    payload = await response.json();
    if (!payload.ok) throw new Error(payload.error || "Could not tag face.");

    if (payload?.files) {
      state.files.clear();
      for (const record of payload.files) {
        state.files.set(record.id, record);
      }
      populateYearFilter();
      if (payload.propagated) {
        setProgress(`Tagged ${payload.propagated + 1} matching faces.`, 100);
      }
      const updatedFile = state.files.get(fileRecord.id);
      if (updatedFile) {
        applyTagToFileRecord(updatedFile, faceIds, cleanTag);
      }
      const currentFile = syncFileRecord(fileRecord, updatedFile);
      if (shouldRerenderAfterTag(currentFile) || !replaceGalleryCard(fileRecord.id)) {
        renderCurrentView({ preserveScroll: true });
      } else {
        refreshRenderedFaceTags();
      }
    }
    finishActivity(activityId, "done", `${faceIds.length} face${faceIds.length === 1 ? "" : "s"} updated`);
  } catch (error) {
    finishActivity(activityId, "failed", error.message);
    throw error;
  }
}

function startActivity(title, detail = "") {
  const id = activityId();
  state.activities.unshift({
    id,
    title,
    detail,
    status: "running",
    startedAt: new Date(),
    finishedAt: null,
  });
  trimActivities();
  renderActivities();
  return id;
}

function finishActivity(id, status, detail = "") {
  const activity = state.activities.find((item) => item.id === id);
  if (!activity) return;
  activity.status = status;
  activity.detail = detail || activity.detail;
  activity.finishedAt = new Date();
  trimActivities();
  renderActivities();
}

function trimActivities() {
  state.activities = state.activities
    .sort((a, b) => b.startedAt - a.startedAt)
    .slice(0, ACTIVITY_LIMIT);
}

function renderActivities() {
  const running = state.activities.filter((activity) => activity.status === "running").length;
  els.activityToggle.textContent = running ? `Activity: ${running} running` : `Activity: ${state.activities.length ? "Recent" : "Idle"}`;
  els.activityList.replaceChildren();

  if (!state.activities.length) {
    const empty = document.createElement("li");
    empty.className = "activity-item done";
    empty.innerHTML = `<span class="activity-main"><span class="activity-title">No recent activity</span></span>`;
    els.activityList.append(empty);
    return;
  }

  for (const activity of state.activities) {
    const item = document.createElement("li");
    item.className = `activity-item ${activity.status}`;
    item.innerHTML = `
      <span class="activity-main">
        <span class="activity-title"></span>
        <span class="activity-detail"></span>
        <span class="activity-time"></span>
      </span>
    `;
    item.querySelector(".activity-title").textContent = activity.title;
    item.querySelector(".activity-detail").textContent = activity.detail || activity.status;
    item.querySelector(".activity-time").textContent = activityTime(activity);
    els.activityList.append(item);
  }
}

function toggleActivityPanel() {
  setActivityPanel(els.activityPanel.hidden);
}

function setActivityPanel(isOpen) {
  els.activityPanel.hidden = !isOpen;
  els.activityToggle.setAttribute("aria-expanded", String(isOpen));
}

function handleActivityOutsideClick(event) {
  if (els.activityPanel.hidden) return;
  if (els.activityPanel.contains(event.target) || els.activityToggle.contains(event.target)) return;
  setActivityPanel(false);
}

function activityTime(activity) {
  if (activity.status === "running") {
    return `Started ${formatClock(activity.startedAt)}`;
  }
  return `${activity.status === "done" ? "Done" : "Failed"} ${formatClock(activity.finishedAt || activity.startedAt)}`;
}

function formatClock(date) {
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function activityId() {
  if (globalThis.crypto?.randomUUID) return crypto.randomUUID();
  return `activity-${Date.now()}-${Math.random().toString(16).slice(2)}`;
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
      const response = await fetch(apiUrl("/api/tag"), {
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
    durationSeconds: fileRecord.durationSeconds,
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
  const activityId = startActivity("Clear index", "Removing saved files and tags");
  try {
    if (state.support.backend) {
      await fetch(apiUrl("/api/clear"), { method: "POST" });
    }
  } catch (error) {
    finishActivity(activityId, "failed", error.message);
    throw error;
  }
  return new Promise((resolve, reject) => {
    const transaction = state.db.transaction(STORE, "readwrite");
    const request = transaction.objectStore(STORE).clear();
    request.onsuccess = () => {
      for (const url of state.objectUrls.values()) URL.revokeObjectURL(url);
      state.objectUrls.clear();
      state.files.clear();
      state.albums = [];
      state.photoTags = [];
      els.folderLabel.textContent = "No folder selected";
      setProgress("Index cleared.", 0);
      showAll();
      finishActivity(activityId, "done", "Index cleared");
      resolve();
    };
    request.onerror = () => {
      finishActivity(activityId, "failed", request.error?.message || "Could not clear index");
      reject(request.error);
    };
  });
}

async function ignoreFace(fileRecord, face) {
  return ignoreFaceIds(fileRecord, [face.id]);
}

async function ignoreFaceIds(fileRecord, faceIds) {
  if (!state.support.backend) {
    fileRecord.faces = fileRecord.faces.filter((candidate) => !faceIds.includes(candidate.id));
    await saveFile(fileRecord);
    setProgress("Face box removed. It will stay hidden on future scans.", 100);
    return;
  }

  let payload = null;
  for (const faceId of faceIds) {
    const response = await fetch(apiUrl("/api/ignore-face"), {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ fileId: fileRecord.id, faceId }),
    });
    payload = await response.json();
    if (!payload.ok) throw new Error(payload.error || "Could not remove face.");
  }

  state.files.clear();
  for (const record of payload?.files || []) {
    state.files.set(record.id, record);
  }
  populateYearFilter();
  setProgress("Face box removed. It will stay hidden on future scans.", 100);
}

async function rescanPhoto(fileRecord, resetIgnored, button) {
  if (!state.support.backend) return;
  const activityId = startActivity(resetIgnored ? "Reset ignored and rescan" : "Rescan faces", fileRecord.name);
  button.disabled = true;
  try {
    const response = await fetch(apiUrl(resetIgnored ? "/api/reset-ignored-faces" : "/api/rescan-photo"), {
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
    finishActivity(activityId, "done", `${fileRecord.name}${payload.warnings?.length ? `, ${payload.warnings.length} warnings` : ""}`);
  } catch (error) {
    setProgress(error.message, 0);
    finishActivity(activityId, "failed", error.message);
  } finally {
    button.disabled = false;
  }
}

function normalizeName(name = "") {
  return name.trim().toLocaleLowerCase();
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}
