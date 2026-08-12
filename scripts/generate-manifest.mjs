// Reads public/data/source/*.json (hand-authored) and writes public/data/generated/*.json:
// denormalized, name-resolved data ready for direct rendering, plus reference-integrity
// checks so a typo'd id fails the build instead of silently rendering blank names.
import { readFileSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const rootDir = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const sourceDir = path.join(rootDir, "public", "data", "source");
const outDir = path.join(rootDir, "public", "data", "generated");

function readSource(name) {
  return JSON.parse(readFileSync(path.join(sourceDir, `${name}.json`), "utf-8"));
}

const works = readSource("works");
const staff = readSource("staff");
const studios = readSource("studios");
const voiceActors = readSource("voiceActors");
const series = readSource("series");
const themes = readSource("themes");
const awards = readSource("awards");

// Optional: built by `npm run fetch-covers` (scripts/fetch-covers.mjs), which resolves the
// AniList key visual per work, then commits the result here so builds stay offline/deterministic.
// Absent entries just mean "no cover resolved yet".
const coversCachePath = path.join(sourceDir, "covers-cache.json");
const coversCache = existsSync(coversCachePath) ? JSON.parse(readFileSync(coversCachePath, "utf-8")) : {};

const staffById = new Map(staff.map((s) => [s.id, s]));
const studiosById = new Map(studios.map((s) => [s.id, s]));
const voiceActorsById = new Map(voiceActors.map((v) => [v.id, v]));
const seriesById = new Map(series.map((x) => [x.id, x]));
const themesById = new Map(themes.map((t) => [t.id, t]));
const awardsById = new Map(awards.map((a) => [a.id, a]));

const QUARTERS = ["winter", "spring", "summer", "fall"];
const ORIGINAL_TYPES = ["manga", "lightnovel", "novel", "game", "original", "other"];

/** 年内のクール順まで含めた比較キー(src/ui/common/labels.ts の seasonSortKey と同じ並び)。 */
function seasonKey(s) {
  return s.year * 4 + QUARTERS.indexOf(s.quarter);
}

const errors = [];

function checkRef(map, id, kind, workId) {
  if (!map.has(id)) errors.push(`work "${workId}": unknown ${kind} id "${id}"`);
}

for (const w of works) {
  if (!Array.isArray(w.directorIds) || w.directorIds.length === 0) {
    errors.push(`work "${w.id}": directorIds must list at least one staff member`);
  }
  if (!Array.isArray(w.studioIds) || w.studioIds.length === 0) {
    errors.push(`work "${w.id}": studioIds must list at least one studio`);
  }
  (w.directorIds ?? []).forEach((id) => checkRef(staffById, id, "staff (director)", w.id));
  (w.seriesComposerIds ?? []).forEach((id) => checkRef(staffById, id, "staff (series composer)", w.id));
  (w.studioIds ?? []).forEach((id) => checkRef(studiosById, id, "studio", w.id));
  (w.cast ?? []).forEach((c) => {
    checkRef(voiceActorsById, c.voiceActorId, "voice actor", w.id);
    if (!c.character) errors.push(`work "${w.id}": cast entry "${c.voiceActorId}" is missing character`);
  });
  if (w.seriesId != null) checkRef(seriesById, w.seriesId, "series", w.id);
  w.themeIds.forEach((id) => checkRef(themesById, id, "theme", w.id));
  (w.awardResults ?? []).forEach((r) => checkRef(awardsById, r.awardId, "award", w.id));

  if (!["tv", "movie", "ova", "ona"].includes(w.format)) {
    errors.push(`work "${w.id}": format must be one of tv/movie/ova/ona (got "${w.format}")`);
  }
  if (!w.season || !Number.isInteger(w.season.year) || !QUARTERS.includes(w.season.quarter)) {
    errors.push(`work "${w.id}": season must be { year, quarter: winter|spring|summer|fall }`);
  }
  // seasonCount / latestSeason は scripts/backfill_seasons.py が入れる派生データ。手で書くと
  // broadcastNote の「第N期」とずれるので、値の形と前後関係だけはここで見ておく。
  if (w.seasonCount != null && (!Number.isInteger(w.seasonCount) || w.seasonCount < 2)) {
    errors.push(`work "${w.id}": seasonCount must be an integer >= 2 (got ${w.seasonCount})`);
  }
  if (w.latestSeason != null) {
    if (!Number.isInteger(w.latestSeason.year) || !QUARTERS.includes(w.latestSeason.quarter)) {
      errors.push(`work "${w.id}": latestSeason must be { year, quarter: winter|spring|summer|fall }`);
    } else if (seasonKey(w.latestSeason) < seasonKey(w.season)) {
      errors.push(`work "${w.id}": latestSeason must not be earlier than season`);
    }
  }
  if (!ORIGINAL_TYPES.includes(w.originalType)) {
    errors.push(`work "${w.id}": originalType must be one of ${ORIGINAL_TYPES.join("|")} (got "${w.originalType}")`);
  }
}

const workIds = new Set();
for (const w of works) {
  if (workIds.has(w.id)) errors.push(`duplicate work id "${w.id}"`);
  workIds.add(w.id);
}

for (const [label, list] of [
  ["staff", staff],
  ["studio", studios],
  ["voiceActor", voiceActors],
  ["series", series],
  ["theme", themes],
  ["award", awards],
]) {
  const seen = new Set();
  for (const item of list) {
    if (seen.has(item.id)) errors.push(`duplicate ${label} id "${item.id}"`);
    seen.add(item.id);
  }
}

if (errors.length > 0) {
  console.error("generate-manifest: reference integrity errors:");
  for (const e of errors) console.error(`  - ${e}`);
  process.exit(1);
}

// ---- related works ("この作品が好きなら") ----
// Cosine similarity over IDF-weighted theme tags, plus a bonus for sharing a studio or director.
// IDF matters because the tag vocabulary is deliberately small and reused: a tag carried by
// hundreds of works says almost nothing about similarity, while a rare one is highly informative.
// Spoiler tags are excluded from the scoring so the recommendation row can't hint at a twist.
const RELATED_COUNT = 6;
const SAME_STUDIO_BONUS = 0.15;
const SAME_DIRECTOR_BONUS = 0.1;

const worksById = new Map(works.map((x) => [x.id, x]));

const tagsOf = (x) => x.themeIds.filter((id) => !themesById.get(id).spoiler);

const tagDocFreq = new Map();
for (const x of works) {
  for (const t of tagsOf(x)) tagDocFreq.set(t, (tagDocFreq.get(t) ?? 0) + 1);
}
// A tag carried by every work gets idf 0 and drops out of the scoring entirely.
const tagIdf = new Map([...tagDocFreq].map(([t, df]) => [t, Math.log(works.length / df)]));

const tagNorm = new Map(
  works.map((x) => {
    let sumSquares = 0;
    for (const t of tagsOf(x)) sumSquares += tagIdf.get(t) ** 2;
    return [x.id, Math.sqrt(sumSquares)];
  }),
);

const tagToItems = new Map();
for (const x of works) {
  for (const t of tagsOf(x)) {
    if (!tagToItems.has(t)) tagToItems.set(t, []);
    tagToItems.get(t).push(x);
  }
}

function relatedIdsFor(item) {
  // Accumulate the dot product only over works that share at least one tag, rather than
  // scanning all N works for each of N works.
  const dotProducts = new Map();
  for (const t of tagsOf(item)) {
    const weight = tagIdf.get(t) ** 2;
    if (weight === 0) continue;
    for (const other of tagToItems.get(t)) {
      if (other.id === item.id) continue;
      dotProducts.set(other.id, (dotProducts.get(other.id) ?? 0) + weight);
    }
  }

  const ownStudios = new Set(item.studioIds);
  const ownDirectors = new Set(item.directorIds);

  // Same-studio works are a strong recommendation even with no tag overlap, so seed them in.
  for (const other of works) {
    if (other.id === item.id || dotProducts.has(other.id)) continue;
    if (other.studioIds.some((id) => ownStudios.has(id))) dotProducts.set(other.id, 0);
  }

  const ownNorm = tagNorm.get(item.id);
  const scored = [];
  for (const [otherId, dot] of dotProducts) {
    const other = worksById.get(otherId);
    const otherNorm = tagNorm.get(otherId);
    let score = ownNorm > 0 && otherNorm > 0 ? dot / (ownNorm * otherNorm) : 0;
    if (other.studioIds.some((id) => ownStudios.has(id))) score += SAME_STUDIO_BONUS;
    if (other.directorIds.some((id) => ownDirectors.has(id))) score += SAME_DIRECTOR_BONUS;
    if (score > 0) scored.push({ id: otherId, score });
  }

  // Tie-break by id so the output (and therefore the prerendered HTML) is stable across builds.
  scored.sort((a, b) => b.score - a.score || a.id.localeCompare(b.id));
  return scored.slice(0, RELATED_COUNT).map((s) => s.id);
}

const relatedById = new Map(works.map((x) => [x.id, relatedIdsFor(x)]));

// ---- generated/works.json ----
// あらすじ・出典メモ・updatedAt はここに入れない(作品詳細ページでしか使わないのに
// works.json の大きな割合を占める)。詳細ページ用は work-texts.json に分ける。
const worksGenerated = works.map(({ synopsis, sourceNote, updatedAt, ...w }) => ({
  relatedWorkIds: relatedById.get(w.id),
  ...w,
  directorNames: w.directorIds.map((id) => staffById.get(id).name),
  seriesName: w.seriesId != null ? seriesById.get(w.seriesId).name : undefined,
  seriesComposerNames: w.seriesComposerIds.map((id) => staffById.get(id).name),
  studioNames: w.studioIds.map((id) => studiosById.get(id).name),
  castGenerated: (w.cast ?? []).map((c) => ({
    ...c,
    voiceActorName: voiceActorsById.get(c.voiceActorId).name,
  })),
  themeNames: w.themeIds.map((id) => themesById.get(id).name),
  // Precomputed so WorkCard can drop spoiler chips without fetching themes.json itself.
  spoilerThemeIds: w.themeIds.filter((id) => themesById.get(id).spoiler),
  awardSummaries: (w.awardResults ?? []).map((r) => ({
    awardId: r.awardId,
    awardName: awardsById.get(r.awardId).name,
    year: r.year,
    result: r.result,
  })),
  coverUrl: coversCache[w.id]?.coverUrl ?? undefined,
}));

// 相互参照リスト(スタッフ・スタジオ・声優・シリーズ・テーマの各詳細ページ)は作品を**idの配列**で
// 持ち、表示側は works.json(取得済みキャッシュ)から引き直して WorkCard を描く。
// 作品をフル展開して埋め込むと1作品が複数のリストに重複して入り、themes.json が gzip 5.5MB・
// voiceActors.json が gzip 4.7MB あった(2026-08-12に是正)。
const idsBy = (list, cmp) => [...list].sort(cmp).map((w) => w.id);

/** 放送開始クール順。声優の出演歴やシリーズ内の並びは「始まった順」に見たいので、
 *  一覧の表示・並べ替えに使う latestSeason ではなく season のまま比べる。 */
function bySeason(a, b) {
  return seasonKey(a.season) - seasonKey(b.season);
}

function groupWorksBy(idsOf) {
  const map = new Map();
  for (const w of works) {
    for (const id of idsOf(w)) {
      if (!map.has(id)) map.set(id, []);
      map.get(id).push(w);
    }
  }
  return map;
}

// ---- generated/staff.json ----
// Directed and composed works stay separate so the detail page can show two sections
// (game-db's developer/publisher roles pattern).
const worksByDirector = groupWorksBy((w) => w.directorIds);
const worksByComposer = groupWorksBy((w) => w.seriesComposerIds);
const staffGenerated = staff
  .map((s) => {
    const directed = worksByDirector.get(s.id) ?? [];
    const composed = worksByComposer.get(s.id) ?? [];
    const uniqueCount = new Set([...directed, ...composed].map((w) => w.id)).size;
    return {
      id: s.id,
      name: s.name,
      nameKana: s.nameKana,
      description: s.description,
      externalLinks: s.externalLinks,
      workCount: uniqueCount,
      directedWorkIds: idsBy(directed, bySeason),
      composedWorkIds: idsBy(composed, bySeason),
    };
  })
  .sort((a, b) => a.nameKana.localeCompare(b.nameKana, "ja"));

// ---- generated/studios.json ----
const worksByStudio = groupWorksBy((w) => w.studioIds);
const studiosGenerated = studios
  .map((s) => {
    const theirWorks = worksByStudio.get(s.id) ?? [];
    return {
      id: s.id,
      name: s.name,
      nameKana: s.nameKana,
      description: s.description,
      externalLinks: s.externalLinks,
      workCount: theirWorks.length,
      workIds: idsBy(theirWorks, bySeason),
    };
  })
  .sort((a, b) => a.nameKana.localeCompare(b.nameKana, "ja"));

// ---- generated/voiceActors.json ----
// Roles keep the character name alongside the embedded work, in broadcast order.
const rolesByActor = new Map();
for (const w of works) {
  for (const c of w.cast ?? []) {
    if (!rolesByActor.has(c.voiceActorId)) rolesByActor.set(c.voiceActorId, []);
    rolesByActor.get(c.voiceActorId).push({ character: c.character, work: w });
  }
}
const voiceActorsGenerated = voiceActors
  .map((v) => {
    const roles = (rolesByActor.get(v.id) ?? []).sort((x, y) => bySeason(x.work, y.work));
    return {
      id: v.id,
      name: v.name,
      nameKana: v.nameKana,
      description: v.description,
      externalLinks: v.externalLinks,
      workCount: roles.length,
      roles: roles.map((r) => ({ character: r.character, workId: r.work.id })),
    };
  })
  .sort((a, b) => a.nameKana.localeCompare(b.nameKana, "ja"));

// ---- generated/series.json ----
// 作品は新しい順(放送順の逆)で固定。最新作から辿れるほうが探しやすいという判断。
// 一覧はテーマ・アワードと同じく収録作品数の多い順(同数は五十音順)。
const worksBySeries = groupWorksBy((w) => (w.seriesId != null ? [w.seriesId] : []));
const seriesGenerated = series
  .map((x) => {
    const theirWorks = worksBySeries.get(x.id) ?? [];
    return {
      id: x.id,
      name: x.name,
      nameKana: x.nameKana,
      description: x.description,
      externalLinks: x.externalLinks,
      workCount: theirWorks.length,
      workIds: idsBy(theirWorks, (a, b) => bySeason(b, a)),
    };
  })
  .sort((a, b) => b.workCount - a.workCount || a.nameKana.localeCompare(b.nameKana, "ja"));

// ---- generated/themes.json ----
const worksByTheme = groupWorksBy((w) => w.themeIds);
const themesGenerated = themes
  .map((t) => {
    const theirWorks = worksByTheme.get(t.id) ?? [];
    return {
      ...t,
      workCount: theirWorks.length,
      workIds: idsBy(theirWorks, bySeason),
    };
  })
  .sort((a, b) => b.workCount - a.workCount || a.name.localeCompare(b.name, "ja"));

// ---- generated/work-texts.json ----
// 作品詳細ページだけが読む長文(あらすじ・出典メモ)。キーは作品id。
const workTexts = Object.fromEntries(
  works.map((w) => [w.id, { synopsis: w.synopsis, sourceNote: w.sourceNote }]),
);

// ---- generated/awards.json ----
// 受賞歴の result は「グランプリ」「作品賞」「第1位」のような自由文なので、
// 並べ替え用の順位をここで一度だけ取り出す。順位を持たない賞(グランプリ・大賞など)は
// 大賞系を先頭、それ以外を末尾に置く。
function rankOf(result) {
  const m = /第\s*(\d+)\s*位/.exec(result ?? "");
  if (m) return Number(m[1]);
  if (/大賞|グランプリ|1位|第一位/.test(result ?? "")) return 0;
  return 900;
}

const winnersByAward = new Map();
for (const w of works) {
  for (const r of w.awardResults ?? []) {
    if (!winnersByAward.has(r.awardId)) winnersByAward.set(r.awardId, []);
    winnersByAward.get(r.awardId).push({
      workId: w.id,
      workTitle: w.title,
      year: r.year,
      result: r.result,
      rank: rankOf(r.result),
    });
  }
}
const awardsGenerated = awards
  .map((a) => {
    // 年の降順 → 部門(result から順位表記を除いた部分)→ 順位の昇順。
    const section = (r) => (r.result ?? "").replace(/第\s*\d+\s*位.*$/, "").trim();
    const winners = (winnersByAward.get(a.id) ?? []).sort(
      (x, y) =>
        y.year - x.year ||
        section(x).localeCompare(section(y), "ja") ||
        x.rank - y.rank ||
        x.workTitle.localeCompare(y.workTitle, "ja"),
    );
    return { ...a, workCount: winners.length, winners };
  })
  // 受賞作の多い賞ほど見たい情報なので件数の降順。同数は名前順で並びを安定させる。
  .sort((a, b) => b.workCount - a.workCount || a.name.localeCompare(b.name, "ja"));

// ---- generated/counts.json ----
const counts = {
  works: works.length,
  series: series.length,
  staff: staff.length,
  studios: studios.length,
  voiceActors: voiceActors.length,
  themes: themes.length,
  awards: awards.length,
};

mkdirSync(outDir, { recursive: true });
writeFileSync(path.join(outDir, "works.json"), JSON.stringify(worksGenerated), "utf-8");
writeFileSync(path.join(outDir, "staff.json"), JSON.stringify(staffGenerated), "utf-8");
writeFileSync(path.join(outDir, "studios.json"), JSON.stringify(studiosGenerated), "utf-8");
writeFileSync(path.join(outDir, "voiceActors.json"), JSON.stringify(voiceActorsGenerated), "utf-8");
writeFileSync(path.join(outDir, "series.json"), JSON.stringify(seriesGenerated), "utf-8");
writeFileSync(path.join(outDir, "themes.json"), JSON.stringify(themesGenerated), "utf-8");
writeFileSync(path.join(outDir, "awards.json"), JSON.stringify(awardsGenerated), "utf-8");
writeFileSync(path.join(outDir, "work-texts.json"), JSON.stringify(workTexts), "utf-8");
writeFileSync(path.join(outDir, "counts.json"), JSON.stringify(counts), "utf-8");

console.log(
  `generate-manifest: wrote ${works.length} works, ${staff.length} staff, ${studios.length} studios, ${voiceActors.length} voice actors, ${series.length} series, ${themes.length} themes, ${awards.length} awards`
);


// ---- sitemap.xml ----
// Lives at the site root (not data/generated/) so it's served at /anime-db/sitemap.xml, but is
// just as deterministically derived from public/data/source/*.json — see the .gitignore note.
const SITE_URL = "https://izenmi.github.io/anime-db";
const today = new Date().toISOString().slice(0, 10);

function urlEntry(loc, lastmod) {
  return `  <url>\n    <loc>${SITE_URL}${loc}</loc>\n    <lastmod>${lastmod ?? today}</lastmod>\n  </url>`;
}

const sitemapEntries = [
  urlEntry("/"),
  urlEntry("/works"),
  ...works.map((w) => urlEntry(`/works/${w.id}`, w.updatedAt?.slice(0, 10))),
  urlEntry("/series"),
  ...series.map((x) => urlEntry(`/series/${x.id}`, x.updatedAt?.slice(0, 10))),
  urlEntry("/themes"),
  ...themes.map((t) => urlEntry(`/themes/${t.id}`)),
  urlEntry("/staff"),
  ...staff.map((s) => urlEntry(`/staff/${s.id}`, s.updatedAt?.slice(0, 10))),
  urlEntry("/studios"),
  ...studios.map((s) => urlEntry(`/studios/${s.id}`, s.updatedAt?.slice(0, 10))),
  urlEntry("/cast"),
  ...voiceActors.map((v) => urlEntry(`/cast/${v.id}`, v.updatedAt?.slice(0, 10))),
  urlEntry("/awards"),
  ...awards.map((a) => urlEntry(`/awards/${a.id}`, a.updatedAt?.slice(0, 10))),
  urlEntry("/about"),
];

const sitemapXml =
  `<?xml version="1.0" encoding="UTF-8"?>\n` +
  `<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${sitemapEntries.join("\n")}\n</urlset>\n`;

writeFileSync(path.join(rootDir, "public", "sitemap.xml"), sitemapXml, "utf-8");
console.log(`generate-manifest: wrote sitemap.xml with ${sitemapEntries.length} URLs`);
