#!/usr/bin/env python3
"""候補プールのうち監督(と構成)が取れていないものを、AniListのstaff次ページから補完する。

AniListの `staff` は1ページ最大50件で、**sort を指定しないと関連度順にならず**
監督が後ろのページへ落ちる(既定順のまま引いていたせいで『負けヒロインが多すぎる!』などを
取りこぼしていた)。人気作は RELEVANCE 順にしてもページ外に出ることがある
(CLAUDE.md記載の既知の落とし穴。実測でも上位26件中13件が空だった)。1件ずつ引くと
1000作品で30分以上かかるので、**`media(id_in: [...])` で25作品ぶんをまとめて**引き、
ページ2,3,4… と必要な作品だけを追いかける。

使い方:
  python3 scripts/fill_directors.py [--pool scripts/.cache/pool.json] [--max-page 5]
"""
import json
import sys
import time
from pathlib import Path

from anilist import SLEEP, query
from harvest_anilist import COMPOSER_ROLES, DIRECTOR_ROLES, DEFAULT_POOL, person, role_key

GQL = """
query ($ids: [Int], $page: Int) {
  Page(page: 1, perPage: 50) {
    media(id_in: $ids, type: ANIME) {
      id
      staff(page: $page, perPage: 50, sort: RELEVANCE) {
        pageInfo { hasNextPage }
        edges { role node { name { native first last full } } }
      }
    }
  }
}
"""
CHUNK = 25


def arg(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def main():
    pool_path = Path(arg("--pool", str(DEFAULT_POOL)))
    max_page = int(arg("--max-page", "5"))
    pool = json.loads(pool_path.read_text(encoding="utf-8"))
    by_id = {p["aid"]: p for p in pool}

    todo = [p["aid"] for p in pool if not p["dir"]]
    print(f"{len(todo)}/{len(pool)} entries missing a director", flush=True)

    # 1ページ目もやり直す。harvest 時点の役職判定が `Director (eps 1-278)` を
    # 取りこぼしていたため、1ページ目に監督がいる長期シリーズが埋まっていない。
    page = int(arg("--from-page", "1"))
    while todo and page <= max_page:
        still, more_pages = [], False
        for i in range(0, len(todo), CHUNK):
            ids = todo[i:i + CHUNK]
            try:
                data = query(GQL, {"ids": ids, "page": page})
            except Exception as e:
                print(f"  chunk error (page {page}): {e}", flush=True)
                still.extend(ids)
                time.sleep(SLEEP)
                continue
            got = {}
            for m in ((data.get("Page") or {}).get("media")) or []:
                rec = by_id.get(m["id"])
                if not rec:
                    continue
                staff = m.get("staff") or {}
                for e in staff.get("edges") or []:
                    role = role_key(e.get("role"))
                    if role in DIRECTOR_ROLES:
                        rec["dir"].append(person(e["node"]))
                    elif role in COMPOSER_ROLES and not rec["comp"]:
                        rec["comp"].append(person(e["node"]))
                got[m["id"]] = (staff.get("pageInfo") or {}).get("hasNextPage")
            for aid in ids:
                if by_id[aid]["dir"]:
                    continue
                if got.get(aid):
                    still.append(aid)
                    more_pages = True
            print(f"  page {page} chunk {i // CHUNK + 1}: resolved so far "
                  f"{sum(1 for p in pool if p['dir'])}/{len(pool)}", flush=True)
            time.sleep(SLEEP)
        pool_path.write_text(json.dumps(pool, ensure_ascii=False), encoding="utf-8")
        todo = still
        page += 1
        if not more_pages:
            break

    missing = [p["t"] for p in pool if not p["dir"]]
    print(f"done. still missing director: {len(missing)}")
    for t in missing[:40]:
        print(f"  - {t}")


if __name__ == "__main__":
    main()
