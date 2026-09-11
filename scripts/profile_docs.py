#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""문서 실태 프로파일러.

내려받은 문서를 파서 3종으로 실제 열어 보고, 무엇이 깨지는지 숫자로 남긴다.
1회차 "문서 실태" 실습의 계측기이자 data/documents.csv 의 생성기다.

만드는 것
    data/doc_profile.json  측정 상세(파서별 추출량·페이지별 밀도·깨짐 비율)
    data/documents.csv     인제스천이 참조하는 문서 카탈로그

사용법
    python scripts/profile_docs.py
    python scripts/profile_docs.py --only nh_jangbyeong_2026 --verbose
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "data" / "corpus_manifest.csv"
RAW, BUNDLED = ROOT / "data" / "raw", ROOT / "data" / "bundled"
PROFILE_JSON = ROOT / "data" / "doc_profile.json"
DOCUMENTS_CSV = ROOT / "data" / "documents.csv"

HANGUL = re.compile(r"[가-힣]")
CID = re.compile(r"\(cid:\d+\)")
# 한국어 금융문서에 실제로 나올 수 있는 문자 범위. 이 밖의 문자는 폰트 매핑이
# 깨졌다는 신호다. PUA(U+F000 등)뿐 아니라 제어문자와 엉뚱한 문자(인도계·키릴 결합
# 문자 등)로 매핑되는 경우가 있어서, 블랙리스트가 아니라 허용목록으로 판정한다.
ALLOWED_RANGES = [
    (0x09, 0x0A), (0x0D, 0x0D), (0x20, 0x7E),      # 탭·개행·ASCII
    (0xA0, 0xFF),                                   # °, ±, · 등
    (0x2000, 0x206F), (0x20A0, 0x20CF),             # 일반 구두점, 통화기호(₩)
    (0x2100, 0x21FF), (0x2200, 0x22FF),             # 문자꼴 기호, 화살표, 수학기호
    (0x2460, 0x24FF), (0x2500, 0x257F),             # 원문자 ①, 괘선
    (0x25A0, 0x26FF),                               # ○ ● △ ■ ◇ ※ 등
    (0x3000, 0x303F), (0x3130, 0x318F),             # 전각 구두점, 호환 자모
    (0x4E00, 0x9FFF), (0xAC00, 0xD7A3),             # 한자, 한글 음절
    (0xF900, 0xFAFF), (0xFF00, 0xFFEF),             # 한자 호환, 전각/반각
]


def is_allowed(ch: str) -> bool:
    o = ord(ch)
    return any(lo <= o <= hi for lo, hi in ALLOWED_RANGES)
TAG = re.compile(r"<[^>]+>")
SCRIPT = re.compile(r"<(script|style).*?</\1>", re.S | re.I)

# 페이지에 이 글자 수 미만이면 텍스트 레이어가 없다고 본다.
EMPTY_PAGE_CHARS = 30
# 문서 전체 평균이 이 미만이면 OCR 경로로 보낸다.
OCR_THRESHOLD = 50


def hangul_count(s: str) -> int:
    return len(HANGUL.findall(s))


def broken_ratio(s: str) -> float:
    """허용 범위 밖 문자의 비율. (cid:123) 표기는 통째로 한 번의 손상으로 센다."""
    if not s:
        return 0.0
    body = CID.sub("", s)
    foreign = sum(1 for ch in body if not is_allowed(ch))
    return (foreign + len(CID.findall(s))) / max(len(s), 1)


def broken_sample(s: str, k: int = 8) -> list[str]:
    from collections import Counter
    bad = Counter(ch for ch in CID.sub("", s) if not is_allowed(ch))
    return [f"U+{ord(c):04X}×{n}" for c, n in bad.most_common(k)]


def extract_pypdf(path: Path) -> list[str]:
    try:
        from pypdf import PdfReader
        return [(p.extract_text() or "") for p in PdfReader(str(path)).pages]
    except Exception:
        return []


def extract_pymupdf(path: Path) -> list[str]:
    try:
        import pymupdf
        with pymupdf.open(str(path)) as doc:
            return [pg.get_text() for pg in doc]
    except Exception:
        return []


def page_objects(path: Path) -> list[dict]:
    """페이지마다 이미지·벡터 객체가 있는지 본다.

    글자가 0자인 페이지가 다 같은 페이지가 아니다.
      - 이미지 객체가 있으면  → 스캔본. OCR 로 보낸다.
      - 아무 객체도 없으면    → 진짜 빈 페이지. OCR 로 보내면 시간만 쓰고 잡음만 얻는다.
    검증 게이트가 이 둘을 구분하지 못하면 빈 페이지를 OCR 큐에 계속 쌓는다.
    """
    try:
        import pymupdf
        with pymupdf.open(str(path)) as doc:
            return [{"images": len(pg.get_images(full=True)),
                     "drawings": len(pg.get_drawings())} for pg in doc]
    except Exception:
        return []


def sample_indices(n: int, k: int) -> list[int]:
    if n <= k:
        return list(range(n))
    step = n / k
    return sorted({min(n - 1, int(i * step)) for i in range(k)})


def probe_pdfplumber(path: Path, n_pages: int, k: int = 5) -> dict:
    """pdfplumber 는 느리므로 표본 페이지만 본다. 표 탐지와 공백 보존 확인용."""
    out = {"sampled_pages": [], "chars": 0, "spaces": 0, "tables": 0, "ok": False}
    try:
        import pdfplumber
        idx = sample_indices(n_pages, k)
        with pdfplumber.open(str(path)) as pdf:
            for i in idx:
                page = pdf.pages[i]
                t = page.extract_text() or ""
                out["sampled_pages"].append(i + 1)
                out["chars"] += len(t)
                out["spaces"] += t.count(" ")
                try:
                    out["tables"] += len(page.find_tables())
                except Exception:
                    pass
        out["ok"] = True
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
    return out


def profile_pdf(path: Path) -> dict:
    pypdf_pages = extract_pypdf(path)
    mupdf_pages = extract_pymupdf(path)
    n = max(len(pypdf_pages), len(mupdf_pages))

    a, b = "".join(pypdf_pages), "".join(mupdf_pages)
    ha, hb = hangul_count(a), hangul_count(b)
    best_name, best_pages = ("pymupdf", mupdf_pages) if hb >= ha else ("pypdf", pypdf_pages)
    best_text = "".join(best_pages)

    per_page = [len(p) for p in best_pages] or [0]
    empty_pages = [i + 1 for i, c in enumerate(per_page) if c < EMPTY_PAGE_CHARS]
    objs = page_objects(path)
    scan_pages, blank_pages, vector_pages = [], [], []
    for pno in empty_pages:
        o = objs[pno - 1] if pno <= len(objs) else {"images": 0, "drawings": 0}
        if o["images"]:
            scan_pages.append(pno)
        elif o["drawings"]:
            vector_pages.append(pno)
        else:
            blank_pages.append(pno)
    mean = statistics.fmean(per_page)
    cv = (statistics.pstdev(per_page) / mean) if mean else 0.0

    plumber = probe_pdfplumber(path, n)
    # 같은 표본 페이지를 PyMuPDF 로도 뽑아 공백 보존율을 비교한다.
    mu_sample = "".join(mupdf_pages[i - 1] for i in plumber["sampled_pages"]
                        if 0 < i <= len(mupdf_pages))
    mu_space_rate = mu_sample.count(" ") / max(len(mu_sample), 1)
    pl_space_rate = plumber["spaces"] / max(plumber["chars"], 1)

    # 페이지별 깨짐 비율의 최댓값(문서 전체 평균은 국소 손상을 감춘다)
    page_broken = [broken_ratio(p) for p in best_pages] or [0.0]

    return {
        "kind": "pdf",
        "pages": n,
        "extractors": {
            "pypdf":   {"chars": len(a), "hangul": ha},
            "pymupdf": {"chars": len(b), "hangul": hb},
            "pdfplumber_sample": plumber,
        },
        "best_parser": best_name,
        "chars": len(best_text),
        "hangul": hangul_count(best_text),
        "chars_per_page": round(mean, 1),
        "density_cv": round(cv, 3),
        "empty_pages": empty_pages,
        "empty_page_count": len(empty_pages),
        "scan_pages": scan_pages,          # 이미지 객체 있음 → OCR 대상
        "blank_pages": blank_pages,        # 아무것도 없음 → 건너뜀
        "vector_only_pages": vector_pages, # 선·도형만 → 사람 확인
        "scan_page_count": len(scan_pages),
        "blank_page_count": len(blank_pages),
        "broken_ratio_doc": round(broken_ratio(best_text), 5),
        "broken_ratio_page_max": round(max(page_broken), 5),
        "broken_page": (page_broken.index(max(page_broken)) + 1) if max(page_broken) > 0 else None,
        "broken_chars": broken_sample(best_pages[page_broken.index(max(page_broken))]) if max(page_broken) > 0 else [],
        "space_rate_pymupdf": round(mu_space_rate, 4),
        "space_rate_pdfplumber": round(pl_space_rate, 4),
        "tables_in_sample": plumber["tables"],
        "text": best_text,
    }


def profile_text_like(path: Path, kind: str) -> dict:
    raw = path.read_bytes()
    for enc in ("utf-8", "cp949", "euc-kr", "latin-1"):
        try:
            s = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if kind == "html":
        s2 = TAG.sub(" ", SCRIPT.sub(" ", s))
        text = " ".join(s2.split())
    elif kind == "xml":
        # <![CDATA[...]]> 안에 조문 본문이 들어 있어 정규식으로 태그를 지우면
        # 내용까지 함께 사라진다. 반드시 XML 파서로 읽는다.
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(s)
            text = " ".join("".join(root.itertext()).split())
        except Exception:
            text = " ".join(TAG.sub(" ", s).split())
    else:
        text = s
    return {"kind": kind, "pages": None, "chars": len(text), "hangul": hangul_count(text),
            "best_parser": {"html": "html_strip", "xml": "xml", "text": "plain"}[kind],
            "text": text}


def classify(p: dict, row: dict) -> tuple[str, str, int, list[str]]:
    """(주 등급, 권장 처리, 난이도 1~5, 측정된 특성 전부)

    한 문서가 문제를 하나만 갖지는 않는다. 주 등급은 '가장 먼저 손대야 할 것'이고,
    traits 에는 측정으로 확인된 특성을 모두 남긴다.
    """
    if p["kind"] != "pdf":
        return "정상텍스트", "직접 파싱", 1, []

    traits: list[str] = []
    pypdf_h = p["extractors"]["pypdf"]["hangul"]
    mupdf_h = p["extractors"]["pymupdf"]["hangul"]
    space_loss = (p["space_rate_pymupdf"] < p["space_rate_pdfplumber"] * 0.5
                  and p["space_rate_pdfplumber"] > 0.05)

    if p["chars_per_page"] < OCR_THRESHOLD:
        traits.append("이미지전용" if p["scan_page_count"] else "빈문서")
    if mupdf_h and pypdf_h < mupdf_h * 0.1:
        traits.append("폰트깨짐")
    if p["broken_ratio_page_max"] > 0.05:
        traits.append("국소깨짐")
    if p["scan_page_count"] > 0:
        traits.append("스캔페이지혼재")
    if p["blank_page_count"] > 0:
        traits.append("빈페이지")
    if p["vector_only_pages"]:
        traits.append("도형전용페이지")
    if space_loss:
        traits.append("공백소실")
    if p["tables_in_sample"] >= 3 or "표붕괴" in row["traits"] or "병합셀" in row["traits"]:
        traits.append("표중심")
    if p["density_cv"] > 0.8:
        traits.append("밀도편차")

    order = [
        ("이미지전용",     "전체 OCR", 5),
        ("폰트깨짐",       f"파서 라우팅 → {p['best_parser']}", 4),
        ("국소깨짐",       f"{p['broken_page']}쪽 재시도 후 사람 확인", 4),
        ("공백소실",       "pdfplumber 로 재추출", 3),
        ("스캔페이지혼재", f"스캔 페이지 {p['scan_page_count']}장만 OCR", 3),
        ("표중심",         "표 특화 파서", 3),
        ("도형전용페이지", "사람 확인", 2),
        ("밀도편차",       "페이지 단위 검증", 2),
        ("빈페이지",       f"빈 페이지 {p['blank_page_count']}장 건너뜀", 1),
        ("빈문서",         "원본 확인 필요", 5),
    ]
    for name, handling, diff in order:
        if name in traits:
            return name, handling, diff, traits
    return "정상텍스트", "직접 파싱", 1, traits


def main() -> int:
    ap = argparse.ArgumentParser(description="문서 실태 프로파일러")
    ap.add_argument("--only", action="append", default=[])
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    rows = list(csv.DictReader(MANIFEST.open(encoding="utf-8")))
    if args.only:
        rows = [r for r in rows if r["doc_id"] in set(args.only)]

    profiles, docs, missing, content_fail = {}, [], [], []

    for row in rows:
        did = row["doc_id"]
        if row["tier"] == "manual":
            continue
        path = (BUNDLED if row["tier"] == "bundled" else RAW) / row["filename"]
        if not path.exists():
            # derived 는 scripts/make_degraded.py 로 만들기 전에는 없는 게 정상이다.
            if row["tier"] != "derived":
                missing.append(did)
            continue

        head = path.open("rb").read(8)
        if head.startswith(b"%PDF-"):
            p = profile_pdf(path)
        elif head.startswith((b"PK\x03\x04", b"\xd0\xcf\x11\xe0")):
            p = {"kind": "binary_office", "pages": None, "chars": 0, "hangul": 0,
                 "best_parser": "unsupported", "text": ""}
        else:
            kind = "xml" if row["expected_type"] == "xml" else (
                "html" if row["expected_type"] == "html" else "text")
            p = profile_text_like(path, kind)

        text = p.pop("text", "")
        # 공백이 소실된 문서에서는 "제31조"가 "제 3 1 조"로 추출된다. 공백을 지운
        # 문자열끼리도 비교해야 "받았는데 내용이 다르다"와 "파서가 공백을 흘렸다"를
        # 혼동하지 않는다.
        flat = re.sub(r"\s+", "", text)

        def present(needle: str) -> bool:
            return needle in text or re.sub(r"\s+", "", needle) in flat

        needles = [x for x in row.get("must_contain", "").split("|") if x]
        missing = [x for x in needles if not present(x)]
        p["must_contain_ok"] = not missing
        p["must_contain_missing"] = missing

        forbidden = [x for x in row.get("must_not_contain", "").split("|") if x]
        unexpected = [x for x in forbidden if present(x)]
        p["must_not_contain_ok"] = not unexpected
        p["must_not_contain_unexpected"] = unexpected

        if missing or unexpected:
            content_fail.append((did, {"없음": missing, "있으면 안 됨": unexpected}))

        quality, handling, difficulty, traits = classify(p, row)
        p.update(quality=quality, handling=handling, difficulty=difficulty,
                 traits_measured=traits, bytes=path.stat().st_size)
        profiles[did] = p

        docs.append({
            "doc_id": did,
            "doc_type": row["doc_type"],
            "issuer": row["issuer"],
            "product": row["product"],
            "generation": row["generation"],
            "effective_from": row["effective_from"],
            "effective_to": row["effective_to"],
            "review_expiry": row["review_expiry"],
            "category": row["category"],
            "path": str(path.relative_to(ROOT)),
            "format": p["kind"],
            "pages": p["pages"] or "",
            "chars": p["chars"],
            "chars_per_page": p.get("chars_per_page", ""),
            "best_parser": p["best_parser"],
            "quality": quality,
            "handling": handling,
            "difficulty": difficulty,
            "traits_measured": "|".join(traits),
            "empty_pages": p.get("empty_page_count", ""),
            "scan_pages": p.get("scan_page_count", ""),
            "blank_pages": p.get("blank_page_count", ""),
            "broken_ratio_page_max": p.get("broken_ratio_page_max", ""),
            "density_cv": p.get("density_cv", ""),
            "tables_in_sample": p.get("tables_in_sample", ""),
            "synthetic_degraded": row["synthetic_degraded"],
            "license": row["license"],
            "sessions": row["sessions"],
            "purpose": row["purpose"],
        })

        if args.verbose:
            print(f"{did:32} {quality:8} {p['chars']:>8,}자  {p['best_parser']}")

    if not docs:
        print("프로파일할 문서가 없습니다. --only 인자나 다운로드 상태를 확인하세요.")
        return 1

    # --only 로 일부만 돌렸다면 기존 결과를 지우지 않고 그 문서만 갱신한다.
    # (전체 결과를 날려 버리면 OCR 캐시 생성 같은 후속 단계가 조용히 멈춘다.)
    if args.only and PROFILE_JSON.exists():
        merged = json.loads(PROFILE_JSON.read_text(encoding="utf-8"))
        merged.update(profiles)
        profiles = merged
    PROFILE_JSON.write_text(json.dumps(profiles, ensure_ascii=False, indent=1), encoding="utf-8")

    if args.only and DOCUMENTS_CSV.exists():
        prev = {r["doc_id"]: r for r in csv.DictReader(DOCUMENTS_CSV.open(encoding="utf-8"))}
        prev.update({d["doc_id"]: d for d in docs})
        docs = list(prev.values())
    with DOCUMENTS_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(docs[0].keys()))
        w.writeheader()
        w.writerows(docs)

    from collections import Counter
    print(f"\n프로파일 {len(docs)}건 → {DOCUMENTS_CSV.relative_to(ROOT)}")
    for k, v in sorted(Counter(d["quality"] for d in docs).items(), key=lambda x: -x[1]):
        print(f"  {k:10} {v}")
    if missing:
        print(f"\n[없음] {len(missing)}건: {', '.join(missing[:8])}")
    if content_fail:
        print(f"\n[내용 검증 실패] {len(content_fail)}건")
        for did, detail in content_fail:
            parts = [f"{k} {v}" for k, v in detail.items() if v]
            print(f"  {did}: {'; '.join(parts)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
