#!/usr/bin/env python3
"""AniList の SEQUEL 関係を辿って、続編情報を broadcastNote に一括補完する。

シリーズ単位1エントリという方針上、第2期以降は本文ではなく broadcastNote に書く。
- SEQUEL の連鎖を辿り、TV/ONA 形式のものだけを「第N期」として番号を振る
- すでに独立した作品として works.json に登録済みの続編は、二重掲載になるので飛ばす
- 既存の broadcastNote は手書きなので上書きしない
"""
import json, pathlib, sys, time, urllib.request, urllib.error

from season_chain import load_relations, numbered_chain, save_relations, title

ROOT = pathlib.Path(__file__).resolve().parent.parent
WORKS = ROOT / "public/data/source/works.json"
UA = "anime-db/1.0 (+https://izenmi.github.io/anime-db/)"
Q = """query($ids:[Int]){Page(perPage:50){media(id_in:$ids,type:ANIME){
id format title{native romaji} startDate{year}
relations{edges{relationType node{id type format title{native romaji} startDate{year}}}}}}}"""

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
                time.sleep(int(e.headers.get("Retry-After", 60)) + 1); continue
            raise
        except Exception:
            if attempt == 4: raise
            time.sleep(5)
    return []

AUTO_SUFFIX = "が制作されている。"          # 自動生成の目印。手書きのnoteは末尾が違う

works = json.loads(WORKS.read_text(encoding="utf-8"))
registered = {w["anilistId"] for w in works if w.get("anilistId")}
info, rel = load_relations()
queue = [w["anilistId"] for w in works if w.get("anilistId")]
seen = set(rel)
while queue:
    batch = [i for i in queue if i not in seen][:25]
    if not batch: break
    seen.update(batch); queue = [i for i in queue if i not in seen]
    for m in gql(batch):
        info[m["id"]] = m
        seq = []
        for e in m.get("relations", {}).get("edges", []):
            n = e["node"]
            if e["relationType"] == "SEQUEL" and n.get("type") == "ANIME":
                seq.append(n["id"]); info.setdefault(n["id"], n)
                if n.get("format") in ("TV", "TV_SHORT", "ONA") and n["id"] not in seen:
                    queue.append(n["id"])
        rel[m["id"]] = seq
    print(f"  fetched {len(seen)} / queued {len(queue)}", file=sys.stderr)
    time.sleep(2.2)
save_relations(info, rel)

n = 0
for w in works:
    aid = w.get("anilistId")
    note = w.get("broadcastNote") or ""
    if not aid or (note and not note.endswith(AUTO_SUFFIX)):
        continue
    parts, prev_num = [], 1
    for num, m in numbered_chain(info, rel, aid, registered):
        t, y = title(m), (m.get("startDate", {}) or {}).get("year")
        label = f"『{t}』({y}年)" if y else f"『{t}』"
        if num != prev_num:
            label = f"第{num}期" + label
        parts.append(label)
        prev_num = num
    w["broadcastNote"] = "、".join(parts) + AUTO_SUFFIX if parts else None
    if w["broadcastNote"] is None: del w["broadcastNote"]
    else: n += 1
WORKS.write_text(json.dumps(works, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"broadcastNote を {n} 作品に補完 (既存 {sum(1 for w in works if w.get('broadcastNote')) - n} 件は据え置き)")
