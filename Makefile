.PHONY: help setup download profile
PY := .venv/bin/python

help:
	@echo "make setup     파이썬 3.12 와 패키지 설치 (1~2분)"
	@echo "make download  문서 49건 내려받기 (약 5분)"
	@echo "make profile   문서 실태 다시 재기 (선택, 약 2분)"

setup:
	uv venv --python 3.12 .venv
	uv pip install --python $(PY) -r requirements.txt

download:
	$(PY) data/download_corpus.py

profile:
	$(PY) scripts/profile_docs.py
