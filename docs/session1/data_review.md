# 데이터 살펴보기 (1회차 · 35분)

오늘 만들 시스템이 읽게 될 문서를 직접 열어 봅니다. 코드는 쓰지 않습니다.
제출은 없습니다. 답은 본인 메모에 적어 두세요. 마지막에 강사가 답을 엽니다.

**진행**

- 5분: 강사가 어디를 볼지 화면으로 보여 줍니다
- 20분: 혼자 봅니다 (아래 문제 12개)
- 10분: 강사가 답을 엽니다

**준비**

- 수업 시작 때 `make download` 를 끝냈으면 `data/raw/` 에 파일이 들어 있습니다
- `data/documents.csv` 와 `data/doc_profile.json` 은 저장소에 들어 있습니다. 문서를 못 받았어도 A 와 B 는 풀 수 있습니다

---

## 어디를 보나

| 순서 | 파일 | 무엇 | 여는 법 |
|---|---|---|---|
| 1 | `data/README.md` | 왜 원본 문서가 저장소에 없는지 | 첫 절만 읽습니다 (2분) |
| 2 | `data/documents.csv` | 문서 51건의 카탈로그. 오늘의 지도입니다 | VS Code 로 열면 검색이 됩니다. 표로 보려면 Numbers 나 Excel 에서 UTF-8 로 가져옵니다 |
| 3 | `data/raw/`, `data/bundled/` | 실물 PDF | 아래 9개를 PDF 뷰어로 엽니다 |
| 4 | `data/doc_profile.json` | 문서마다 파서별로 글자가 몇 자 나왔는지 | VS Code 에서 doc_id 로 검색합니다 |
| 5 | `data/glossary.md` 2절, `data/constants.yaml` 머리말 | 판본·시점 용어, 법령 상수 | 각 3분 |

**documents.csv 에서 볼 열**

| 열 | 뜻 |
|---|---|
| `doc_id` | 문서 이름입니다. 다른 파일에서도 이 이름으로 찾습니다 |
| `issuer`, `doc_type`, `product` | 누가 낸 무슨 문서인지 |
| `format` | pdf / html / xml / binary_office(HWP) / text |
| `pages`, `chars`, `chars_per_page` | 쪽수, 글자 수, 쪽당 글자 수. **0 이면 글자가 없습니다** |
| `best_parser` | 가장 많이 읽어 낸 파서. `unsupported` 면 셋 다 실패한 것입니다 |
| `quality` | 측정 결과 분류. 정상텍스트 / 표중심 / 공백소실 / 국소깨짐 / 이미지전용 / 폰트깨짐 |
| `effective_from`, `effective_to` | 시행일, 종료일 |
| `review_expiry` | 심의필 유효기간이 끝나는 날 |
| `synthetic_degraded` | `true` 면 실습용으로 일부러 망가뜨린 문서입니다 |
| `purpose` | 이 문서를 왜 넣었는지 (인덱싱 / 홀드아웃 / 네거티브 …) |

**열어 볼 PDF 9개**

| 파일 | 폴더 | 쓰는 문제 |
|---|---|---|
| `hana_credit_terms_2009.pdf`, `hana_credit_terms_2013.pdf`, `hana_credit_terms_2024.pdf` | data/raw | B1, B2, C1 |
| `kbstar_deposit_2021.pdf`, `im_mortgage_2024.pdf` | data/raw | B2 |
| `knia_3500_scan.pdf` | data/raw | C3 |
| `im_household_2025.pdf`, `hana_household_loan_2014.pdf` | data/raw | D1 |
| `law_silson_std.pdf` | data/bundled | C2 |

---

## 문제 12개

시간이 모자라면 B 와 D 를 먼저 하세요. 오늘 이야기의 핵심이 거기 있습니다.

### A. 무엇이 있나

**A1.** 문서는 모두 몇 건이고, 형식(`format`)은 몇 가지입니까. PDF 가 아닌 것은 몇 건입니까.
어디서: documents.csv

**A2.** 저장소 안에 실제로 들어 있는 원본은 어느 폴더의 어떤 문서뿐입니까. 나머지는 왜 없습니까.
어디서: data/README.md 첫 절, data/bundled/

**A3.** `chars` 가 0 인 행을 모두 찾으세요. 몇 건입니까. 0 인 이유가 전부 같습니까.
어디서: documents.csv 의 `chars`, `format`, `best_parser`, `synthetic_degraded` 열

### B. 판본과 날짜

**B1.** 하나은행 여신거래기본약관은 판본이 몇 개입니까. 각 시행일은 언제입니까. 2013년 판본은 언제까지 쓰였습니까.
그리고 2021년 5월에 대출을 받은 고객이 약관 조항을 물으면, 어느 판본으로 답해야 합니까.
어디서: documents.csv 에서 `hana_credit_terms` 검색. `effective_from`, `effective_to`

**B2.** 아래 세 문서의 1쪽에서 "심의필"을 찾아 그 줄을 그대로 적으세요. 세 개의 형식이 같습니까.

- `kbstar_deposit_2021.pdf`
- `im_mortgage_2024.pdf`
- `hana_credit_terms_2024.pdf`

어디서: PDF 뷰어에서 Ctrl+F (Mac 은 Cmd+F) "심의필"

**B3.** `review_expiry` 가 채워진 문서는 몇 건입니까. 그중 오늘 날짜로 이미 지난 것과, 한 달 안에 지나는 것은 무엇입니까.
어디서: documents.csv 의 `review_expiry` 열

### C. 글자가 제대로 나오나

**C1.** `hana_credit_terms_2009.pdf` 를 열면 눈에는 멀쩡한 약관입니다. documents.csv 의 `quality` 는 무엇입니까. doc_profile.json 에서 이 문서의 pypdf 와 pymupdf 가 읽은 한글(`hangul`) 수를 각각 적으세요.
어디서: doc_profile.json 에서 `hana_credit_terms_2009` 검색 → `extractors`

**C2.** `law_silson_std.pdf` 는 492쪽입니다. doc_profile.json 에서 이 문서의 `broken_page` 와 `empty_pages` 를 찾으세요. 나쁜 쪽은 몇 쪽입니까. 이 문서를 색인에서 빼야 합니까.
어디서: doc_profile.json 에서 `law_silson_std_pdf` 검색

**C3.** `knia_3500_scan.pdf` 를 열어 본문 글자를 마우스로 드래그해 보세요. 선택이 됩니까. documents.csv 에서 이 문서의 `chars` 와 `quality` 는 무엇입니까.

### D. 숫자가 있나

**D1.** `im_household_2025.pdf` 에서 "중도상환수수료"를 찾으세요. 요율은 몇 % 입니까.
`hana_household_loan_2014.pdf` 에서 "기준금리는"을 찾으세요. 기준금리는 연 몇 % 입니까.
어디서: 각 PDF 뷰어 검색. 앞은 2쪽, 뒤는 1쪽

**D2.** 이자소득세율은 몇 % 이고 어디에 적혀 있습니까. 이 값은 문서에서 검색해야 합니까, 상수표에서 읽어야 합니까. 반대로 적금 이율은 어디서 읽어야 합니까.
어디서: data/constants.yaml 머리말과 `tax` 항목

**D3.** 고객이 "자기부담금"이라고 묻습니다. 실손 표준약관 본문은 이것을 무엇이라고 부릅니까.
어디서: data/glossary.md 에서 "자기부담금" 검색
