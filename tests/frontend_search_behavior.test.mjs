import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const appJs = readFileSync(new URL("../app.js", import.meta.url), "utf8");

const SEARCH_FUNCTIONS = [
  "normalizeName",
  "sortedFaces",
  "displayFaces",
  "isVideoRecord",
  "matchesPeople",
  "placeSearchTerms",
  "matchesSelectedAlbum",
  "matchesLocationFilter",
  "matchesMediaFilter",
  "matchesVisibleVideoFaces",
  "matchesDateFilters",
  "photoTakenDate",
  "matchesCurrentGalleryFilters",
];

function extractFunction(name) {
  const start = appJs.indexOf(`function ${name}`);
  assert.notEqual(start, -1, `Could not find function ${name}`);
  const braceStart = appJs.indexOf("{", start);
  let depth = 0;
  for (let index = braceStart; index < appJs.length; index += 1) {
    if (appJs[index] === "{") depth += 1;
    if (appJs[index] === "}") depth -= 1;
    if (depth === 0) {
      return appJs.slice(start, index + 1);
    }
  }
  throw new Error(`Could not extract function ${name}`);
}

function frontendSearchModel({ state = {}, els = {} } = {}) {
  const baseState = {
    currentView: { type: "search", terms: [] },
    ...state,
  };
  const baseEls = {
    mediaFilter: { value: "both" },
    showNoFaceVideos: { checked: false },
    yearFilter: { value: "" },
    monthFilter: { value: "" },
    dateFilter: { value: "" },
    ...els,
  };
  const body = `
    ${SEARCH_FUNCTIONS.map(extractFunction).join("\n")}
    return { ${SEARCH_FUNCTIONS.join(", ")} };
  `;
  return Function("state", "els", "VIDEO_TYPES", "MIN_VIDEO_FACE_APPEARANCES", body)(
    baseState,
    baseEls,
    new Set(["video/mp4", "video/webm", "video/quicktime", "video/x-m4v", "video/x-msvideo"]),
    2,
  );
}

function photoRecord(overrides = {}) {
  return {
    id: "photo-1",
    name: "photo.jpg",
    type: "image/jpeg",
    faces: [{ id: "face-1", tag: "Aman Madan" }],
    albums: [{ id: 1, name: "Malaysia Trip" }],
    tags: [{ id: 1, name: "Post Ironman" }],
    place: { city: null, region: null, country: null },
    metadata: { taken_at: "2022-12-01T10:00:00" },
    ...overrides,
  };
}

test("people search survives null location fields and matches tagged names", () => {
  const model = frontendSearchModel({
    state: { currentView: { type: "search", terms: ["aman madan"] } },
  });

  assert.equal(model.normalizeName(null), "");
  assert.equal(model.matchesCurrentGalleryFilters(photoRecord()), true);
});

test("typed search can match albums, photo tags, and known locations", () => {
  const model = frontendSearchModel({
    state: { currentView: { type: "search", terms: ["post ironman", "malaysia trip", "toronto"] } },
  });
  const record = photoRecord({
    place: { city: "Toronto", region: "Ontario", country: "Canada" },
  });

  assert.equal(model.matchesCurrentGalleryFilters(record), true);
});

test("date and media filters compose with people search", () => {
  const model = frontendSearchModel({
    state: { currentView: { type: "search", terms: ["aman madan"] } },
    els: {
      mediaFilter: { value: "photos" },
      yearFilter: { value: "2022" },
      monthFilter: { value: "12" },
    },
  });

  assert.equal(model.matchesCurrentGalleryFilters(photoRecord()), true);
  assert.equal(model.matchesCurrentGalleryFilters(photoRecord({ type: "video/mp4" })), false);
  assert.equal(
    model.matchesCurrentGalleryFilters(photoRecord({ metadata: { taken_at: "2021-12-01T10:00:00" } })),
    false,
  );
});

test("location explorer filters country region and city without crashing on missing place data", () => {
  const model = frontendSearchModel({
    state: {
      currentView: {
        type: "location",
        terms: [],
        locationFilter: { country: "Canada", region: "Ontario", city: "Toronto" },
      },
    },
  });

  assert.equal(
    model.matchesCurrentGalleryFilters(photoRecord({ place: { city: "Toronto", region: "Ontario", country: "Canada" } })),
    true,
  );
  assert.equal(model.matchesCurrentGalleryFilters(photoRecord({ place: { city: null, region: null, country: null } })), false);
});
