# skhynix-hackerton-ish606
sk 하이닉스 해커톤을 위해 생성한 github repository

## 냉각 조건 비교 연습

발열량 100 W, 입구 온도 20℃인 조건 중 최고온도 50℃ 이하를 만족하는
최소 유량 조건을 추천합니다. 동률이면 최고온도, case_id 순으로 선택합니다.
Python 3 표준 라이브러리만 사용하므로 추가 패키지 설치가 필요 없습니다.

## 실행 방법

터미널에서 이 저장소 폴더로 이동한 뒤 실행합니다.
Windows에서 Python Launcher가 설치되어 있다면 다음 명령을 사용합니다.

```bash
py -3 main.py --input data/cases.csv --out outputs
```

이 클라우드 환경과 Linux/macOS에서는 다음 명령을 사용합니다.

```bash
python3 main.py --input data/cases.csv --out outputs
```

입력 원본은 변경하지 않습니다. 결과 폴더는 자동 생성하며, 재실행하면
그 안의 summary.csv, excluded.csv, report.md를 덮어씁니다.
CSV는 UTF-8 BOM 인코딩으로 저장해 한글을 포함한 스프레드시트 열기를 돕습니다.

## 파일 설명

| 파일 | 설명 |
| --- | --- |
| requirements.md | 비교 목표, 데이터 처리 규칙과 검증 기준 |
| data/cases.csv | 원본 냉각 조건 데이터 |
| main.py | 분석 프로그램 |
| outputs/summary.csv | 유효 조건의 모든 입력 값, 원본 행 번호, 통과/미통과 및 추천 여부 |
| outputs/excluded.csv | 제외 행의 모든 입력 값, 원본 행 번호와 모든 제외 이유 |
| outputs/report.md | 추천 결과, 판단 근거, 처리 내역과 분석 한계 |
| tests/test_main.py | 임시 입력을 이용한 실행 및 경계 조건 검증 |

summary.csv의 temperature_status는 `통과` 또는 `미통과`, recommended는
`예` 또는 `아니오`입니다. 원본 행 번호(source_row)는 헤더를 1행으로 셉니다.
제공 데이터의 기대 결과는 비교 5행, 통과 4행, 미통과 1행, 제외 5행이며
추천은 C07(1.2 L/min, 50℃)입니다.

동일한 중복 행은 처음만 사용합니다. 동일 ID에 다른 값이 있으면
오류와 관련 행 번호를 알리고, 결과 파일에 오류 내역을 남기며 추천을 보류합니다.
중복 판단은 모든 열의 원본 문자열을 비교하므로 `1.0`과 `1.00`은 서로 다른 값으로 취급합니다.
빈 값·비숫자·무한대 및 비교 기준에 맞지 않는 행은 제외합니다.
잘못된 헤더나 열 개수 등 CSV 구조 오류가 발생하면 분석을 중단합니다.

종료 코드는 정상 완료(추천 없음 포함) 0, 입력/출력 오류 1, 동일 ID 값 충돌 2입니다.
실행이 실패한 경우 이전 실행의 결과 파일을 최신 결과로 사용하지 마세요.

## 결과 확인과 테스트

실행 후 outputs/report.md를 열어 추천과 처리 내역을 확인하고,
summary.csv와 excluded.csv를 열어 각 행의 판정과 제외 이유를 확인합니다.

```bash
python3 -m unittest discover -s tests -v
```

Windows에서는 위 테스트 명령의 `python3` 대신 `py -3`을 사용합니다.
테스트는 임시 폴더를 사용하며 원본 데이터와 outputs는 변경하지 않습니다.
