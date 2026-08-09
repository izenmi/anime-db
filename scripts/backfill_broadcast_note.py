#!/usr/bin/env python3
"""AniList の SEQUEL 関係を辿って、続編情報を broadcastNote に一括補完する。

シリーズ単位1エントリという方針上、第2期以降は本文ではなく broadcastNote に書く。
- SEQUEL の連鎖を辿り、TV/ONA 形式のものだけを「第N期」として番号を振る
- すでに独立した作品として works.json に登録済みの続編は、二重掲載になるので飛ばす
- 既存の broadcastNote は手書きなので上書きしない
"""
import json, pathlib, re, sys, time, urllib.request, urllib.error

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
CACHE = pathlib.Path(__file__).resolve().parent / ".cache/relations.json"

works = json.loads(WORKS.read_text(encoding="utf-8"))
registered = {w["anilistId"] for w in works if w.get("anilistId")}
info, rel = {}, {}
if CACHE.exists():
    c = json.loads(CACHE.read_text(encoding="utf-8"))
    info = {int(k): v for k, v in c["info"].items()}
    rel = {int(k): v for k, v in c["rel"].items()}
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
CACHE.write_text(json.dumps({"info": info, "rel": rel}, ensure_ascii=False), encoding="utf-8")

def title(m):
    return (m.get("title") or {}).get("native") or (m.get("title") or {}).get("romaji") or ""

def chain(aid):
    """SEQUEL を辿って TV/ONA の続編だけを順に返す。分岐は最も古いものを選ぶ。"""
    out, cur, guard = [], aid, 0
    while guard < 12:
        guard += 1
        nxt = [info[i] for i in rel.get(cur, []) if i in info
               and info[i].get("format") in ("TV", "TV_SHORT", "ONA")]
        if not nxt: break
        nxt.sort(key=lambda m: (m.get("startDate", {}) or {}).get("year") or 9999)
        out.append(nxt[0]); cur = nxt[0]["id"]
    return out

COUR_RE = re.compile(r"クール|cour|part\s*[2-9]", re.I)
SEASON_NO_RE = re.compile(r"^[\s:：\-‐−~〜]*(?:[0-9０-９]+|[IViv]+|[Ⅰ-Ⅹ]+|nd|rd|th)[\s]*$")


def is_new_season(prev, cur):
    """前作と別クールでなく「別の期」と言えるか。

    分割クール(『◯◯ 承』→『◯◯ 転』のような続き)を第3期と数えてしまうのを防ぐ。
    共通接頭辞が長いのに残りが数字だけなら、それは期数表記なので新しい期として扱う。
    """
    a, b = title(prev), title(cur)
    if COUR_RE.search(b):
        return False
    i = 0
    while i < min(len(a), len(b)) and a[i] == b[i]:
        i += 1
    if i < 5 or i / min(len(a), len(b)) < 0.6:
        return True
    # 接頭辞が一致していても、残りが「2」「Ⅱ」のような期数表記なら別の期
    return bool(SEASON_NO_RE.match(b[i:]))


n = 0
for w in works:
    aid = w.get("anilistId")
    note = w.get("broadcastNote") or ""
    if not aid or (note and not note.endswith(AUTO_SUFFIX)):
        continue
    parts, num, prev = [], 1, None
    for m in chain(aid):
        if m["id"] in registered: break   # 別エントリとして登録済みなら重複するので止める
        t, y = title(m), (m.get("startDate", {}) or {}).get("year")
        if not t: break
        label = f"『{t}』({y}年)" if y else f"『{t}』"
        if prev is None or is_new_season(prev, m):
            num += 1
            label = f"第{num}期" + label
        parts.append(label)
        prev = m
    w["broadcastNote"] = "、".join(parts) + AUTO_SUFFIX if parts else None
    if w["broadcastNote"] is None: del w["broadcastNote"]
    else: n += 1
WORKS.write_text(json.dumps(works, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"broadcastNote を {n} 作品に補完 (既存 {sum(1 for w in works if w.get('broadcastNote')) - n} 件は据え置き)")
