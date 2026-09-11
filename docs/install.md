# 설치와 문서 내려받기

수업 첫 시간에 같이 합니다. 전부 해서 10분쯤 걸리고, 마지막 문서 내려받기가 대부분입니다. 내려받는 동안은 수업을 들으면 됩니다.

## 1. 준비물 두 가지, git 과 uv

uv 는 파이썬 패키지 도구입니다. 파이썬 3.12 도 uv 가 받아 주니 파이썬을 따로 설치하지 않아도 됩니다.

**Mac**

```bash
xcode-select --install
curl -LsSf https://astral.sh/uv/install.sh | sh
```

첫 줄은 git 을 설치합니다. 이미 있으면 "already installed"라고 나오고, 그러면 넘어갑니다.

**Windows (PowerShell)**

```powershell
winget install --id Git.Git -e
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

설치가 끝나면 터미널을 닫고 새로 엽니다. 새로 열어야 방금 설치한 명령이 잡힙니다. 확인은 이렇게 합니다.

```bash
git --version
uv --version
```

## 2. 저장소 받기

```bash
git clone https://github.com/hyeonsikseo/finance-agentic-rag-s01.git
cd finance-agentic-rag-s01
```

Windows 에서도 같습니다.

## 3. 파이썬과 패키지 설치

**Mac**

```bash
make setup
```

**Windows (PowerShell)**

```powershell
uv venv --python 3.12 .venv
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
```

1~2분 걸립니다. 파이썬 3.12 가 없으면 uv 가 받아 옵니다.

## 4. 문서 내려받기

**Mac**

```bash
make download
```

**Windows (PowerShell)**

```powershell
.venv\Scripts\python data\download_corpus.py
```

약 5분 걸립니다. 금융감독원, 법제처, 각 금융회사 사이트에서 공개 문서 49건을 각자 내려받습니다. 원본이 저장소에 없는 이유는 저작권입니다. [data/README.md](../data/README.md) 에 적어 두었습니다. 사이트에 부담을 주지 않도록 사이트마다 간격을 두고 받게 돼 있습니다. 그 값은 줄이지 않습니다.

끝나면 `data/raw` 폴더에 파일이 40개 넘게 있어야 합니다. 몇 건 실패했으면 같은 명령을 한 번 더 돌립니다. 계속 실패하는 문서는 그것만 다시 받습니다.

```bash
.venv/bin/python data/download_corpus.py --only <doc_id>
```

## 막힐 때

| 증상 | 이유 | 이렇게 합니다 |
|---|---|---|
| `uv: command not found` | 설치 뒤 터미널을 새로 안 열었습니다 | 터미널을 닫고 새로 엽니다 |
| 파이썬 3.12 를 못 찾는다 | 아직 없는 것입니다 | uv 가 받아 오니 기다립니다. 인터넷이 필요합니다 |
| SSL 오류가 나거나 내려받기가 멈춘다 | 회사 네트워크의 보안 검사 | 휴대폰 핫스팟으로 바꿔 다시 돌립니다 |
| 회사 노트북이라 설치가 막힌다 | 관리자 권한 문제 | 오늘은 강사 화면으로 따라오고, 개인 노트북에서 다시 합니다 |
| Mac 에서 `make: command not found` | 1번 첫 줄 설치가 안 끝났습니다 | 첫 줄을 다시 하고 새 터미널을 엽니다 |
| Windows 에서 `make` 가 없다 | 원래 없습니다 | 위의 PowerShell 명령을 씁니다 |

## 오늘 못 받았으면

수업 4부는 강사 화면으로 따라오면 됩니다. 문제지의 A 와 B 는 저장소에 들어 있는 `data/documents.csv` 와 `data/doc_profile.json` 만으로 풀 수 있습니다. 수업 뒤에 위 순서대로 받아 두면 됩니다.
