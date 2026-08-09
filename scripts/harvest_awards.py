#!/usr/bin/env python3
"""Wikipedia日本語版から5賞の「作品に対する賞」だけを抜き出してTSVにする。

賞ページは表形式とは限らず、5賞とも書式がばらばらなので賞ごとに専用の抽出を書いてある
(姉妹サイトの award_wiki.py は表形式専用。こちらは箇条書き・テンプレート形式も扱う)。
キャラクター賞・声優賞・監督賞のような**作品以外に与えられる賞は対象外**。

  python3 scripts/harvest_awards.py > scripts/.cache/awards.tsv

出力: <awardId>\t<year>\t<result>\t<title>
"""
import re
import sys
import urllib.parse
import urllib.request

from award_wiki import clean_cell, parse_tables

UA = "anime-db-award/1.0 (+https://izenmi.github.io/anime-db/)"


def raw(page: str) -> str:
    url = "https://ja.wikipedia.org/wiki/" + urllib.parse.quote(page) + "?action=raw"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8")


def section(text: str, heading_re: str) -> str:
    """=== 見出し === から次の同レベル以上の見出しまでを切り出す。"""
    m = re.search(rf"^(=+) *{heading_re} *=+$", text, re.M)
    if not m:
        return ""
    depth = len(m.group(1))
    rest = text[m.end():]
    nxt = re.search(rf"^={{1,{depth}}} [^=]", rest, re.M)
    return rest[: nxt.start()] if nxt else rest


def titles_in(s: str):
    """『』で囲まれた作品名を取り出す。無ければリンク・素のテキストを1件として返す。"""
    out = [clean_cell(x) for x in re.findall(r"『(.+?)』", s)]
    if not out:
        t = clean_cell(s)
        # 「作品名（スタジオ名）」「作品名 — スタジオ名」の後半を落とす。
        # 区切りは前後に空白のあるダッシュだけを見る(『劇場版 PSYCHO-PASS』のような
        # 作品名内のハイフンで切ってしまわないため)。
        t = re.sub(r"\s+[—–]\s*.+$", "", t)
        t = re.sub(r"\s+-\s+.+$", "", t)
        t = re.sub(r"（[^（）]*）$", "", t).strip()
        if t:
            out = [t]
    return [t for t in out if t]


def tokyo_anime_award():
    t = raw("東京アニメアワード")
    body = section(t, r"アニメーション オブ ザ イヤー")
    for line in body.splitlines():
        if not line.startswith("* "):
            continue
        m = re.match(r"\* *(\d{4})年[^：:]*[：:](.*)", line)
        if not m:
            continue
        year, rest = int(m.group(1)), m.group(2)
        for title in titles_in(rest):
            yield ("tokyo-anime-award", year, "アニメ オブ ザ イヤー", title)


def animage_grand_prix():
    t = raw("アニメグランプリ")
    body = section(t, r"グランプリ作品部門1位")
    for grid in parse_tables(body):
        for row in grid:
            if len(row) < 2:
                continue
            m = re.search(r"(\d{4})", row[0])
            if not m or "回" not in row[0]:
                continue
            for title in titles_in(row[1]):
                yield ("animage-grand-prix", int(m.group(1)), "グランプリ", title)


def newtype_anime_award():
    t = raw("ニュータイプアニメアワード")
    year = None
    for line in t.splitlines():
        if re.match(r"^=+ *.*アニメアワード", line):
            # 「アニメアワード2016 - 2017」のように会期をまたぐ見出しがあるので、
            # 見出し中の最後の年(=授賞式の年)を採る。
            ys = re.findall(r"(\d{4})", line)
            if ys:
                year = int(ys[-1])
            continue
        m = re.match(r"\* *(作品賞[^：:]*)[：:](.*)", line)
        if not m or year is None:
            continue
        result = clean_cell(m.group(1)).replace("（", "(").replace("）", ")")
        for title in titles_in(m.group(2)):
            yield ("newtype-anime-award", year, result, title)


def japan_media_arts_festival():
    """回・年度がrowspanで結合された表。大賞は '''太字''' で示されている。"""
    t = raw("文化庁メディア芸術祭アニメーション部門")
    body = section(t, r"大賞・優秀賞")
    for grid in parse_tables(body):
        for row in grid:
            if len(row) < 3:
                continue
            m = re.search(r"^(\d{4})$", row[1].strip())
            if not m:
                continue
            cell = row[2]
            result = "大賞" if "'''" in cell else "優秀賞"
            name = re.sub(r"（[^（）]*）\s*$", "", clean_cell(cell)).strip()
            if name:
                yield ("japan-media-arts-festival", int(m.group(1)), result, name)


def crunchyroll_anime_awards():
    """{{Award category|色|部門名}} の直後の箇条書きのうち、太字の行が受賞作。"""
    t = raw("クランチロール・アニメアワード")
    year, category = None, None
    for line in t.splitlines():
        h = re.match(r"^=+ *第\d+回（(\d{4})年） *=+$", line)
        if h:
            year = int(h.group(1))
            continue
        c = re.search(r"\{\{Award category\|[^|]*\|([^}]*)\}\}", line)
        if c:
            category = clean_cell(c.group(1))
            continue
        if not line.startswith("* ") or year is None or category is None:
            continue
        if "'''" not in line:  # 受賞作以外(ノミネート)は取らない
            continue
        # 作品に与えられる賞だけを対象にする
        if not re.search(r"アニメ・オブ・ザ・イヤー|作品賞|アニメーション賞", category):
            continue
        for title in titles_in(line[2:]):
            yield ("crunchyroll-anime-awards", year, category, title)


SOURCES = [
    tokyo_anime_award,
    animage_grand_prix,
    newtype_anime_award,
    japan_media_arts_festival,
    crunchyroll_anime_awards,
]

if __name__ == "__main__":
    n = 0
    for fn in SOURCES:
        rows = list(fn())
        print(f"{fn.__name__}: {len(rows)}", file=sys.stderr)
        for r in rows:
            print("\t".join(str(x) for x in r))
            n += 1
    print(f"-- total {n}", file=sys.stderr)
