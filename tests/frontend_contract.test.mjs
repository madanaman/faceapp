import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const html = readFileSync(new URL("../index.html", import.meta.url), "utf8");
const appJs = readFileSync(new URL("../app.js", import.meta.url), "utf8");

test("face editor keeps both tag suggestions and remove control", () => {
  assert.match(html, /<input[^>]+list="personSuggestions"/);
  assert.match(html, /<datalist id="personSuggestions"/);
  assert.match(html, /class="remove-face-btn"/);
  assert.match(html, /aria-label="Remove face"/);
});

test("remove face action remains wired to the backend ignore endpoint", () => {
  assert.match(appJs, /function removeFace\(/);
  assert.match(appJs, /\/api\/ignore-face/);
  assert.match(appJs, /querySelector\("\.remove-face-btn"\)/);
});

test("person search keeps spaces inside names and uses commas for multiple names", () => {
  assert.match(appJs, /function parseSearch\([^)]*\)\s*{[^}]*value\.split\(","\)/s);
  assert.doesNotMatch(appJs, /split\(\s*\/\\s\+/);
});

test("library search can use backend natural-language parsing with comma fallback", () => {
  assert.match(appJs, /async function search\(/);
  assert.match(appJs, /function parseNaturalSearch\(/);
  assert.match(appJs, /\/api\/search\/parse\?q=/);
  assert.match(appJs, /function applyParsedSearchFilters\(/);
  assert.match(appJs, /Interpreted as:/);
  assert.match(appJs, /const displayTerms = parsed \? parsed\.terms \|\| \[\] : parseSearch\(rawQuery\)/);
});

test("people search excludes records with no matching tagged faces at search and render time", () => {
  assert.match(appJs, /function matchesPeople\(/);
  assert.match(appJs, /function matchesCurrentGalleryFilters\(fileRecord\)/);
  assert.match(appJs, /\.filter\(matchesCurrentGalleryFilters\)/);
  assert.match(appJs, /if \(!matchesCurrentGalleryFilters\(fileRecord\)\) continue/);
  assert.match(appJs, /fileRecord\.faces \|\| \[\]/);
});

test("gallery renders in scroll-loaded batches instead of all cards at once", () => {
  assert.match(appJs, /const GALLERY_BATCH_SIZE = 50/);
  assert.match(appJs, /function appendGalleryBatch\(/);
  assert.match(appJs, /IntersectionObserver/);
  assert.match(appJs, /state\.filteredIds\.slice\(state\.galleryCursor, nextCursor\)/);
});

test("gallery cards keep the enlarged photo lightbox with previous and next controls", () => {
  assert.match(html, /id="lightbox"/);
  assert.match(html, /id="lightboxImage"/);
  assert.match(html, /id="lightboxPrev"/);
  assert.match(html, /id="lightboxNext"/);
  assert.match(appJs, /function openLightbox\(/);
  assert.match(appJs, /function stepLightbox\(/);
  assert.match(appJs, /mediaWrap\.addEventListener\("click", \(\) => openLightbox\(fileRecord\.id\)\)/);
});

test("tagging and face removal show a busy overlay while changes apply", () => {
  assert.match(html, /id="busyOverlay"/);
  assert.match(html, /id="busyText"/);
  assert.match(appJs, /function setBusy\(/);
  assert.match(appJs, /setBusy\(true, "Applying tag\.\.\."\)/);
  assert.match(appJs, /setBusy\(true, "Removing face box\.\.\."\)/);
  assert.match(appJs, /setBusy\(false\)/);
});

test("gallery date filters and per-photo rescan controls stay wired", () => {
  assert.match(html, /id="mediaFilter"/);
  assert.match(html, /id="yearFilter"/);
  assert.match(html, /id="monthFilter"/);
  assert.match(html, /id="dateFilter"/);
  assert.match(html, /id="sortDirection"/);
  assert.match(html, /class="rescan-photo"/);
  assert.match(html, /class="reset-ignored"/);
  assert.match(appJs, /function renderCurrentView\(/);
  assert.match(appJs, /function matchesDateFilters\(/);
  assert.match(appJs, /function rescanPhoto\(/);
});

test("scan controls let the user choose photos, videos, or both and bulk-assign an album", () => {
  assert.match(html, /id="scanMode"/);
  assert.match(html, /id="scanAlbumInput"/);
  assert.match(html, /id="albumSuggestions"/);
  assert.match(html, /value="photos"/);
  assert.match(html, /value="videos"/);
  assert.match(html, /value="both"/);
  assert.match(appJs, /scanMode: document\.querySelector\("#scanMode"\)/);
  assert.match(appJs, /scanAlbumInput: document\.querySelector\("#scanAlbumInput"\)/);
  assert.match(appJs, /body: JSON\.stringify\(\{ path, scanMode, albumName \}\)/);
  assert.match(appJs, /function renderAlbumSuggestions\(\)/);
});

test("video records can render in the gallery and lightbox", () => {
  assert.match(html, /id="lightboxVideo"/);
  assert.match(appJs, /const VIDEO_TYPES = new Set/);
  assert.match(appJs, /document\.createElement\("video"\)/);
  assert.match(appJs, /els\.lightboxVideo\.style\.display = isVideo \? "block" : "none"/);
});

test("gallery can filter photos versus videos and hides video preview face boxes", () => {
  assert.match(html, /value="both">Photos and videos/);
  assert.match(html, /value="photos">Photos only/);
  assert.match(html, /value="videos">Videos only/);
  assert.match(html, /id="showNoFaceVideos"/);
  assert.match(appJs, /mediaFilter: document\.querySelector\("#mediaFilter"\)/);
  assert.match(appJs, /showNoFaceVideos: document\.querySelector\("#showNoFaceVideos"\)/);
  assert.match(appJs, /function matchesMediaFilter\(/);
  assert.match(appJs, /function matchesVisibleVideoFaces\(/);
  assert.match(appJs, /displayFaces\(fileRecord\)\.length > 0/);
  assert.match(appJs, /\.filter\(matchesMediaFilter\)/);
  assert.match(appJs, /\.filter\(matchesVisibleVideoFaces\)/);
  assert.match(appJs, /if \(!isVideoRecord\(fileRecord\)\) \{\s*mediaWrap\.append\(renderFaceBox/s);
});

test("video face rows collapse repeated tagged names and paths are shortened for display", () => {
  assert.match(appJs, /function displayFaces\(/);
  assert.match(appJs, /groupedFaceIds/);
  assert.match(appJs, /function displayFileLocation\(/);
  assert.match(appJs, /function displayFolderName\(/);
  assert.match(appJs, /path\.title = fileRecord\.path/);
});

test("face thumbnails from backend media paths render without recropping video faces", () => {
  assert.match(html, /class="face-extra"/);
  assert.match(appJs, /function getFaceImageUrl\(/);
  assert.match(appJs, /\/api\/media\?path=\$\{encodeURIComponent\(face\.thumbnail\)\}/);
  assert.match(appJs, /if \(face\.thumbnail\) \{\s*drawFullCanvas/s);
});

test("activity panel tracks running and recent background actions", () => {
  assert.match(html, /id="activityList"/);
  assert.match(html, /id="activityToggle"/);
  assert.match(html, /id="activityPanel"/);
  assert.match(appJs, /const ACTIVITY_LIMIT = 10/);
  assert.match(appJs, /function startActivity\(/);
  assert.match(appJs, /function finishActivity\(/);
  assert.match(appJs, /function toggleActivityPanel\(/);
  assert.match(appJs, /startActivity\(`Scan \$\{modeLabel\}`/);
  assert.match(appJs, /startActivity\("Selected folder", displayFolderName\(path\)\)/);
  assert.match(appJs, /startActivity\(cleanTag \? `Tag \$\{cleanTag\}` : "Clear tag"/);
  assert.match(appJs, /startActivity\("Remove face box"/);
  assert.match(appJs, /startActivity\(resetIgnored \? "Reset ignored and rescan" : "Rescan faces"/);
  assert.doesNotMatch(appJs, /addActivity/);
});

test("face list supports scrolling and bulk removal", () => {
  assert.match(html, /class="bulk-face-actions"/);
  assert.match(html, /class="bulk-remove-face"/);
  assert.match(html, /class="face-select"/);
  assert.match(appJs, /const MIN_VIDEO_FACE_APPEARANCES = 2/);
  assert.match(appJs, /function bulkRemoveFaces\(/);
  assert.match(appJs, /selectedFaces = new Map\(\)/);
  assert.match(appJs, /ignoreFaceIds\(fileRecord, faceIds\)/);
  assert.match(appJs, /function isLikelyMainVideoFace\(/);
});

test("tag editor targets the text input, not the bulk-select checkbox", () => {
  assert.match(appJs, /querySelector\('input\[type="text"\]'\)/);
  assert.doesNotMatch(appJs, /querySelector\("input"\)/);
});

test("tag editor saves explicitly on blur or Enter", () => {
  assert.match(appJs, /const commitTag = async \(\) =>/);
  assert.match(appJs, /input\.addEventListener\("blur", \(\) => \{\s*commitTag\(\)/s);
  assert.match(appJs, /input\.addEventListener\("keydown", \(event\) => \{\s*if \(event\.key === "Enter"\)/s);
  assert.match(appJs, /event\.preventDefault\(\)/);
  assert.match(appJs, /commitTag\(\)/);
});

test("tag save patches the edited gallery card instead of rerendering every media item", () => {
  assert.match(appJs, /card\.dataset\.fileId = fileRecord\.id/);
  assert.match(appJs, /function replaceGalleryCard\(fileId\)/);
  assert.match(appJs, /card\.replaceWith\(renderPhoto\(fileRecord\)\)/);
  assert.match(appJs, /function applyTagToFileRecord\(fileRecord, faceIds, tag\)/);
  assert.match(appJs, /function syncFileRecord\(fileRecord, updatedFile\)/);
  assert.match(appJs, /function refreshRenderedFaceTags\(\)/);
  assert.match(appJs, /Object\.assign\(fileRecord, updatedFile\)/);
  assert.match(appJs, /chip\.dataset\.faceId = face\.id/);
  assert.match(appJs, /box\.dataset\.faceId = face\.id/);
  assert.match(appJs, /tagsByFaceId\.get\(chip\.dataset\.faceId\)/);
  assert.match(appJs, /input\.value = tag/);
  assert.match(appJs, /function shouldRerenderAfterTag\(fileRecord\)/);
  assert.match(appJs, /if \(shouldRerenderAfterTag\(currentFile\) \|\| !replaceGalleryCard\(fileRecord\.id\)\)/);
  assert.match(appJs, /refreshRenderedFaceTags\(\)/);
});

test("local static script tag does not rely on manual cache-bust strings", () => {
  assert.match(html, /<script src="\.\/app\.js" type="module"><\/script>/);
  assert.doesNotMatch(html, /app\.js\?v=/);
});

test("video cluster tag save sends only one backend request", () => {
  assert.match(appJs, /body: JSON\.stringify\(\{ fileId: fileRecord\.id, faceId: faceIds\[0\], tag: cleanTag \}\)/);
  assert.doesNotMatch(appJs, /for \(const faceId of faceIds\)[\s\S]*\/api\/tag/);
});

test("albums and descriptive photo tags are available from the gallery", () => {
  assert.match(html, /id="albumNameInput"/);
  assert.match(html, /id="createAlbumBtn"/);
  assert.match(html, /id="albumList"/);
  assert.match(html, /id="photoTagList"/);
  assert.match(html, /class="album-select"/);
  assert.doesNotMatch(html, /class="add-album/);
  assert.match(html, /class="custom-tag-input"/);
  assert.match(appJs, /fetch\(apiUrl\("\/api\/albums"\)\)/);
  assert.match(appJs, /fetch\(apiUrl\("\/api\/photo-tags"\)\)/);
  assert.match(appJs, /postLibraryMutation\("\/api\/albums\/photos"/);
  assert.match(appJs, /albumSelect\.addEventListener\("change", \(\) => addPhotoToAlbum\(fileRecord, albumSelect\)\)/);
  assert.match(appJs, /className = "remove-collection-chip"/);
  assert.match(appJs, /deleteLibraryMutation\("\/api\/albums\/photos"/);
  assert.match(appJs, /postLibraryMutation\("\/api\/photos\/tags"/);
  assert.match(appJs, /function removeCustomPhotoTag\(fileRecord, tagId, tagName, button\)/);
  assert.match(appJs, /deleteLibraryMutation\("\/api\/photos\/tags"/);
});

test("desktop shell keeps Tauri bridge and routes backend calls through dynamic URL", () => {
  assert.match(appJs, /function desktopInvoke\(\)/);
  assert.match(appJs, /invoke\("backend_url"\)/);
  assert.match(appJs, /function apiUrl\(path\)/);
  assert.match(appJs, /fetch\(apiUrl\("\/api\/health"\)/);
  assert.match(appJs, /return invoke\("pick_folder"\)/);
});

test("library search includes people albums and custom photo tags", () => {
  assert.match(appJs, /function matchesPeople\(fileRecord, terms\)/);
  assert.match(appJs, /\.\.\.\(fileRecord\.albums \|\| \[\]\)\.map\(\(album\) => normalizeName\(album\.name\)\)/);
  assert.match(appJs, /\.\.\.\(fileRecord\.tags \|\| \[\]\)\.map\(\(tag\) => normalizeName\(tag\.name\)\)/);
  assert.match(appJs, /function matchesSelectedAlbum\(fileRecord\)/);
});

test("library search includes known photo places", () => {
  assert.match(appJs, /function placeSearchTerms\(fileRecord\)/);
  assert.match(appJs, /\[place\.city, place\.region, place\.country\]/);
  assert.match(appJs, /\.\.\.placeSearchTerms\(fileRecord\)/);
});
