import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const html = readFileSync(new URL("../index.html", import.meta.url), "utf8");
const appJs = readFileSync(new URL("../app.js", import.meta.url), "utf8");
const styles = readFileSync(new URL("../styles.css", import.meta.url), "utf8");

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
  assert.match(appJs, /String\(name \?\? ""\)\.trim\(\)\.toLocaleLowerCase\(\)/);
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
  assert.match(html, /id="lightboxUnavailable" class="media-unavailable" hidden/);
  assert.match(html, /id="lightboxPrev"/);
  assert.match(html, /id="lightboxNext"/);
  assert.match(appJs, /function openLightbox\(/);
  assert.match(appJs, /function stepLightbox\(/);
  assert.match(appJs, /mediaWrap\.addEventListener\("click", \(\) => openLightbox\(fileRecord\.id\)\)/);
  assert.match(appJs, /createMediaElement\(fileRecord, \(\) => showMediaUnavailable\(mediaWrap, fileRecord\)\)/);
  assert.match(appJs, /function resetLightboxMedia\(\)/);
  assert.match(appJs, /els\.lightboxImage\.onerror = null/);
  assert.match(appJs, /els\.lightboxVideo\.onerror = null/);
  assert.match(appJs, /function showMediaUnavailable\(container, fileRecord\)/);
  assert.match(appJs, /function showLightboxMediaUnavailable\(fileRecord\)/);
  assert.match(appJs, /addEventListener\("error", onUnavailable, \{ once: true \}\)/);
  assert.match(styles, /\.media-unavailable\s*{/);
  assert.match(styles, /\.media-unavailable\[hidden\]\s*{/);
  assert.match(styles, /\.lightbox-frame \.media-unavailable\s*{/);
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
  assert.match(html, /id="pathInput" type="hidden"/);
  assert.doesNotMatch(html, /placeholder="\/Users\/you\/Pictures\/Photo Library"/);
  assert.match(html, /id="pickFolderBtn" class="primary"[^>]*>Choose Folder<\/button>/);
  assert.match(html, /id="folderLabel">Choose a folder to start<\/span>/);
  assert.match(html, /id="scanMode"/);
  assert.match(html, /id="scanAlbumInput"/);
  assert.match(html, /id="scanLocationInput"/);
  assert.match(html, /id="scanPathBtn" class="primary">Scan<\/button>/);
  assert.match(html, /id="locationSuggestions"/);
  assert.match(html, /id="albumSuggestions"/);
  assert.match(html, /value="photos"/);
  assert.match(html, /value="videos"/);
  assert.match(html, /value="both"/);
  assert.match(appJs, /scanMode: document\.querySelector\("#scanMode"\)/);
  assert.match(appJs, /scanAlbumInput: document\.querySelector\("#scanAlbumInput"\)/);
  assert.match(appJs, /body: JSON\.stringify\(\{ path, scanMode, albumName, location \}\)/);
  assert.match(appJs, /function renderAlbumSuggestions\(\)/);
  assert.match(appJs, /function scanLocationInput\(\)/);
  assert.match(appJs, /function locationFromInput\(input\)/);
  assert.match(appJs, /Choose a folder first\./);
});

test("video records can render in the gallery and lightbox", () => {
  assert.match(html, /id="lightboxVideo"/);
  assert.match(appJs, /const VIDEO_TYPES = new Set/);
  assert.match(appJs, /document\.createElement\("video"\)/);
  assert.match(appJs, /resetLightboxMedia\(\)/);
  assert.match(appJs, /els\.lightboxVideo\.style\.display = "block"/);
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
  assert.match(appJs, /parts\.slice\(-3\)\.join\(" \/ "\)/);
  assert.match(appJs, /path\.title = fileRecord\.path/);
  assert.match(styles, /#folderLabel\s*{[^}]*text-overflow: ellipsis;[^}]*white-space: nowrap;/s);
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
  assert.match(appJs, /input\.addEventListener\("blur", \(\) => \{\s*void commitTag\(\)/s);
  assert.match(appJs, /input\.addEventListener\("focusout", \(\) => \{\s*void commitTag\(\)/s);
  assert.match(appJs, /input\.addEventListener\("keydown", \(event\) => \{\s*if \(event\.key === "Enter"\)/s);
  assert.match(appJs, /event\.preventDefault\(\)/);
  assert.match(appJs, /void commitTag\(\)/);
});

test("tag save patches the edited gallery card instead of rerendering every media item", () => {
  assert.match(appJs, /card\.dataset\.fileId = fileRecord\.id/);
  assert.match(appJs, /function replaceGalleryCard\(fileId\)/);
  assert.match(appJs, /card\.replaceWith\(renderPhoto\(fileRecord\)\)/);
  assert.match(appJs, /function applyTagToFileRecord\(fileRecord, faceIds, tag\)/);
  assert.match(appJs, /function syncFileRecord\(fileRecord, updatedFile\)/);
  assert.match(appJs, /function updateAfterFaceTag\(fileRecord, faceIds, tag, payload = null\)/);
  assert.match(appJs, /function refreshRenderedFaceTags\(\)/);
  assert.match(appJs, /Object\.assign\(fileRecord, updatedFile\)/);
  assert.match(appJs, /chip\.dataset\.faceId = face\.id/);
  assert.match(appJs, /box\.dataset\.faceId = face\.id/);
  assert.match(appJs, /tagsByFaceId\.get\(chip\.dataset\.faceId\)/);
  assert.match(appJs, /input\.value = tag/);
  assert.match(appJs, /updateAfterFaceTag\(fileRecord, faceIds, cleanTag, payload\)/);
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

test("photo cards collapse faces and organize controls by default", () => {
  assert.match(html, /class="card-section faces-section"/);
  assert.match(html, /class="card-section organize-section"/);
  assert.match(html, /<summary>Faces<\/summary>/);
  assert.match(html, /<summary>Organize<\/summary>/);
  assert.match(html, /class="photo-badges"/);
  assert.match(html, /class="face-summary"/);
  assert.match(appJs, /facesSection\.open = visibleFaces\.some\(\(face\) => !normalizeName\(face\.tag\)\)/);
  assert.match(appJs, /function formatFaceSummary\(fileRecord, visibleFaces\)/);
});

test("locations can be browsed resolved and edited from the UI", () => {
  assert.match(html, /id="locationToggle"/);
  assert.match(html, /aria-label="Browse locations"/);
  assert.match(html, /<svg viewBox="0 0 24 24" aria-hidden="true">/);
  assert.match(html, /id="locationPanel"/);
  assert.match(html, /id="locationList"/);
  assert.match(html, /id="resolveLocationsBtn"/);
  assert.match(html, /class="location-input"/);
  assert.match(html, /class="save-location[^"]*"/);
  assert.match(html, /class="remove-location[^"]*"/);
  assert.match(appJs, /fetch\(apiUrl\("\/api\/locations"\)\)/);
  assert.match(appJs, /\/api\/locations\/suggest\?q=/);
  assert.match(appJs, /function scheduleLocationSuggestions\(query\)/);
  assert.match(appJs, /function renderLocations\(\)/);
  assert.match(appJs, /function locationTree\(\)/);
  assert.match(appJs, /function setLocationFilter\(type, place, closePanel = false\)/);
  assert.match(appJs, /function matchesLocationFilter\(fileRecord\)/);
  assert.match(appJs, /openLocationNodes: new Set\(\)/);
  assert.match(appJs, /function toggleLocationNode\(event, key, node\)/);
  assert.match(appJs, /state\.openLocationNodes\.has\(countryKey\)/);
  assert.match(appJs, /unresolvedGpsCount\(\)/);
  assert.match(appJs, /function resolveLocations\(\)/);
  assert.match(appJs, /postLibraryMutation\("\/api\/locations\/resolve"/);
  assert.match(appJs, /postLibraryMutation\("\/api\/photos\/location"/);
  assert.match(appJs, /deleteLibraryMutation\("\/api\/photos\/location"/);
  assert.match(styles, /\.location-panel\s*{[^}]*position: absolute;[^}]*width: min\(380px, calc\(100vw - 40px\)\);/s);
  assert.match(styles, /\.location-list\s*{[^}]*max-height: 188px;[^}]*overflow-y: auto;/s);
});

test("clear index resets frontend location state", () => {
  assert.match(appJs, /async function clearIndex\(\)/);
  assert.match(appJs, /state\.locations = \[\]/);
  assert.match(appJs, /state\.locationSuggestions\.clear\(\)/);
  assert.match(appJs, /state\.openLocationNodes\.clear\(\)/);
  assert.match(appJs, /els\.locationSuggestions\.replaceChildren\(\)/);
  assert.match(appJs, /renderLocations\(\)/);
});

test("backup and restore controls are wired to backend APIs", () => {
  assert.doesNotMatch(html, /id="backupPathInput"/);
  assert.match(html, /id="includeMediaBackup"/);
  assert.match(html, /class="library-maintenance"/);
  assert.match(html, /id="libraryBackupMode"/);
  assert.match(html, /id="libraryRestoreMode"/);
  assert.match(html, /id="backupPanel" class="maintenance-panel" hidden/);
  assert.match(html, /id="restorePanel" class="maintenance-panel" hidden/);
  assert.match(html, /id="chooseBackupFolderBtn"/);
  assert.match(html, /id="backupFolderLabel"/);
  assert.match(html, /id="backupBtn"/);
  assert.doesNotMatch(html, /id="restorePathInput"/);
  assert.doesNotMatch(html, /id="validateRestoreBtn"/);
  assert.match(html, /id="chooseRestoreFolderBtn"/);
  assert.match(html, /id="restoreFolderLabel"/);
  assert.match(html, /id="restoreBtn"/);
  assert.match(html, /id="backupStatus"/);
  assert.match(html, /id="backupWarningsToggle"/);
  assert.match(html, /id="backupWarningsPanel" class="backup-warnings" hidden/);
  assert.match(html, /id="backupWarningsList"/);
  assert.match(html, /id="clearDbBtn"/);
  assert.match(appJs, /function createLibraryBackup\(\)/);
  assert.match(appJs, /function validateLibraryRestore\(\)/);
  assert.match(appJs, /function restoreLibraryBackup\(\)/);
  assert.match(appJs, /function toggleLibraryToolMode\(mode\)/);
  assert.match(appJs, /function setLibraryToolMode\(mode\)/);
  assert.match(appJs, /function setBackupWarnings\(warnings = \[\]\)/);
  assert.match(appJs, /function toggleBackupWarnings\(\)/);
  assert.match(appJs, /function setBackupWarningsPanel\(isOpen\)/);
  assert.match(appJs, /els\.libraryBackupMode\.addEventListener\("click", \(\) => toggleLibraryToolMode\("backup"\)\)/);
  assert.match(appJs, /els\.libraryRestoreMode\.addEventListener\("click", \(\) => toggleLibraryToolMode\("restore"\)\)/);
  assert.match(appJs, /els\.backupWarningsToggle\.addEventListener\("click", toggleBackupWarnings\)/);
  assert.match(appJs, /setLibraryToolMode\(currentMode === mode \? "" : mode\)/);
  assert.match(appJs, /els\.chooseRestoreFolderBtn\.addEventListener\("click", chooseRestoreFolder\)/);
  assert.match(appJs, /await validateLibraryRestore\(\)/);
  assert.match(appJs, /els\.restoreBtn\.disabled = false/);
  assert.match(appJs, /function describeRestoreValidation\(payload\)/);
  assert.match(appJs, /postLibraryMutation\("\/api\/backup"/);
  assert.match(appJs, /fetch\(apiUrl\("\/api\/restore\/validate"\)/);
  assert.match(appJs, /postLibraryMutation\("\/api\/restore"/);
  assert.match(appJs, /const restorePrompt = warningCount/);
  assert.match(appJs, /confirm\(restorePrompt\)/);
  assert.match(appJs, /This backup has \$\{warningCount\} warning/);
  assert.match(appJs, /payload\.skippedMediaCount/);
  assert.match(styles, /\.library-maintenance\s*{/);
  assert.match(styles, /\.maintenance-panel\s*{/);
  assert.match(styles, /\.backup-warnings\s*{[^}]*max-height: 150px;[^}]*overflow-y: auto;/s);
  assert.match(styles, /\.backup-status\.error\s*{/);
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
