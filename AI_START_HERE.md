# PDF와 링크를 받은 AI의 시작점

1. [AGENTS.md](AGENTS.md)를 읽는다.
2. `python scripts/setup.py`로 로컬 환경을 준비한다.
3. 가상환경 Python으로 `-m math_testpaper prepare INPUT.pdf --workdir jobs/task`를 실행한다.
4. 원문 전 페이지를 보고 `jobs/task/exam.json`에 한국어 문항과 TeX 수식을 작성한다. [형식](docs/format.md)을 따른다.
5. 원문과 대조한 각 문항에만 `review.status: verified`를 기록한다.
6. `-m math_testpaper build jobs/task/exam.json --out jobs/task/output`을 실행한다.
7. 최종 PNG 전 페이지를 확인하고 문제를 수정한다.
8. `review --all-pages --note ...`를 기록하고 `verify --require-reviewed`를 통과시킨다.
9. `output/exam.pdf`를 사용자에게 전달한다.

이 프로그램은 PDF를 읽어 의미를 이해하는 AI 자체를 포함하지 않는다. 현재 AI의 PDF 읽기와 코드 실행 도구를 사용한다. 별도 API 키·한컴·브라우저 자동화는 필요 없다.
