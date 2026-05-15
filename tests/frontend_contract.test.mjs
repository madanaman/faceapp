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

test("people search excludes records with no matching tagged faces at search and render time", () => {
  assert.match(appJs, /function matchesPeople\(/);
  assert.match(appJs, /\.filter\(\(fileRecord\) => matchesPeople\(fileRecord, terms\)\)/);
  assert.match(appJs, /if \(!matchesPeople\(fileRecord, state\.currentView\.terms \|\| \[\]\)\) continue/);
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
