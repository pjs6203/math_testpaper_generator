# 문항 데이터 형식 v1

`exam.json`은 UTF-8 JSON입니다. 주석을 쓰지 않습니다. JSON Schema는 `schema/exam.schema.json`, 완성 예제는 `examples/demo/exam.json`입니다.

## 최소 예제

```json
{
  "schema_version": 1,
  "title": "수학 문제지",
  "subject": "수 학",
  "exam_code": "MA",
  "edition": "한국어 편집본",
  "duration_minutes": 180,
  "expected_question_count": 1,
  "expected_total_marks": 2,
  "questions": [
    {
      "number": 1,
      "score": 2,
      "type": "NAT",
      "stem": "다음 적분의 값을 구하시오.\n$$\\int_0^1 x^2\\,dx$$",
      "rounding": "(소수 셋째 자리에서 반올림하여 소수 둘째 자리까지 나타내시오.)",
      "choices": [],
      "source_pages": [],
      "review": {"status": "verified", "notes": ["자체 작성 예제"]}
    }
  ]
}
```

실제 원문이 있는 작업은 prepare가 만든 `source` 객체를 유지합니다. 그때 `source_pages`는 빈 목록일 수 없습니다. `verified`는 AI가 실제로 원문 대조를 마친 뒤에만 기록합니다.

## 메타데이터

| 필드 | 설명 |
| --- | --- |
| schema_version | 정수 1 |
| title | 첫 면 상단 제목. 너무 길면 오류가 납니다. |
| subject | 과목명. 보통 `수 학`. |
| exam_code | 표와 쪽수에 표시할 짧은 시험 코드 |
| edition | 표에 표시할 편집본 이름 |
| language | PDF 언어. 기본 `ko-KR` |
| duration_minutes | 시험 시간 또는 null. 원문에 없으면 추정하지 않습니다. |
| expected_question_count | 직접 확인한 전체 문항 수. 원문 PDF가 있으면 필수. |
| expected_total_marks | 직접 확인한 총점 또는 null |
| source | `{ "path": "input.pdf", "sha256": "…", "url": null }`. 원문 해시가 달라지면 재확인이 필요합니다. |
| instructions / glossary / notes | 문자열 목록. 최종 notes.md에 보존됩니다. 문제지에 추가 문항처럼 끼워 넣지 않습니다. |

본문에 필요한 기호 정의는 해당 문항에 포함할 수도 있습니다. 여러 문항의 공통 정의와 긴 시험 운영 안내는 glossary와 instructions에 넣어 별도 안내로 전달합니다.

## 문항

- `number`: 원문의 양의 정수 번호. 중복 없이 오름차순이어야 합니다. 원문이 일부 번호만 제공되면 번호 간격을 억지로 채우지 않습니다.
- `score`: 0 이상의 숫자 또는 null. 총점이 지정되면 모든 문항의 배점이 있어야 합니다.
- `type`: `MCQ`(단일정답), `MSQ`(복수정답), `NAT`(수치답), `FREE`(서답).
- `stem`: 본문과 수식. 소문항도 여기에 보존합니다.
- `choices`: MCQ/MSQ는 2-8개, NAT/FREE는 없거나 빈 목록. 라벨은 넣지 않고 원래 순서대로 문자열만 적습니다.
- `rounding`: 원문의 반올림·답 표기 요구. NAT/FREE에 사용하며 원문에 없으면 추가하지 않습니다.
- `source_pages`: 원본 PDF 페이지 번호 목록. 1부터 셉니다. 인쇄된 쪽수와 다를 수 있습니다.
- `review`: `{ "status": "pending" 또는 "verified", "notes": [] }`.
- `figures`: 아래 그림 형식의 목록. 본문 뒤, 선택지 앞에 배치됩니다.

문항 수가 홀수이면 마지막 오른쪽 단은 비워 둡니다. 긴 문항을 자동으로 다음 단으로 분할하거나 다른 문항을 삭제하지 않습니다.

## 수식

- 인라인: `$x^2+1$`
- 별도 줄: `$$\frac{a}{b}$$`
- 일반 문장 안에서 줄바꿈은 JSON의 `\n`입니다.
- JSON 문자열에서 TeX의 역슬래시는 두 번 씁니다: `"$\\frac12$"`.
- 행렬의 행 구분자 `\\`는 JSON에서 `\\\\`로 씁니다.
- 분수, 적분, 합, 행렬, cases, aligned 등 MathJax의 base/ams/newcommand 패키지를 지원합니다. 임의 패키지 자동 로드나 웹 링크는 지원하지 않습니다.
- 한국어 문장은 수식 밖에 둡니다. `\text{한국어}`는 지원 대상이 아닙니다. 수식 안의 짧은 영문은 지원됩니다.
- 돈 기호처럼 문장에 `$`가 필요하면 JSON에서 `\\$`로 이스케이프합니다.
- 수식은 한 덩어리로 줄바꿈합니다. 너무 넓으면 최소 9 pt까지 축소할 수 있고, 그 이하가 필요하면 오류를 냅니다. `aligned` 등으로 직접 줄을 나눕니다.

## 그림

벡터 원본이 있으면 PDF를 권장합니다.

```json
{
  "figures": [
    {
      "path": "input.pdf",
      "page": 3,
      "bbox": [100, 300, 400, 500],
      "width": 230,
      "caption": "그림의 가로축은 $x$, 세로축은 $y$이다."
    }
  ]
}
```

- `path`: exam.json 디렉터리를 기준으로 한 상대경로. 작업 디렉터리 밖 파일이나 절대경로를 허용하지 않습니다.
- `page`: PDF 자산 페이지. 1부터 시작합니다.
- `bbox`: PDF 포인트 단위 `[x0,y0,x1,y1]`. **왼쪽 아래 원점**입니다. 생략하면 자산 PDF의 cropbox를 사용합니다.
- `width`: 포인트 단위 희망 너비. 단 너비를 넘지 않게 맞추고 종횡비를 보존합니다.
- PNG/JPEG도 path와 width를 사용합니다. 원래 이미지 품질 이상으로 선명해지지는 않습니다.
- 회전이 있는 원본 페이지는 아래 crop-figure 명령으로 정규화한 별도 자산을 먼저 만듭니다.

별도 벡터 자산 저장:

```sh
python -m math_testpaper crop-figure jobs/task/input.pdf --page 3 --box 100 300 400 500 --out jobs/task/figures/q5.pdf
```

이때 bbox는 페이지 회전을 정규화한 뒤의 PDF 좌표입니다. 표시용 PNG에서 측정한 좌표는 `pt = pixel × 72 / dpi`로 변환하고 세로 좌표를 아래 원점으로 바꿉니다. 원문 PDF의 표기·다른 문항·워터마크가 함께 들어가지 않도록 crop을 확인합니다.

복잡한 그림을 새로 만들어야 하면 Python 등으로 벡터 PDF를 작성하여 figures로 넣습니다. 원본 그림을 임의로 단순화해 수학적 정보를 잃지 않습니다.

## 글꼴 지정

```json
{
  "body": "fonts/body.ttf",
  "head": "fonts/bold.ttf",
  "title": "fonts/gothic.ttf"
}
```

```sh
python -m math_testpaper build jobs/task/exam.json --out jobs/task/output --fonts fonts.json
```

글꼴 경로는 fonts.json 기준입니다. 사용 권한과 PDF 포함 가능 여부를 확인한 TrueType 글꼴을 지정합니다. 자동 글꼴 프로필과 원본 평가원 서브셋 글꼴은 동일하다고 가정하지 않습니다. 글꼴에 없는 문자는 오류로 알립니다. 나눔 글꼴에 없는 선택지 동그라미 번호는 벡터 원과 숫자로 그립니다.

## 템플릿 조정

`src/math_testpaper/assets/kice_a3.json`을 복사해 `--template custom.json`으로 전달할 수 있습니다. A3 2단 계약 안에서 본문 크기·행간 등을 조정합니다. 기본 템플릿은 고정된 평가원식 표제 좌표를 사용하므로 다른 종이 크기로 바꾸는 기능은 제공하지 않습니다. 변경 값과 이유를 notes에 기록합니다.
