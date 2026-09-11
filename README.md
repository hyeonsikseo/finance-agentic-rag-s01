# 약관부터 답변까지 — 1회차

금융 문서 특화 Agentic RAG 수업의 저장소입니다. 지금은 1회차에 필요한 것만 들어 있고, 회차가 진행되면 내용이 늘어납니다.

## 1회차에 할 일

1. 설치하고 문서를 내려받습니다. 수업 첫 시간에 같이 합니다. → [docs/install.md](docs/install.md)
2. 수업 중에 문서를 직접 열어 보고 문제 12개를 풉니다. → [docs/session1/data_review.md](docs/session1/data_review.md)
3. 수업이 끝나면 강사가 산출물 예시 네 개를 올립니다. 저장소 폴더에서 `git pull` 하면 `docs/session1/examples/` 폴더가 생깁니다.

## 폴더

| 폴더 | 무엇 |
|---|---|
| `docs/install.md` | 설치와 문서 내려받기. 막힐 때 보는 표가 있습니다 |
| `docs/session1/` | 고객 브리프, 문제지, 시행일 읽는 법. 수업 뒤에 산출물 예시가 추가됩니다 |
| `data/` | 문서 51건의 카탈로그와 측정 결과. 원본 문서는 각자 내려받습니다 |
| `scripts/profile_docs.py` | 문서 실태를 재는 스크립트. 카탈로그는 이미 들어 있으니 안 돌려도 됩니다 |

## 명령

```bash
make setup      # 파이썬 3.12 와 패키지 설치. 1~2분
make download   # 문서 49건 내려받기. 약 5분
make profile    # (선택) 문서 실태를 다시 잰다. 약 2분
```

Windows 에서는 `make` 가 없으니 [docs/install.md](docs/install.md) 의 PowerShell 명령을 씁니다.

## 원본 문서가 저장소에 없는 이유

약관과 상품설명서는 각 금융회사의 저작물이라 다시 나눠 줄 수 없습니다. 저장소에는 "무엇을 어디서 받는지"만 있고, 각자 원 출처에서 받습니다. 자세한 것은 [data/README.md](data/README.md) 에 있습니다.
