"""AniList の SEQUEL 連鎖から「第N期」を数える共通ロジック。

backfill_broadcast_note.py(続編情報の文章)と backfill_seasons.py(期数・最新クール)の
両方がここを使う。番号の振り方が2本でずれると、カードの「全4期」と本文の「第2期…」が
食い違うので、判定は必ずこの1か所に置く。

`info` / `rel` は scripts/.cache/relations.json の中身(backfill_broadcast_note.py が作る)。
"""
import json
import pathlib
import re

CACHE = pathlib.Path(__file__).resolve().parent / ".cache/relations.json"

COUR_RE = re.compile(r"クール|cour|part\s*[2-9]", re.I)
SEASON_NO_RE = re.compile(r"^[\s:：\-‐−~〜]*(?:[0-9０-９]+|[IViv]+|[Ⅰ-Ⅹ]+|nd|rd|th)[\s]*$")


def load_relations():
    """(info, rel) を返す。キャッシュがなければ空。int キーに直して返す。"""
    if not CACHE.exists():
        return {}, {}
    c = json.loads(CACHE.read_text(encoding="utf-8"))
    return ({int(k): v for k, v in c["info"].items()}, {int(k): v for k, v in c["rel"].items()})


def save_relations(info, rel):
    CACHE.write_text(json.dumps({"info": info, "rel": rel}, ensure_ascii=False), encoding="utf-8")


def title(m):
    return (m.get("title") or {}).get("native") or (m.get("title") or {}).get("romaji") or ""


def chain(info, rel, aid):
    """SEQUEL を辿って TV/ONA の続編だけを順に返す。分岐は最も古いものを選ぶ。"""
    out, cur, guard = [], aid, 0
    while guard < 12:
        guard += 1
        nxt = [info[i] for i in rel.get(cur, []) if i in info
               and info[i].get("format") in ("TV", "TV_SHORT", "ONA")]
        if not nxt:
            break
        nxt.sort(key=lambda m: (m.get("startDate", {}) or {}).get("year") or 9999)
        out.append(nxt[0])
        cur = nxt[0]["id"]
    return out


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


def numbered_chain(info, rel, aid, registered):
    """[(期数, media), ...] を返す。第1期(aid 自身)は含まない。

    - 別エントリとして works.json に登録済みの続編に当たったらそこで打ち切る(二重掲載になるため)
    - 分割クールの続きは期数を増やさず、前の期と同じ番号のまま返す
    """
    out, num, prev = [], 1, None
    for m in chain(info, rel, aid):
        if m["id"] in registered:
            break
        if not title(m):
            break
        if prev is None or is_new_season(prev, m):
            num += 1
        out.append((num, m))
        prev = m
    return out
