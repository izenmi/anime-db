#!/usr/bin/env python3
"""AniListの人気順カタログから「シリーズ第1期の未登録アニメ」だけを一括収穫して候補プールを作る。

suggest_candidates.py(候補列挙)+ probe_anilist.py(1件ずつ裏取り)を1本にまとめたもの。
**1リクエストで50作品ぶんのスタジオ・スタッフ・キャスト・タグまで取り切る**ので、1000作品
規模でもAPI往復が20〜40回で済む(1件1リクエストだと1000回=40分かかる)。

使い方:
  python3 scripts/harvest_anilist.py --pages 40 [--start-page 1] [--per-page 50]
                                     [--pool scripts/.cache/pool.json]

- 既にプールにある anilistId は再取得しない(何度実行しても追記マージ)ので、
  トークン/APIが途中で切れても同じコマンドで再開できる
- 除外ルール(シリーズ単位1エントリの原則):
  * works.json に既にある(anilistId一致 or タイトル正規化一致)
  * **同フランチャイズの別エントリが既に採択済み**(タイトルの前方一致で判定。下記 same_franchise)
  * TVシリーズの劇場版・総集編(劇場版/総集編/Movie 等のマーカー)
  * 放送開始前(NOT_YET_RELEASED)・クール不明・制作スタジオ不明

**relations による続編判定は使わない**。第1期の側にも SIDE_STORY(OVA)・SUMMARY(総集編)・
PREQUEL(前日譚の劇場版)がぶら下がるため、『DEATH NOTE』『ONE PIECE』『呪術廻戦』の第1期まで
落ちてしまうことを実測で確認した(2026-08-09)。人気順で先に出てきた方を第1期とみなし、
より短いタイトルが後から来たらそちらに差し替える方が精度が高い。
"""
import json
import re
import sys
import time
import unicodedata
from pathlib import Path

from anilist import SLEEP, query

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "public" / "data" / "source"
DEFAULT_POOL = ROOT / "scripts" / ".cache" / "pool.json"

GQL = """
query ($page: Int, $perPage: Int, $country: CountryCode) {
  Page(page: $page, perPage: $perPage) {
    pageInfo { hasNextPage }
    media(type: ANIME, countryOfOrigin: $country, format_in: [TV, TV_SHORT, MOVIE],
          sort: POPULARITY_DESC) {
      id
      title { native romaji }
      format
      status
      season
      seasonYear
      episodes
      source
      popularity
      startDate { year month }
      description
      genres
      tags { name rank }
      studios(isMain: true) { nodes { name } }
      staff(perPage: 50) { edges { role node { name { native first last full } } } }
      characters(role: MAIN, perPage: 8, sort: RELEVANCE) {
        edges {
          node { name { native full } }
          voiceActors(language: JAPANESE) { name { native first last full } }
        }
      }
    }
  }
}
"""

# 監督ロールは Director / Chief Director のみ(Episode/Assistant/Sound Director を混ぜない)
DIRECTOR_ROLES = ("director", "chief director", "general director")
COMPOSER_ROLES = ("series composition",)


def role_key(role: str) -> str:
    """AniListの役職名から話数の注記を落として比較用に正規化する。

    長期シリーズは `Director (eps 1-278)` のように担当話数が付く。ここを見落とすと
    『ONE PIECE』『名探偵コナン』『銀魂』のような大作が丸ごと監督なしと判定され、
    stage が skip.json に落としてしまう(実際に140作品を取りこぼした)。
    """
    return re.sub(r"\s*\([^()]*\)\s*$", "", (role or "")).strip().lower()
# 続編であることがタイトルに書いてあるもの。前方一致判定は『地獄楽』のような短いタイトルだと
# 閾値(3文字)に届かず素通りするため、マーカーによる明示的な除外を併用する。第1期が未登録でも
# 「第2期をシリーズ代表として登録する」のは避けたいので、マーカーが出たら無条件で捨てる。
SEQUEL_TITLE_RE = re.compile(
    r"第[2-9２-９二三四五六七八九十]+期|[2-9２-９]期|セカンドシーズン|サードシーズン|ファイナルシーズン"
    r"|(?:2nd|3rd|4th|5th|second|third|fourth|final)\s+season|season\s*[2-9]|part\s*[2-9]"
    r"|\bii+\b\s*$", re.I)
# TVシリーズの劇場版・総集編は登録しない(単独の劇場作品のみ format: movie で登録する)
MOVIE_SPINOFF_RE = re.compile(
    r"劇場版|劇場編|総集編|^映画[\s　]|特別編集版|gekijou|gekijō|compilation|recap|the movie|movie \d", re.I)

SOURCE_MAP = {
    "MANGA": "manga", "COMIC": "manga", "MANHWA": "manga", "MANHUA": "manga",
    "FOUR_KOMA_MANGA": "manga", "LIGHT_NOVEL": "lightnovel", "NOVEL": "novel",
    "WEB_NOVEL": "novel", "VISUAL_NOVEL": "game", "VIDEO_GAME": "game", "GAME": "game",
    "ORIGINAL": "original", "MULTIMEDIA_PROJECT": "original",
}
STATUS_MAP = {"FINISHED": "completed", "RELEASING": "ongoing", "HIATUS": "ongoing",
              "CANCELLED": "unknown"}
GENRE_THEMES = {
    "Action": "action", "Fantasy": "fantasy", "Sci-Fi": "sci-fi", "Mecha": "robot-mecha",
    "Music": "music", "Mystery": "mystery", "Romance": "romance", "Sports": "sports",
    "Slice of Life": "slice-of-life", "Comedy": "comedy", "Horror": "horror",
    "Thriller": "suspense", "Psychological": "suspense", "Mahou Shoujo": "magical-girl",
}
TAG_THEMES = {
    "Isekai": "isekai", "Reincarnation": "isekai", "School": "school",
    "School Club": "club-activities", "Coming of Age": "youth", "Idol": "idol",
    "Cooking": "cooking", "Food": "cooking", "War": "war", "Historical": "history",
    "Ensemble Cast": "ensemble", "Travel": "journey", "Super Power": "battle",
    "Martial Arts": "battle", "Shounen": "battle", "Dark Fantasy": "dark-fantasy",
    "Work": "work", "Office Lady": "work", "Superhero": "hero", "Heroine": "hero",
    "Family Life": "family", "Parenthood": "family", "Tragedy": "tearjerker",
    "Love Triangle": "romance", "Male Harem": "romcom", "Female Harem": "romcom",
    "Primarily Female Cast": None, "Primarily Male Cast": None,
}
TAG_MIN_RANK = 60


def norm(s: str) -> str:
    return re.sub(r"[\s　・･、。,，.!！?？:：;；~〜ー\-‐−『』「」【】()（）\[\]√※'\"]", "",
                  unicodedata.normalize("NFKC", s or "")).lower()


def title_keys(s: str) -> tuple:
    """タイトルの正規化バリアントを返す。括弧の扱いが1通りだと続編を取りこぼすため2通り作る。

    - そのまま記号だけ落とした形 … 『東京喰種[トーキョーグール]√A』が『東京喰種 トーキョーグール』の
      前方一致になる
    - 括弧の中身ごと落とした形 … 『ジョジョの奇妙な冒険 (TV)』が『ジョジョの奇妙な冒険 スターダスト
      クルセイダース』と同じ根を持つと判定できる
    """
    t = unicodedata.normalize("NFKC", s or "")
    stripped = re.sub(r"[(（\[【][^)）\]】]*[)）\]】]", " ", t)
    # 語幹 = 最初の区切り記号まで。両方に副題が付く『かぐや様は告らせたい～天才たちの…』と
    # 『かぐや様は告らせたい-ウルトラロマンティック-』は前方一致では引っかからないので、
    # 副題を落とした語幹どうしでも比べる
    root = re.split(r"[\s:：~〜\-‐−[(【「『]", t.strip(), 1)[0]
    keys = {norm(t), norm(stripped)}
    root = norm(root)
    if len(root) >= 4:
        keys.add(root)
    return tuple(keys - {""})


def person(node) -> dict:
    n = (node or {}).get("name") or {}
    last, first = (n.get("last") or "").strip(), (n.get("first") or "").strip()
    # 日本のクレジット順(姓+名)に揃える。片方しか無ければ full で代用
    romaji = " ".join(x for x in (last, first) if x) or (n.get("full") or "").strip()
    return {"n": (n.get("native") or "").strip(), "r": romaji}


def quarter_of(m) -> str:
    s = (m.get("season") or "").lower()
    if s in ("winter", "spring", "summer", "fall"):
        return s
    month = ((m.get("startDate") or {}).get("month")) or 0
    return {1: "winter", 2: "winter", 3: "winter", 4: "spring", 5: "spring", 6: "spring",
            7: "summer", 8: "summer", 9: "summer", 10: "fall", 11: "fall", 12: "fall"}.get(month, "")


def themes_of(m) -> list:
    out = []
    for g in m.get("genres") or []:
        t = GENRE_THEMES.get(g)
        if t and t not in out:
            out.append(t)
    for tag in m.get("tags") or []:
        if (tag.get("rank") or 0) < TAG_MIN_RANK:
            continue
        t = TAG_THEMES.get(tag.get("name"))
        if t and t not in out:
            out.append(t)
    return out[:6]


def romaji_root(s: str) -> str:
    """『Magi: The Labyrinth of Magic』→ "magi"。副題の前までを取る。

    native側の語幹だけだと『マギ』のように2文字で閾値に届かず、同じ本編名+別副題の続編を
    取りこぼす。ローマ字の語幹が一致するかを併せて見ることで、短い邦題のシリーズも拾える。
    """
    return norm(re.split(r"[:：]|\s[-–—]\s", (s or "").strip(), 1)[0])


def _prefix_match(a, b) -> bool:
    if not a or not b:
        return False
    if a == b:
        return True
    return len(a) >= 2 and len(b) >= 2 and (a.startswith(b) or b.startswith(a))


def same_franchise(a, b) -> bool:
    """(nativeキー群, 正規化romaji) の組2つが同一シリーズか。

    片方がもう片方の前方一致になっているときだけ同一とみなす(『進撃の巨人』と
    『進撃の巨人 Season２』)。**nativeとromajiの両方で前方一致が成立すること**を要求して、
    「トリコ」と「トリコロール」のような偶然の前方一致を弾く。
    """
    an = a[0] if isinstance(a[0], (list, tuple)) else (a[0],)
    bn = b[0] if isinstance(b[0], (list, tuple)) else (b[0],)
    if not any(_prefix_match(x, y) for x in an for y in bn):
        # 前方一致しなくても、ローマ字の本編名が一致すれば同一シリーズ扱い
        # (『Magi: The Labyrinth of Magic』と『Magi: The Kingdom of Magic』)
        ar, br = a[1], b[1]
        return bool(ar) and ar == br and len(ar) >= 4
    ar, br = a[1], b[1]
    if ar and br and len(ar) >= 4 and len(br) >= 4:
        return ar.startswith(br) or br.startswith(ar)
    return True  # 片側にromajiが無い(works.jsonの登録済み作品)ときはnativeの前方一致だけで判断


def condense(m) -> dict:
    directors, composers = [], []
    for e in (m.get("staff") or {}).get("edges") or []:
        role = (e.get("role") or "").strip().lower()
        if role_key(role) in DIRECTOR_ROLES:
            directors.append(person(e["node"]))
        elif role_key(role) in COMPOSER_ROLES:
            composers.append(person(e["node"]))
    cast = []
    for e in (m.get("characters") or {}).get("edges") or []:
        vas = e.get("voiceActors") or []
        char = ((e.get("node") or {}).get("name") or {}).get("native")
        if not vas or not char:
            continue
        va = person(vas[0])
        if not va["n"] or not va["r"]:
            continue
        cast.append({"c": char.strip(), "va": va})
        if len(cast) == 5:
            break
    desc = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m.get("description") or "")).strip()
    return {
        "aid": m["id"],
        "t": (m.get("title") or {}).get("native"),
        "r": (m.get("title") or {}).get("romaji"),
        "fmt": "movie" if m.get("format") == "MOVIE" else "tv",
        "y": m.get("seasonYear") or (m.get("startDate") or {}).get("year"),
        "q": quarter_of(m),
        "ep": m.get("episodes"),
        "src": SOURCE_MAP.get(m.get("source") or "", "other"),
        "st": STATUS_MAP.get(m.get("status") or "", "unknown"),
        "studios": [s["name"] for s in ((m.get("studios") or {}).get("nodes") or []) if s.get("name")],
        "dir": [d for d in directors if d["n"] or d["r"]],
        "comp": [c for c in composers if c["n"] or c["r"]],
        "cast": cast,
        "themes": themes_of(m),
        "desc": desc[:420],
        "pop": m.get("popularity") or 0,
    }


def arg(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def main():
    pages = int(arg("--pages", "10"))
    start = int(arg("--start-page", "1"))
    per_page = int(arg("--per-page", "50"))
    pool_path = Path(arg("--pool", str(DEFAULT_POOL)))
    pool_path.parent.mkdir(parents=True, exist_ok=True)

    works = json.loads((SRC / "works.json").read_text(encoding="utf-8"))
    known_ids = {w.get("anilistId") for w in works if w.get("anilistId")}
    # 登録済み作品は「差し替え不可のフランチャイズ代表」として扱う
    locked = [(title_keys(w["title"]), norm(w.get("titleRomaji") or "")) for w in works]

    pool = json.loads(pool_path.read_text(encoding="utf-8")) if pool_path.exists() else []
    pool_ids = {p["aid"] for p in pool}

    stats = {"fetched": 0, "dup": 0, "franchise": 0, "spinoff": 0, "skip": 0,
             "new": 0, "replaced": 0}
    for page in range(start, start + pages):
        try:
            data = query(GQL, {"page": page, "perPage": per_page, "country": "JP"})
        except Exception as e:
            print(f"page {page}: ERROR {e}", flush=True)
            break
        info = (data.get("Page") or {}).get("pageInfo") or {}
        media = ((data.get("Page") or {}).get("media")) or []
        for m in media:
            stats["fetched"] += 1
            native = (m.get("title") or {}).get("native")
            romaji = (m.get("title") or {}).get("romaji") or ""
            if not native or m.get("status") == "NOT_YET_RELEASED":
                stats["skip"] += 1
                continue
            if m["id"] in known_ids or m["id"] in pool_ids:
                stats["dup"] += 1
                continue
            key = (title_keys(native), norm(romaji))
            if any(same_franchise(key, k) for k in locked):
                stats["dup"] += 1
                continue
            if SEQUEL_TITLE_RE.search(native) or SEQUEL_TITLE_RE.search(romaji):
                stats["franchise"] += 1
                continue
            if m.get("format") == "MOVIE" and (MOVIE_SPINOFF_RE.search(native)
                                               or MOVIE_SPINOFF_RE.search(romaji)):
                stats["spinoff"] += 1
                continue
            rec = condense(m)
            if not rec["y"] or not rec["q"] or not rec["studios"]:
                stats["skip"] += 1
                continue
            rec["key"] = [list(key[0]), key[1]]

            hit = next((i for i, p in enumerate(pool)
                        if same_franchise(key, (tuple(p["key"][0]), p["key"][1]))), None)
            if hit is None:
                pool.append(rec)
                pool_ids.add(rec["aid"])
                stats["new"] += 1
            elif len(max(key[0], key=len)) < len(max(pool[hit]["key"][0], key=len)):
                # 後から出てきた方がタイトルが短い = そちらが第1期。人気順の取りこぼし救済
                pool_ids.discard(pool[hit]["aid"])
                pool[hit] = rec
                pool_ids.add(rec["aid"])
                stats["replaced"] += 1
            else:
                stats["franchise"] += 1
        pool_path.write_text(json.dumps(pool, ensure_ascii=False), encoding="utf-8")
        print(f"page {page}: pool={len(pool)} {stats}", flush=True)
        if not info.get("hasNextPage"):
            print("no more pages", flush=True)
            break
        time.sleep(SLEEP)

    print(f"pool -> {pool_path} ({len(pool)} candidates) {stats}")


if __name__ == "__main__":
    main()
