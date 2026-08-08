// AniListからキービジュアル(coverImage)を取得して public/data/source/covers-cache.json に
// 保存する。works.json の各エントリが持つ anilistId をキーに Media(id:) を直接引くので、
// 姉妹サイトのタイトル検索ベースの表紙取得と違い「あいまいマッチの誤ヒット」が構造的に起きない
// (anilistId の登録間違いはその限りではないので、matchedTitle の目視確認は省略しないこと)。
//
// 使い方:
//   node scripts/fetch-covers.mjs [--only=id1,id2] [--force] [--retry-misses]
//
// - 既定ではキャッシュに無い作品だけ取得する
// - --retry-misses は coverUrl:null のエントリだけを再試行する
// - --force は既存エントリも再取得するが、再取得に失敗した場合は既存の値を維持する([keep])
// - 画像は content-type と実バイト数で検証する(content-length ヘッダはHTTP/2で
//   返らないことがあるため使わない — game-db の IGDB 実装で踏んだバグ)
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const rootDir = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const sourceDir = path.join(rootDir, "public", "data", "source");
const cachePath = path.join(sourceDir, "covers-cache.json");

const API = "https://graphql.anilist.co";
const SLEEP_MS = 2200; // AniListのレート制限(実測30req/分程度)を割らない間隔

const args = process.argv.slice(2);
const force = args.includes("--force");
const retryMisses = args.includes("--retry-misses");
const onlyArg = args.find((a) => a.startsWith("--only="));
const only = onlyArg ? new Set(onlyArg.slice("--only=".length).split(",")) : null;

const works = JSON.parse(readFileSync(path.join(sourceDir, "works.json"), "utf-8"));
const cache = existsSync(cachePath) ? JSON.parse(readFileSync(cachePath, "utf-8")) : {};

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function queryMedia(anilistId) {
  const gql = `query ($id: Int) { Media(id: $id, type: ANIME) {
    id title { native romaji } coverImage { extraLarge large }
  } }`;
  for (let attempt = 0; attempt < 4; attempt++) {
    const res = await fetch(API, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        "User-Agent": "anime-db-fan-site/0.1 (https://izenmi.github.io/anime-db/)",
      },
      body: JSON.stringify({ query: gql, variables: { id: anilistId } }),
    });
    if (res.status === 429) {
      const wait = Number(res.headers.get("retry-after") ?? 30);
      console.log(`  429 rate limited, waiting ${wait}s...`);
      await sleep((wait + 1) * 1000);
      continue;
    }
    if (!res.ok) throw new Error(`AniList HTTP ${res.status}`);
    const payload = await res.json();
    if (payload.errors) throw new Error(`AniList errors: ${JSON.stringify(payload.errors)}`);
    return payload.data.Media;
  }
  throw new Error("rate limited repeatedly");
}

async function verifyImage(url) {
  const res = await fetch(url);
  if (!res.ok) return false;
  const type = res.headers.get("content-type") ?? "";
  if (!type.startsWith("image/")) return false;
  const buf = await res.arrayBuffer();
  return buf.byteLength > 1000;
}

function shouldFetch(w) {
  if (only && !only.has(w.id)) return false;
  const entry = cache[w.id];
  if (!entry) return true;
  if (retryMisses) return entry.coverUrl == null;
  return force;
}

const targets = works.filter((w) => shouldFetch(w));
console.log(`fetch-covers: ${targets.length} works to process (of ${works.length} total)`);

let ok = 0;
let miss = 0;
let kept = 0;
for (const w of targets) {
  if (!w.anilistId) {
    // anilistId が無い作品は取得できない。probe_anilist.py で id を確認して works.json に入れること。
    if (!cache[w.id]) cache[w.id] = { coverUrl: null, note: "anilistId未設定のため未取得" };
    console.log(`[skip] ${w.title}: anilistId not set`);
    miss++;
    continue;
  }
  try {
    const media = await queryMedia(w.anilistId);
    const url = media?.coverImage?.extraLarge ?? media?.coverImage?.large ?? null;
    if (url && (await verifyImage(url))) {
      cache[w.id] = {
        coverUrl: url,
        matchedTitle: media.title?.native ?? media.title?.romaji ?? null,
        anilistId: w.anilistId,
      };
      console.log(`[ok]   ${w.title} -> ${cache[w.id].matchedTitle}`);
      ok++;
    } else if (cache[w.id]?.coverUrl) {
      console.log(`[keep] ${w.title}: refetch failed, keeping existing cover`);
      kept++;
    } else {
      cache[w.id] = { coverUrl: null, anilistId: w.anilistId, note: "AniListに画像なし/検証失敗" };
      console.log(`[miss] ${w.title}`);
      miss++;
    }
  } catch (e) {
    if (cache[w.id]?.coverUrl) {
      console.log(`[keep] ${w.title}: ${e.message}`);
      kept++;
    } else {
      cache[w.id] = { coverUrl: null, anilistId: w.anilistId ?? null, note: `取得エラー: ${e.message}` };
      console.log(`[err]  ${w.title}: ${e.message}`);
      miss++;
    }
  }
  await sleep(SLEEP_MS);
}

writeFileSync(cachePath, JSON.stringify(cache, null, 2) + "\n", "utf-8");
console.log(`fetch-covers: done. ok=${ok} miss=${miss} keep=${kept} -> ${cachePath}`);
