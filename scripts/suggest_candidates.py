#!/usr/bin/env python3
"""AniListのカタログに「人気順で、まだworks.jsonに無いTVアニメ」を列挙させる。

**候補タイトルを自分で思いつくのはやめる**(姉妹サイト共通の教訓)。カタログ側に列挙させれば
出てくるものは全て実在し、重複も事前に除ける。game-db の suggest-candidates.mjs (IGDB版)、
mystery-db の suggest_candidates.py (楽天版) と同じ発想の AniList 版。

使い方:
  python3 scripts/suggest_candidates.py out.txt [--pages 4] [--offset-page 1]
      [--format TV|MOVIE] [--country JP]

- sort: POPULARITY_DESC(AniListユーザーの登録数順。日本国内の人気と完全には一致しないが
  裏取り済みカタログとしては十分)
- 1ページ50件。--offset-page を増やすと知名度の低い層に降りられる
- 出力: タイトル|anilistId 形式(そのまま probe_anilist.py に渡せる)。
  title.native がnullの作品(未放送など)はスキップする
- 重複判定はタイトル正規化一致とanilistId一致の両方。**日本語の別表記(『Re:ゼロ〜』の
  記号ゆれ等)はすり抜けることがある**ので、最後の防波堤は apply_batch.py のid衝突検出
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
query ($page: Int, $format: MediaFormat, $country: CountryCode) {
  Page(page: $page, perPage: 50) {
    media(type: ANIME, format: $format, countryOfOrigin: $country, sort: POPULARITY_DESC) {
      id
      title { native }
      format
      seasonYear
      popularity
    }
  }
}
"""


def norm(s: str) -> str:
    return re.sub(r"[\s　・･、。,，.!！?？:：;；~〜ー\-‐−『』「」【】()（）]", "",
                  unicodedata.normalize("NFKC", s or "")).lower()


def arg(name, default):
    if name in sys.argv:
        return sys.argv[sys.argv.index(name) + 1]
    return default


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    out_path = Path(sys.argv[1])
    pages = int(arg("--pages", "4"))
    offset_page = int(arg("--offset-page", "1"))
    fmt = arg("--format", "TV")
    country = arg("--country", "JP")

    works = json.loads((SRC / "works.json").read_text(encoding="utf-8"))
    existing_titles = {norm(w["title"]) for w in works}
    existing_ids = {w.get("anilistId") for w in works if w.get("anilistId")}

    lines, seen = [], set()
    for page in range(offset_page, offset_page + pages):
        data = query(GQL, {"page": page, "format": fmt, "country": country})
        media = ((data.get("Page") or {}).get("media")) or []
        for m in media:
            native = (m.get("title") or {}).get("native")
            if not native:
                continue
            key = norm(native)
            if key in seen or key in existing_titles or m["id"] in existing_ids:
                continue
            seen.add(key)
            lines.append(f"{native}|{m['id']}")
        print(f"page {page}: {len(media)} fetched, {len(lines)} new so far", flush=True)
        time.sleep(SLEEP)

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out_path} ({len(lines)} candidates)")


if __name__ == "__main__":
    main()
