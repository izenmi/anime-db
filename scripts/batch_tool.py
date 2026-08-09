#!/usr/bin/env python3
"""候補プール → apply_batch.py に食わせるバッチJSON を組み立てる2段ツール。

1000作品規模の投入でモデル(=私)が書く必要があるものを**あらすじだけ**に絞り込むのが目的。
人名・作品名のかなは AniList のローマ字表記から機械変換し(jp_romaji)、原作種別・放送クール・
テーマ・話数・スタジオ・監督・キャストは AniList の値をそのまま機械的に写す。

  stage:    プールから未投入の N 件を取り出し、あらすじ以外を埋めた batchNNN.json と、
            人手で埋める項目だけを並べた batchNNN.ask.txt を書く
  finalize: batchNNN.meta.json(あらすじ等)を合流させて apply_batch.py を実行する

使い方:
  python3 scripts/batch_tool.py stage 40
  python3 scripts/batch_tool.py finalize 1

- 消費済み判定は works.json の anilistId(applyされた時点で自動的に消える)+ .cache/skip.json
- 監督が取れていない候補は stage が skip.json に落として次へ進む(directorIds は必須のため)
"""
import json
import os.path
import re
import subprocess
import sys
from pathlib import Path

from harvest_anilist import (MOVIE_SPINOFF_RE, SEQUEL_TITLE_RE, norm, romaji_root,
                             same_franchise, title_keys)
from jp_romaji import person_slug, romaji_to_hiragana, slug

# `--force 1254,235` でフランチャイズ判定を素通しさせるaid。派生作品が先に登録されて
# 本編が弾かれるケース(『聖闘士星矢』など)の逃げ道。
FORCED_AIDS = {int(x) for x in (
    sys.argv[sys.argv.index("--force") + 1] if "--force" in sys.argv else ""
).split(",") if x.strip()}

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "public" / "data" / "source"
CACHE = ROOT / "scripts" / ".cache"
POOL = CACHE / "pool.json"
APPLIED = CACHE / "applied_keys.json"
SKIP = CACHE / "skip.json"
STUDIO_KANA = ROOT / "scripts" / "studio_kana.json"
STUDIO_ALIAS = ROOT / "scripts" / "studio_alias.json"
PERSON_ALIAS = ROOT / "scripts" / "person_alias.json"
TODAY = "2026-08-09"
SOURCE_NOTE = ("スタジオ・監督・シリーズ構成・主要キャスト・放送クール・話数はAniList(id:{aid})の"
               "クレジットで確認(2026-08-09取得)。あらすじは独自要約(コピペなし、核心の展開には"
               "触れていない)。続編・劇場版などのシリーズ展開は未検証のため記載していない。")


def load(name):
    return json.loads((SRC / f"{name}.json").read_text(encoding="utf-8"))


def read_json(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def kana_of(romaji, native):
    k = romaji_to_hiragana(romaji)
    if k:
        return k
    # AniListのromajiが姓名逆・欠落のときは native をそのまま返せないので手動送り
    return None


# ---------------------------------------------------------------- stage
def stage(count):
    pool = read_json(POOL, [])
    skip = set(read_json(SKIP, []))
    works = load("works")
    staff, studios, vas = load("staff"), load("studios"), load("voiceActors")
    studio_kana = read_json(STUDIO_KANA, {})
    studio_alias = read_json(STUDIO_ALIAS, {})
    person_alias = read_json(PERSON_ALIAS, {})

    done_ids = {w.get("anilistId") for w in works if w.get("anilistId")}
    work_ids = {w["id"] for w in works}
    # harvest時点のプールには「その後に登録された作品の続編」が残っている。works.jsonは
    # バッチごとに育つので、**適用直前にもう一度フランチャイズ判定をかける**のが最後の砦。
    # works.json はローマ字題を持たないので、投入済み作品のキーを別ファイルに覚えておく
    applied = read_json(APPLIED, {})
    locked = [(title_keys(w["title"]), applied.get(w["id"], {}).get("rr", "")) for w in works]
    staff_by_name = {s["name"]: s["id"] for s in staff}
    studio_by_name = {s["name"]: s["id"] for s in studios}
    va_by_name = {v["name"]: v["id"] for v in vas}
    used_staff_ids = {s["id"] for s in staff}
    used_studio_ids = {s["id"] for s in studios}
    used_va_ids = {v["id"] for v in vas}

    batch = {"newStaff": [], "newStudios": [], "newVoiceActors": [], "works": []}
    ask, need_studio_kana, newly_skipped = [], {}, []
    seen_person, seen_studio = {}, {}

    def person_id(p, pool_by_name, used_ids, taken):
        """既存の同名人物がいればそのidを、いなければ新規idを返す。(id, is_new)"""
        name = p["n"] or p["r"]
        if name in person_alias:
            return person_alias[name], False
        if name in pool_by_name:
            return pool_by_name[name], False
        if name in taken:
            return taken[name], False
        base = person_slug(p["r"]) or person_slug(p["n"])
        if not base:
            return None, False
        cand, i = base, 2
        while cand in used_ids:
            cand, i = f"{base}-{i}", i + 1
        used_ids.add(cand)
        taken[name] = cand
        return cand, True

    for rec in pool:
        if len(batch["works"]) >= count:
            break
        aid = rec["aid"]
        if aid in done_ids or aid in skip:
            continue
        if not rec["dir"]:
            newly_skipped.append(aid)
            continue
        if SEQUEL_TITLE_RE.search(rec["t"]) or SEQUEL_TITLE_RE.search(rec["r"] or ""):
            newly_skipped.append(aid)
            continue
        cand_key = (title_keys(rec["t"]), romaji_root(rec["r"]))
        # --force に挙げたaidはフランチャイズ判定を通す。『聖闘士星矢』(TV)のように
        # 派生の劇場版が先に登録されたせいで本編が弾かれる場合に使う。
        forced = FORCED_AIDS
        if rec["aid"] not in forced and any(same_franchise(cand_key, k) for k in locked):
            newly_skipped.append(aid)
            continue
        # 『青春ブタ野郎はゆめみる少女の夢を見ない』のようにマーカーの無いTVシリーズの劇場版は、
        # 既存作品と長い共通接頭辞を持つことで見分ける(単独の劇場作品は普通そうならない)
        # 『映画 ギヴン』『映画けいおん!』のようにマーカー付きの劇場版はここでも落とす
        # (harvest後にルールを足したぶん、プールに残っている候補を拾うため)
        if rec["fmt"] == "movie" and (MOVIE_SPINOFF_RE.search(rec["t"])
                                      or MOVIE_SPINOFF_RE.search(rec["r"] or "")):
            newly_skipped.append(aid)
            continue
        # 『映画 ゆるキャン△』のように接頭辞が付くとそのままでは既存作品と突合できないので、
        # 先頭の「映画」「劇場版」を外した形でも比べる
        movie_titles = {norm(rec["t"]),
                        norm(re.sub(r"^(映画|劇場版)[\s　]*", "", rec["t"]))}
        # 共通接頭辞6文字だと『映画けいおん!』(けいおん=4文字)を取りこぼすので、完全一致も見る
        if rec["fmt"] == "movie" and any(
                t == norm(w["title"]) or len(os.path.commonprefix([t, norm(w["title"])])) >= 6
                for t in movie_titles for w in works):
            newly_skipped.append(aid)
            continue

        wid_base = slug(rec["r"]) or slug(rec["t"])
        if not wid_base:
            newly_skipped.append(aid)
            continue
        wid, i = wid_base, 2
        while wid in work_ids:
            wid, i = f"{wid_base}-{rec['y']}" if i == 2 else f"{wid_base}-{i}", i + 1
        work_ids.add(wid)

        director_ids, composer_ids = [], []
        for p in rec["dir"][:2]:
            pid, is_new = person_id(p, staff_by_name, used_staff_ids, seen_person)
            if not pid:
                continue
            if is_new:
                batch["newStaff"].append({
                    "id": pid, "name": p["n"] or p["r"],
                    "nameKana": kana_of(p["r"], p["n"]) or "", "description": "アニメーション監督。",
                    "externalLinks": {},
                    "sourceNote": "AniListの作品クレジット(2026-08-09取得)から登録。",
                    "updatedAt": TODAY})
            if pid not in director_ids:
                director_ids.append(pid)
        for p in rec["comp"][:2]:
            pid, is_new = person_id(p, staff_by_name, used_staff_ids, seen_person)
            if not pid:
                continue
            if is_new:
                batch["newStaff"].append({
                    "id": pid, "name": p["n"] or p["r"],
                    "nameKana": kana_of(p["r"], p["n"]) or "", "description": "脚本家。",
                    "externalLinks": {},
                    "sourceNote": "AniListの作品クレジット(2026-08-09取得)から登録。",
                    "updatedAt": TODAY})
            if pid not in composer_ids:
                composer_ids.append(pid)
        if not director_ids:
            newly_skipped.append(aid)
            continue

        studio_ids = []
        for name in rec["studios"][:3]:
            # AniListはラテン表記(MADHOUSE)、既存データは日本語表記(マッドハウス)のことがある。
            # スラッグが既存idと一致したら**同じスタジオ**とみなして再利用する(でないと
            # madhouse-2 のような二重登録が量産される)。綴りがずれる社名だけ alias で吸収。
            sid = (studio_by_name.get(name) or seen_studio.get(name)
                   or studio_alias.get(name))
            if not sid and slug(name) in used_studio_ids:
                sid = slug(name)
            if not sid:
                base = slug(name) or "studio"
                sid, i = base, 2
                while sid in used_studio_ids:
                    sid, i = f"{base}-{i}", i + 1
                used_studio_ids.add(sid)
                seen_studio[name] = sid
                # スタジオ名は英単語で「読み」ではないので romaji 変換は使えない(bones→ぼねす)
                kana = studio_kana.get(name) or ""
                if not kana:
                    need_studio_kana[name] = sid
                batch["newStudios"].append({
                    "id": sid, "name": name, "nameKana": kana,
                    "description": "アニメーション制作会社。", "externalLinks": {},
                    "sourceNote": "AniListの作品クレジット(2026-08-09取得)から登録。",
                    "updatedAt": TODAY})
            if sid not in studio_ids:
                studio_ids.append(sid)
        if not studio_ids:
            newly_skipped.append(aid)
            continue

        cast = []
        for c in rec["cast"][:5]:
            pid, is_new = person_id(c["va"], va_by_name, used_va_ids, seen_person)
            if not pid:
                continue
            if is_new:
                batch["newVoiceActors"].append({
                    "id": pid, "name": c["va"]["n"] or c["va"]["r"],
                    "nameKana": kana_of(c["va"]["r"], c["va"]["n"]) or "",
                    "description": "声優。", "externalLinks": {},
                    "sourceNote": "AniListの作品クレジット(2026-08-09取得)から登録。",
                    "updatedAt": TODAY})
            if not any(x["voiceActorId"] == pid for x in cast):
                cast.append({"voiceActorId": pid, "character": c["c"]})

        title_kana = romaji_to_hiragana(rec["r"])
        work = {
            "id": wid, "title": rec["t"], "titleKana": title_kana or "",
            "directorIds": director_ids, "seriesComposerIds": composer_ids,
            "studioIds": studio_ids, "cast": cast, "themeIds": rec["themes"],
            "format": rec["fmt"], "season": {"year": rec["y"], "quarter": rec["q"]},
            "originalType": rec["src"], "status": rec["st"], "synopsis": "",
            "anilistId": aid, "externalLinks": {},
            "sourceNote": SOURCE_NOTE.format(aid=aid), "updatedAt": TODAY,
        }
        if rec["ep"]:
            work["episodes"] = rec["ep"]
        batch["works"].append(work)
        applied[wid] = {"rr": romaji_root(rec["r"])}
        locked.append(cand_key)

        ask.append(f"{wid} | {rec['t']} | {rec['fmt']} {rec['y']} {rec['src']} "
                   f"{'ep' + str(rec['ep']) if rec['ep'] else ''} | "
                   f"{'/'.join(rec['studios'][:2])} | 監督{rec['dir'][0]['n'] or rec['dir'][0]['r']}"
                   f"{' | KANA?' if not title_kana else ''}\n  {rec['desc']}")

    # 空のかなは既存データの品質を落とすので、埋まらなかった人物も手動送りにする
    for group in ("newStaff", "newVoiceActors"):
        for p in batch[group]:
            if not p["nameKana"]:
                ask.append(f"PERSON_KANA {p['id']} | {p['name']}")

    APPLIED.write_text(json.dumps(applied, ensure_ascii=False), encoding="utf-8")
    if newly_skipped:
        SKIP.write_text(json.dumps(sorted(skip | set(newly_skipped))), encoding="utf-8")

    n = 1
    while (CACHE / f"batch{n:03d}.json").exists():
        n += 1
    (CACHE / f"batch{n:03d}.json").write_text(
        json.dumps(batch, ensure_ascii=False, indent=1), encoding="utf-8")
    header = [f"# batch{n:03d}: {len(batch['works'])} works",
              "# 各行 = 作品id | タイトル | 形式/年/原作 | スタジオ | 監督 (+ AniListのdescription)",
              "# 返すもの: .cache/batchNNN.meta.json"
              ' = {"<作品id>": {"s": "あらすじ150〜250字", "k": "KANA?の行だけタイトルのかな"},'
              ' "STUDIO": {"<スタジオid>": "かな"}, "PERSON": {"<人物id>": "かな"}}', ""]
    if need_studio_kana:
        header.append("STUDIO_KANA が必要: " +
                      ", ".join(f"{sid}({name})" for name, sid in need_studio_kana.items()))
    (CACHE / f"batch{n:03d}.ask.txt").write_text("\n".join(header + ask) + "\n", encoding="utf-8")
    print(f"staged batch{n:03d}: works={len(batch['works'])} "
          f"newStaff={len(batch['newStaff'])} newStudios={len(batch['newStudios'])} "
          f"newVA={len(batch['newVoiceActors'])} skipped={len(newly_skipped)}")
    print(f"  -> {CACHE / f'batch{n:03d}.ask.txt'}")


# ---------------------------------------------------------------- finalize
def finalize(n):
    bpath = CACHE / f"batch{n:03d}.json"
    mpath = CACHE / f"batch{n:03d}.meta.json"
    batch = json.loads(bpath.read_text(encoding="utf-8"))
    meta = json.loads(mpath.read_text(encoding="utf-8"))
    studio_kana = read_json(STUDIO_KANA, {})

    problems = []
    for w in batch["works"]:
        m = meta.get(w["id"]) or {}
        s = (m.get("s") or "").strip()
        if not s:
            problems.append(f"{w['id']}: synopsis missing")
        elif not 100 <= len(s) <= 320:
            problems.append(f"{w['id']}: synopsis length {len(s)}")
        # あらすじにキリル/ハングル/長い英単語が混ざっていないか機械点検(既存の運用ルール)
        if re.search(r"[Ѐ-ӿ가-힯]", s) or re.search(r"[A-Za-z]{4,}", s):
            bad = re.findall(r"[A-Za-z]{4,}|[Ѐ-ӿ가-힯]+", s)
            problems.append(f"{w['id']}: suspicious tokens {bad}")
        w["synopsis"] = s
        if not w["titleKana"]:
            w["titleKana"] = (m.get("k") or "").strip()
            if not w["titleKana"]:
                problems.append(f"{w['id']}: titleKana missing")

    for wid, series_id in (meta.get("SERIES") or {}).items():
        for w in batch["works"]:
            if w["id"] == wid:
                w["seriesId"] = series_id
    for sid, kana in (meta.get("STUDIO") or {}).items():
        for s in batch["newStudios"]:
            if s["id"] == sid:
                s["nameKana"] = kana
                studio_kana[s["name"]] = kana
    for pid, name in (meta.get("PERSON_NAME") or {}).items():
        for group in ("newStaff", "newVoiceActors"):
            for p in batch[group]:
                if p["id"] == pid:
                    p["name"] = name
                    p["sourceNote"] += "AniListの表記が日本のクレジットと異なるため表記を修正。"
    for pid, kana in (meta.get("PERSON") or {}).items():
        for group in ("newStaff", "newVoiceActors"):
            for p in batch[group]:
                if p["id"] == pid:
                    p["nameKana"] = kana
    for group in ("newStudios", "newStaff", "newVoiceActors"):
        for p in batch[group]:
            if not p["nameKana"]:
                problems.append(f"{p['id']}: nameKana missing ({p['name']})")

    if problems:
        print("REFUSING TO APPLY:")
        for p in problems[:40]:
            print("  " + p)
        sys.exit(1)

    STUDIO_KANA.write_text(json.dumps(studio_kana, ensure_ascii=False, indent=1), encoding="utf-8")
    merged = CACHE / f"batch{n:03d}.final.json"
    merged.write_text(json.dumps(batch, ensure_ascii=False, indent=1), encoding="utf-8")
    # apply_batch.py は追加idを全部並べるので、そのまま流すと1バッチ数千トークンになる。
    # 判断に要るのは件数と rejected だけなので圧縮して出す。
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "apply_batch.py"), str(merged)],
                       check=True, capture_output=True, text=True)
    rep = json.loads(r.stdout)
    print(f"batch{n:03d} applied: " + ", ".join(
        f"{k}={len(v)}" for k, v in rep["added"].items() if v))
    dups = {k: v for k, v in rep["skipped_duplicates"].items() if v}
    if dups:
        print("  skipped duplicates:", dups)
    if rep["rejected_works"]:
        print("  REJECTED:", json.dumps(rep["rejected_works"], ensure_ascii=False)[:1500])
    total = len(json.loads((SRC / "works.json").read_text(encoding="utf-8")))
    print(f"  works.json total: {total}")


# ---------------------------------------------------------------- drop
def drop(n, ids):
    """ステージ済みバッチから作品を取り除く(自動判定で拾いきれない分割公開作などの手動除外)。

    再ステージすると説明文をもう一度読む必要があり無駄なので、staged のまま間引けるようにする。
    取り除いた作品は skip.json に入り、以後のステージでも出てこない。
    """
    bpath = CACHE / f"batch{n:03d}.json"
    batch = json.loads(bpath.read_text(encoding="utf-8"))
    keep, dropped = [], []
    for w in batch["works"]:
        (dropped if w["id"] in ids else keep).append(w)
    batch["works"] = keep
    bpath.write_text(json.dumps(batch, ensure_ascii=False, indent=1), encoding="utf-8")
    skip = set(read_json(SKIP, []))
    skip |= {w["anilistId"] for w in dropped if w.get("anilistId")}
    SKIP.write_text(json.dumps(sorted(skip)), encoding="utf-8")
    print(f"dropped {[w['id'] for w in dropped]}; batch{n:03d} now has {len(keep)} works")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    CACHE.mkdir(parents=True, exist_ok=True)
    if sys.argv[1] == "stage":
        stage(int(sys.argv[2]))
    elif sys.argv[1] == "drop":
        drop(int(sys.argv[2]), set(sys.argv[3:]))
    elif sys.argv[1] == "finalize":
        finalize(int(sys.argv[2]))
    else:
        print(__doc__)
        sys.exit(1)
