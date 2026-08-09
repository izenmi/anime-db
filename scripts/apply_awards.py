#!/usr/bin/env python3
"""harvest_awards.py のTSVを works.json の awardResults に反映する。

**2段構えの1段目(既存作品への受賞歴付与)がこのスクリプトの役目**。
未一致行は捨てずに標準エラーへ出すので、2段目(未登録作品の追加)の判断に使うこと
(飛ばすと受賞歴が大量に欠落する。姉妹サイトで実際に1149件落とした事故がある)。

  python3 scripts/apply_awards.py scripts/.cache/awards.tsv --dry-run
  python3 scripts/apply_awards.py scripts/.cache/awards.tsv
"""
import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "public" / "data" / "source"
DROP = re.compile(r"[\s　ー～〜~\-−–—・,、.。!！?？:：;；'\"’”“‘()（）\[\]【】<>〈〉《》「」『』/／\\|☆★♪＊*+]")


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s).lower()
    s = re.sub(r"\(.*?\)", "", s)
    s = re.sub(r"(テレビ)?アニメ(ーション)?$", "", s)
    return DROP.sub("", s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tsv")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    works = json.loads((SRC / "works.json").read_text(encoding="utf-8"))
    by_norm = {}
    for w in works:
        by_norm.setdefault(norm(w["title"]), []).append(w)

    rows = []
    for line in Path(args.tsv).read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("--"):
            continue
        award, year, result, title = line.split("\t")
        rows.append((award, int(year), result, title))

    hits, misses, derived = 0, [], []
    per_work = {}
    for award, year, result, title in rows:
        n = norm(title)
        cand = by_norm.get(n)
        if not cand:
            # 「〜 (アニメ)」「劇場版〜」のような表記ゆれは、片方がもう片方を完全に含むときだけ拾う。
            # 短い語だと『K』が『K RETURN OF KINGS』に当たるので6文字以上に限る。
            if len(n) >= 6:
                cand = [w for k, ws in by_norm.items() if k and (k == n or (len(k) >= 6 and (n in k or k in n))) for w in ws]
        if not cand:
            # 続編・劇場版は独立エントリを作らない方針なので、本編に紐づける。
            # 受賞したのがどの期・どの劇場版かは result に残して誤解を避ける。
            # 「劇場版」「映画」の接頭辞が付くと前方一致しないので、外した形でも試す
            stripped = norm(re.sub(r"^(劇場版|映画|新劇場版)", "", title))
            if stripped in by_norm:   # 『映画 聲の形』のように本編そのものを指す表記
                w = by_norm[stripped][0]
                per_work.setdefault(w["id"], []).append(
                    {"awardId": award, "year": year, "result": result})
                hits += 1
                continue
            cands_n = [n, stripped]
            parent = None
            for base in cands_n:
                for k, ws in by_norm.items():
                    if len(k) >= 4 and base.startswith(k) and len(base) > len(k):
                        if parent is None or len(k) > len(parent[0]):
                            parent = (k, ws[0])
                if parent:
                    break
            if parent:
                w = parent[1]
                per_work.setdefault(w["id"], []).append(
                    {"awardId": award, "year": year, "result": f"{result}（{title}）"})
                hits += 1
                derived.append((title, w["title"]))
                continue
            misses.append((award, year, result, title))
            continue
        if len(cand) > 1:
            cand = sorted(cand, key=lambda w: abs((w.get("season") or {}).get("year", 9999) - year))
        w = cand[0]
        per_work.setdefault(w["id"], []).append({"awardId": award, "year": year, "result": result})
        hits += 1

    for wid, results in per_work.items():
        w = next(x for x in works if x["id"] == wid)
        existing = {(r["awardId"], r["year"], r["result"]) for r in w.get("awardResults", [])}
        merged = list(w.get("awardResults", []))
        for r in results:
            if (r["awardId"], r["year"], r["result"]) not in existing:
                merged.append(r)
                existing.add((r["awardId"], r["year"], r["result"]))
        merged.sort(key=lambda r: (r["year"], r["awardId"], r["result"]))
        w["awardResults"] = merged

    print(f"付与: {hits}件 / 対象作品 {len(per_work)}件 / 未一致 {len(misses)}件", file=sys.stderr)
    for a, b in derived:
        print(f"DERIVED\t{a}\t-> {b}", file=sys.stderr)
    for m in misses:
        print("MISS\t" + "\t".join(str(x) for x in m), file=sys.stderr)

    if not args.dry_run:
        (SRC / "works.json").write_text(
            json.dumps(works, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print("works.json を更新した", file=sys.stderr)


if __name__ == "__main__":
    main()
