#!/usr/bin/env python3
"""AniList GraphQL APIの薄い共有ラッパ(probe_anilist.py / suggest_candidates.py が使う)。

- エンドポイント: https://graphql.anilist.co (認証不要)
- レート制限: 公式には90req/分だが、実際には30req/分程度に絞られている時期があるため
  既定で2.2秒スリープを挟む。429が返ったら Retry-After を尊重して再試行する。
"""
import json
import time
import urllib.request

API = "https://graphql.anilist.co"
SLEEP = 2.2


def query(gql: str, variables: dict, retries: int = 3) -> dict:
    body = json.dumps({"query": gql, "variables": variables}).encode("utf-8")
    for attempt in range(retries + 1):
        req = urllib.request.Request(
            API,
            data=body,
            # urllib既定のUA(Python-urllib/3.x)はCloudflareに403で弾かれるため必ず名乗る
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "anime-db-fan-site/0.1 (https://izenmi.github.io/anime-db/)",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as res:
                payload = json.loads(res.read().decode("utf-8"))
                if payload.get("errors"):
                    raise RuntimeError(f"AniList errors: {payload['errors']}")
                return payload["data"]
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries:
                wait = int(e.headers.get("Retry-After") or 30)
                print(f"  429 rate limited, waiting {wait}s...", flush=True)
                time.sleep(wait + 1)
                continue
            raise
    raise RuntimeError("unreachable")
