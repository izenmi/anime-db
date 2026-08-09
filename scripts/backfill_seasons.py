#!/usr/bin/env python3
"""シリーズの期数(`seasonCount`)と最新シーズンのクール(`latestSeason`)を一括補完する。

`season` は第1期の放送開始クールなので、長寿シリーズほど作品一覧に出る日付が古くなる。
一覧では「いま何期まで来ていて、最新シーズンはいつだったか」のほうが見たい情報なので、
broadcastNote と同じ SEQUEL 連鎖(season_chain.py)から機械的に求めて works.json に持たせる。

- 期数の数え方は backfill_broadcast_note.py と完全に同じ(season_chain.numbered_chain)。
  「全4期」とnoteの「第4期『…』」が食い違わないよう、判定はあの1か所しかない
- 続編のクールは AniList の `season`/`seasonYear` を使う。無ければ startDate の月から割り出す
- `seasonCount` は2以上のときだけ、`latestSeason` は `season` と違うときだけ書く
  (単発作品に冗長なフィールドを増やさないため。読み手側は `?? 1` / `?? season` で補う)

前提: scripts/.cache/relations.json が最新であること。先に backfill_broadcast_note.py を流す。
"""
import json
import pathlib
import sys
import time
import urllib.error
import urllib.request

from season_chain import load_relations, numbered_chain

ROOT = pathlib.Path(__file__).resolve().parent.parent
WORKS = ROOT / "public/data/source/works.json"
CACHE = pathlib.Path(__file__).resolve().parent / ".cache/seasons.json"
UA = "anime-db/1.0 (+https://izenmi.github.io/anime-db/)"
Q = """query($ids:[Int]){Page(perPage:50){media(id_in:$ids,type:ANIME){
id season seasonYear startDate{year month}}}}"""

QUARTERS = ["winter", "spring", "summer", "fall"]
QUARTER_OF_ENUM = {"WINTER": "winter", "SPRING": "spring", "SUMMER": "summer", "FALL": "fall"}


def gql(ids):
    body = json.dumps({"query": Q, "variables": {"ids": ids}}).encode()
    req = urllib.request.Request("https://graphql.anilist.co", data=body,
        headers={"Content-Type": "application/json", "User-Agent": UA})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)["data"]["Page"]["media"]
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(int(e.headers.get("Retry-After", 60)) + 1)
                continue
            raise
        except Exception:
            if attempt == 4:
                raise
            time.sleep(5)
    return []


def quarter_of(m):
    """AniList の season enum を優先し、無ければ開始月から割り出す。年が無ければ None。"""
    q = QUARTER_OF_ENUM.get(m.get("season") or "")
    start = m.get("startDate") or {}
    year = m.get("seasonYear") or start.get("year")
    if not year:
        return None
    if not q:
        month = start.get("month")
        if not month:
            return None
        q = QUARTERS[(month - 1) // 3]
    return {"year": year, "quarter": q}


def sort_key(s):
    return s["year"] * 4 + QUARTERS.index(s["quarter"])


works = json.loads(WORKS.read_text(encoding="utf-8"))
registered = {w["anilistId"] for w in works if w.get("anilistId")}
info, rel = load_relations()

# 各作品の期数と、クールを引きたい続編のidを先に洗い出す
chains = {}
wanted = set()
for w in works:
    aid = w.get("anilistId")
    if not aid:
        continue
    entries = numbered_chain(info, rel, aid, registered)
    if not entries:
        continue
    chains[w["id"]] = entries
    wanted.update(m["id"] for _, m in entries)

seasons = {}
if CACHE.exists():
    seasons = {int(k): v for k, v in json.loads(CACHE.read_text(encoding="utf-8")).items()}
todo = sorted(wanted - set(seasons))
print(f"続編 {len(wanted)} 件中 {len(todo)} 件をAniListに問い合わせ", file=sys.stderr)
for i in range(0, len(todo), 50):
    batch = todo[i:i + 50]
    for m in gql(batch):
        seasons[m["id"]] = quarter_of(m)
    for mid in batch:                    # 応答に含まれなかったidも記録して再問い合わせを防ぐ
        seasons.setdefault(mid, None)
    print(f"  {min(i + 50, len(todo))} / {len(todo)}", file=sys.stderr)
    time.sleep(2.2)
CACHE.write_text(json.dumps(seasons, ensure_ascii=False), encoding="utf-8")

n_count = n_latest = 0
for w in works:
    entries = chains.get(w["id"], [])
    count = max((num for num, _ in entries), default=1)
    latest = w["season"]
    for _, m in entries:
        s = seasons.get(m["id"])
        if s and sort_key(s) > sort_key(latest):
            latest = s
    for key in ("seasonCount", "latestSeason"):
        w.pop(key, None)
    if count > 1:
        w["seasonCount"] = count
        n_count += 1
    if latest is not w["season"]:
        w["latestSeason"] = latest
        n_latest += 1

WORKS.write_text(json.dumps(works, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"seasonCount を {n_count} 作品、latestSeason を {n_latest} 作品に付与")
