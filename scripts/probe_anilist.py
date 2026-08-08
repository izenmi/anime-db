#!/usr/bin/env python3
"""AniListで候補アニメを一括裏取りする主力ツール。

使い方:
  python3 scripts/probe_anilist.py candidates.txt [--out probe.json]

candidates.txt は1行1候補:
  タイトル              … AniListを日本語タイトルで検索
  タイトル|12345        … AniList id直指定(検索の誤マッチを避けたいとき)

- **works.json との重複判定を検索の前に行い、DUP と出た候補はネットワークアクセスしない**
  (タイトルの正規化一致 or anilistId の一致)
- 検索結果からは title.native が候補と最も近いものを採用する。format が TV/TV_SHORT/MOVIE
  以外(OVA/ONA/SPECIAL/MUSIC)しか無い場合は MISS 扱いにする
- 出力(JSON配列)の各要素:
  q / status(OK|DUP|MISS) / id / native / romaji / format / seasonYear / season /
  episodes / studios(メインスタジオ名の配列) / directors / composers /
  cast([{char, va}] MAIN級最大6) / cover / popularity / description(先頭200字)
- statusがOKでも **native が候補とずれていないか必ず目視すること**(同名の続編・劇場版を
  拾うことがある)
"""
import json
import re
import sys
import time
import unicodedata
from pathlib import Path

from anilist import SLEEP, query

SRC = Path(__file__).resolve().parent.parent / "public" / "data" / "source"

GQL = """
query ($search: String, $id: Int) {
  Page(page: 1, perPage: 5) {
    media(search: $search, id: $id, type: ANIME) {
      id
      title { native romaji }
      format
      season
      seasonYear
      episodes
      popularity
      description
      coverImage { extraLarge }
      studios(isMain: true) { nodes { name } }
      staff(perPage: 25) { edges { role node { name { native full } } } }
      characters(role: MAIN, perPage: 6, sort: RELEVANCE) {
        edges {
          node { name { native full } }
          voiceActors(language: JAPANESE) { name { native full } }
        }
      }
    }
  }
}
"""

ACCEPTED_FORMATS = {"TV", "TV_SHORT", "MOVIE"}
DIRECTOR_ROLES = {"Director", "Chief Director"}
COMPOSER_ROLES = {"Series Composition"}


def norm(s: str) -> str:
    return re.sub(r"[\s　・･、。,，.!！?？:：;；~〜ー\-‐−『』「」【】()（）]", "",
                  unicodedata.normalize("NFKC", s or "")).lower()


def name_of(node) -> str:
    n = node.get("name") or {}
    return n.get("native") or n.get("full") or ""


def pick_media(media_list, target):
    """format が受理対象のものの中から、native/romaji が候補に最も近いものを選ぶ。"""
    tn = norm(target)
    best, best_score = None, -1
    for m in media_list:
        if m.get("format") not in ACCEPTED_FORMATS:
            continue
        native = norm((m.get("title") or {}).get("native") or "")
        romaji = norm((m.get("title") or {}).get("romaji") or "")
        if tn and (tn == native or tn == romaji):
            score = 100
        elif tn and (tn in native or native in tn):
            score = 50 - abs(len(native) - len(tn))
        else:
            score = 0 - abs(len(native) - len(tn))
        if score > best_score:
            best, best_score = m, score
    return best


def summarize(q, m):
    directors, composers = [], []
    for e in (m.get("staff") or {}).get("edges") or []:
        role = (e.get("role") or "").strip()
        if role in DIRECTOR_ROLES:
            directors.append(name_of(e["node"]))
        elif role in COMPOSER_ROLES:
            composers.append(name_of(e["node"]))
    cast = []
    for e in (m.get("characters") or {}).get("edges") or []:
        vas = e.get("voiceActors") or []
        if not vas:
            continue
        cast.append({"char": name_of(e["node"]), "va": name_of(vas[0])})
    desc = re.sub(r"<[^>]+>", "", m.get("description") or "")[:200]
    return {
        "q": q,
        "status": "OK",
        "id": m["id"],
        "native": (m.get("title") or {}).get("native"),
        "romaji": (m.get("title") or {}).get("romaji"),
        "format": m.get("format"),
        "seasonYear": m.get("seasonYear"),
        "season": m.get("season"),
        "episodes": m.get("episodes"),
        "studios": [s["name"] for s in ((m.get("studios") or {}).get("nodes") or [])],
        "directors": directors,
        "composers": composers,
        "cast": cast,
        "cover": (m.get("coverImage") or {}).get("extraLarge"),
        "popularity": m.get("popularity"),
        "description": desc,
    }


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    out_path = None
    if "--out" in sys.argv:
        out_path = Path(sys.argv[sys.argv.index("--out") + 1])

    works = json.loads((SRC / "works.json").read_text(encoding="utf-8"))
    existing_titles = {norm(w["title"]) for w in works}
    existing_ids = {w.get("anilistId") for w in works if w.get("anilistId")}

    lines = [ln.strip() for ln in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines()]
    results = []
    for ln in lines:
        if not ln or ln.startswith("#"):
            continue
        title, _, id_part = ln.partition("|")
        title = title.strip()
        anilist_id = int(id_part) if id_part.strip().isdigit() else None

        if norm(title) in existing_titles or (anilist_id and anilist_id in existing_ids):
            results.append({"q": ln, "status": "DUP"})
            print(f"DUP  {title}", flush=True)
            continue

        variables = {"id": anilist_id} if anilist_id else {"search": title}
        try:
            data = query(GQL, variables)
        except Exception as e:
            results.append({"q": ln, "status": "MISS", "error": str(e)})
            print(f"ERR  {title}: {e}", flush=True)
            time.sleep(SLEEP)
            continue
        media = ((data.get("Page") or {}).get("media")) or []
        best = pick_media(media, title)
        if not best:
            results.append({"q": ln, "status": "MISS"})
            print(f"MISS {title}", flush=True)
        else:
            r = summarize(ln, best)
            results.append(r)
            print(
                f"OK   {title} -> {r['native']} ({r['format']} {r['seasonYear']} {r['season']}, "
                f"ep{r['episodes']}, {'/'.join(r['studios'])}, 監督:{'/'.join(r['directors'])})",
                flush=True,
            )
        time.sleep(SLEEP)

    if out_path:
        out_path.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"wrote {out_path} ({len(results)} entries)")


if __name__ == "__main__":
    main()
