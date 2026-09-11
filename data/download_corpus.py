#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""코퍼스 다운로더.

원본 문서는 저작권 때문에 저장소에 담지 않는다. 각자 이 스크립트로 원 출처에서
내려받는다. 매니페스트(data/corpus_manifest.csv)가 유일한 기준이며, 다운로드 결과의
SHA256 을 매니페스트 값과 대조해 "원문이 갱신됐는지"를 감지한다.

사용법
    python data/download_corpus.py                 # core + bundled 내려받기
    python data/download_corpus.py --tier all      # derived·manual 안내까지 포함
    python data/download_corpus.py --only nh_jangbyeong_2026
    python data/download_corpus.py --update-hashes # (강사) 매니페스트에 해시 기록
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import re
import sys
import time
import urllib.parse
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("requests 가 필요합니다:  uv pip install requests")

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "data" / "corpus_manifest.csv"
RAW_DIR = ROOT / "data" / "raw"
BUNDLED_DIR = ROOT / "data" / "bundled"
REPORT = ROOT / "data" / "download_report.json"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

# 같은 호스트에 연속 요청할 때의 최소 간격(초). 상대 서버를 배려하는 값이며 줄이지 말 것.
HOST_DELAY = defaultdict(lambda: 1.5, {
    "kpub.knia.or.kr": 3.0,        # WAF. 느리게.
    "og.kakaobank.io": 3.0,        # robots Disallow. 소량·저빈도만.
    "www.kakaobank.com": 3.0,
    "www.fss.or.kr": 2.0,
    "fine.fss.or.kr": 2.0,
    "www.idbins.com": 3.0,
})
MAX_RETRY = 3
TIMEOUT = 90

# 확장자가 아니라 첫 바이트로 형식을 판별한다. 서버가 Content-Type 을 비워 보내는
# 곳(손사코리아)이 있고, 200 응답에 HTML 오류 페이지를 담아 주는 곳도 있기 때문이다.
MAGIC = {
    "pdf":  [b"%PDF-"],
    "zip":  [b"PK\x03\x04"],            # hwpx·docx·zip 공통
    "hwp":  [b"\xd0\xcf\x11\xe0"],      # HWP 5.0 = CFBF
    "png":  [b"\x89PNG\r\n\x1a\n"],
    "jpg":  [b"\xff\xd8\xff"],
    "xml":  [b"<?xml", b"\xef\xbb\xbf<?xml"],
}


def sniff(head: bytes) -> str:
    for kind, sigs in MAGIC.items():
        if any(head.startswith(s) for s in sigs):
            return kind
    low = head[:1024].lower().lstrip()
    if low.startswith(b"<!doctype html") or low.startswith(b"<html") or b"<head" in low[:512]:
        return "html"
    return "text"


def type_ok(expected: str, actual: str) -> bool:
    if expected == actual:
        return True
    # hwpx 는 zip, 구형 hwp 는 CFBF. text 판정은 html/xml 을 포괄한다.
    return {("zip", "hwp"), ("hwp", "zip"), ("text", "html"), ("html", "text"),
            ("xml", "text"), ("text", "xml")} & {(expected, actual)} != set()


def encode_url(url: str) -> str:
    """URL 안의 한글 경로를 퍼센트 인코딩한다(쿼리스트링은 그대로 둔다)."""
    parts = urllib.parse.urlsplit(url)
    path = urllib.parse.quote(parts.path, safe="/%")
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment))


def text_of(body: bytes, kind: str) -> str:
    """텍스트 계열 응답을 사람이 읽는 문자열로 바꾼다(내용 검증용)."""
    for enc in ("utf-8", "cp949", "euc-kr", "latin-1"):
        try:
            s = body.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        return ""
    if kind in ("html", "text"):
        s = re.sub(r"<(script|style).*?</\1>", " ", s, flags=re.S | re.I)
    if kind in ("html", "xml", "text"):
        s = re.sub(r"<[^>]+>", " ", s)
    return " ".join(s.split())


def content_problems(body: bytes, row: dict, kind: str) -> list[str]:
    """HTTP 200 이라고 내용이 맞는 것은 아니다.

    로그인 페이지나 오류 페이지를 200 으로 돌려주는 사이트가 있고, 목록만 있고
    본문은 JS 로 채우는 사이트도 있다. 매니페스트에 적어 둔 필수 문자열로 확인한다.
    PDF 는 여기서 열지 않고 scripts/profile_docs.py 가 검사한다.
    """
    if kind not in ("html", "xml", "text"):
        return []
    text = text_of(body, kind)
    flat = re.sub(r"\s+", "", text)

    def present(n: str) -> bool:
        return n in text or re.sub(r"\s+", "", n) in flat

    problems = [f"없음:{n}" for n in row.get("must_contain", "").split("|") if n and not present(n)]
    problems += [f"있으면안됨:{n}" for n in row.get("must_not_contain", "").split("|")
                 if n and present(n)]
    return problems


# 갱신 감지의 기준. HTML 은 요청마다 바뀌는 값(APM 추적 토큰, CSRF, 타임스탬프)이
# 섞여 들어와서 바이트 해시가 매번 달라진다. 그대로 두면 "갱신됨" 경고가 늘 울려
# 아무도 보지 않게 된다. 그래서 텍스트 계열은 태그와 공백을 정리한 뒤 해시한다.
TEXTUAL = {"html", "xml", "text"}


def content_hash(body: bytes, kind: str, strip: str = "") -> str:
    if kind not in TEXTUAL:
        return hashlib.sha256(body).hexdigest()
    text = text_of(body, kind)
    if strip:
        # 조회수처럼 볼 때마다 바뀌는 값을 빼고 해시한다. 무엇을 "내용"으로 볼지
        # 정하는 일이라, 규칙은 매니페스트에 문서마다 적어 둔다.
        text = re.sub(strip, "", text)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def hash_file(path: Path, kind: str, strip: str = "") -> str:
    return content_hash(path.read_bytes(), kind, strip)


def kind_of(row: dict, head: bytes) -> str:
    k = sniff(head)
    return k if k in TEXTUAL or row["expected_type"] not in TEXTUAL else row["expected_type"]


def page_count(path: Path) -> int | None:
    if path.suffix.lower() != ".pdf":
        return None
    try:
        from pypdf import PdfReader
        return len(PdfReader(str(path)).pages)
    except Exception:
        return None


class Throttle:
    def __init__(self):
        self.last: dict[str, float] = {}

    def wait(self, host: str) -> None:
        gap = HOST_DELAY[host]
        prev = self.last.get(host)
        if prev is not None:
            rest = gap - (time.monotonic() - prev)
            if rest > 0:
                time.sleep(rest)
        self.last[host] = time.monotonic()


def fetch(session: requests.Session, row: dict, throttle: Throttle) -> tuple[bytes | None, str]:
    url = encode_url(row["url"].replace("{OC}", os.getenv("LAW_OC", "test")))
    host = urllib.parse.urlsplit(url).netloc
    headers = {"User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9"}
    if row.get("referer"):
        headers["Referer"] = row["referer"]

    for attempt in range(1, MAX_RETRY + 1):
        throttle.wait(host)
        try:
            r = session.get(url, headers=headers, timeout=TIMEOUT, allow_redirects=True)
        except requests.RequestException as e:
            if attempt == MAX_RETRY:
                return None, f"요청 실패: {type(e).__name__}"
            time.sleep(2 ** attempt + random.uniform(0, 1))
            continue

        if r.status_code == 200:
            if not r.content:
                return None, "빈 응답(0바이트)"
            return r.content, ""
        if r.status_code in (403, 404, 410):
            return None, f"HTTP {r.status_code}"
        if attempt == MAX_RETRY:
            return None, f"HTTP {r.status_code}"
        time.sleep(2 ** attempt + random.uniform(0, 1))
    return None, "재시도 소진"


def main() -> int:
    ap = argparse.ArgumentParser(description="금융 문서 코퍼스 다운로더")
    ap.add_argument("--tier", default="default",
                    choices=["default", "core", "bundled", "manual", "derived", "all"],
                    help="default = core + bundled")
    ap.add_argument("--only", action="append", default=[], help="doc_id 지정(여러 번 가능)")
    ap.add_argument("--force", action="store_true", help="이미 받은 파일도 다시 받는다")
    ap.add_argument("--update-hashes", action="store_true",
                    help="(강사) 내려받은 해시를 매니페스트에 기록한다")
    args = ap.parse_args()

    if not MANIFEST.exists():
        sys.exit(f"매니페스트가 없습니다: {MANIFEST}")
    with MANIFEST.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    want = {"default": {"core", "bundled"}, "all": {"core", "bundled", "manual", "derived"}}.get(
        args.tier, {args.tier})
    targets = [r for r in rows if r["tier"] in want]
    if args.only:
        targets = [r for r in targets if r["doc_id"] in set(args.only)]
    if not targets:
        sys.exit("대상이 없습니다.")

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    BUNDLED_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    throttle = Throttle()
    results, hashes = [], {}

    fetchable = [r for r in targets if r["tier"] in ("core", "bundled")]
    print(f"대상 {len(targets)}건 (내려받기 {len(fetchable)}건)\n")

    for i, row in enumerate(targets, 1):
        did, tier = row["doc_id"], row["tier"]
        dest_dir = BUNDLED_DIR if tier == "bundled" else RAW_DIR
        dest = dest_dir / (row["filename"] or f"{did}.bin")

        if tier == "manual":
            results.append({"doc_id": did, "status": "manual", "note": row["notes"]})
            print(f"[{i:2}/{len(targets)}] {did:34} 수동 수집 → {row['url']}")
            continue
        if tier == "derived":
            results.append({"doc_id": did, "status": "derived", "note": row["url"]})
            print(f"[{i:2}/{len(targets)}] {did:34} 로컬 생성 → {row['url']}")
            continue

        if dest.exists() and not args.force:
            digest = hash_file(dest, kind_of(row, dest.open("rb").read(2048)),
                               row.get("hash_strip", ""))
            hashes[did] = digest
            status = "cached"
            if row["sha256"] and row["sha256"] != digest:
                status = "changed"
            results.append({"doc_id": did, "status": status, "path": str(dest.relative_to(ROOT)),
                            "sha256": digest, "bytes": dest.stat().st_size})
            print(f"[{i:2}/{len(targets)}] {did:34} 보유({status})")
            continue

        body, err = fetch(session, row, throttle)
        if body is None:
            results.append({"doc_id": did, "status": "failed", "error": err, "url": row["url"]})
            print(f"[{i:2}/{len(targets)}] {did:34} 실패: {err}")
            continue

        actual = sniff(body[:2048])
        problems = content_problems(body, row, actual)
        if problems:
            results.append({"doc_id": did, "status": "bad_content", "problems": problems,
                            "bytes": len(body), "url": row["url"]})
            print(f"[{i:2}/{len(targets)}] {did:34} 내용 이상: {', '.join(problems[:3])}")
            continue
        if not type_ok(row["expected_type"], actual):
            results.append({"doc_id": did, "status": "wrong_type", "expected": row["expected_type"],
                            "actual": actual, "bytes": len(body)})
            print(f"[{i:2}/{len(targets)}] {did:34} 형식 불일치: {row['expected_type']} 기대 / {actual} 수신")
            continue

        dest.write_bytes(body)
        digest = content_hash(body, actual, row.get("hash_strip", ""))
        hashes[did] = digest
        status = "new"
        if row["sha256"]:
            status = "ok" if row["sha256"] == digest else "changed"
        pages = page_count(dest)
        results.append({"doc_id": did, "status": status, "path": str(dest.relative_to(ROOT)),
                        "sha256": digest, "bytes": len(body), "pages": pages})
        extra = f", {pages}p" if pages else ""
        print(f"[{i:2}/{len(targets)}] {did:34} {status} ({len(body):,}바이트{extra})")

    if args.update_hashes and hashes:
        cols = list(rows[0].keys())
        for r in rows:
            if r["doc_id"] in hashes:
                r["sha256"] = hashes[r["doc_id"]]
                res = next(x for x in results if x["doc_id"] == r["doc_id"])
                r["bytes"] = str(res.get("bytes", ""))
        with MANIFEST.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
        print(f"\n매니페스트에 해시 {len(hashes)}건 기록")

    counts = defaultdict(int)
    for r in results:
        counts[r["status"]] += 1
    REPORT.write_text(json.dumps(
        {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "tier": args.tier, "counts": dict(counts), "results": results},
        ensure_ascii=False, indent=1), encoding="utf-8")

    print("\n" + " / ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    print(f"리포트: {REPORT.relative_to(ROOT)}")

    if counts["changed"]:
        print("\n[알림] 원문이 갱신된 문서가 있습니다. 재인제스천 대상입니다.")
    failed = counts["failed"] + counts["wrong_type"] + counts["bad_content"]
    if failed:
        print(f"\n[경고] 실패 {failed}건. 원 출처가 URL 이나 화면 구성을 바꿨을 수 있습니다.")
        print("     data/download_report.json 을 열어 어떤 문서가 왜 실패했는지 확인하세요.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
