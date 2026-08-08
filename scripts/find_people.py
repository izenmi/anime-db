#!/usr/bin/env python3
"""人名・スタジオ名が既存エンティティにあるかを一覧する。

使い方: python3 scripts/find_people.py --names 新海誠 MAPPA 花澤香菜

staff/studios/voiceActors のJSON全体をコンテキストに載せずに既存IDを引くための補助。
バッチを組む前に必ず通して、同一人物・同一スタジオの重複登録を避ける。
"""
import json
import re
import sys
import unicodedata
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "public" / "data" / "source"


def norm(s: str) -> str:
    return re.sub(r"[\s　・･,，.。]", "", unicodedata.normalize("NFKC", s or "")).lower()


def load(name):
    return {norm(x["name"]): x["id"] for x in json.loads((SRC / f"{name}.json").read_text(encoding="utf-8"))}


def main():
    staff, studios, vas = load("staff"), load("studios"), load("voiceActors")
    if sys.argv[1:2] != ["--names"] or len(sys.argv) < 3:
        print("usage: find_people.py --names <name> [<name> ...]")
        sys.exit(1)
    for nm in sys.argv[2:]:
        k = norm(nm)
        print(f"{nm}\tstaff={staff.get(k, '?')}\tstudio={studios.get(k, '?')}\tva={vas.get(k, '?')}")


if __name__ == "__main__":
    main()
