"""표준 라이브러리만 사용하는 냉각 조건 비교 CLI."""

import argparse
import csv
import sys
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path


FIELDS = ['case_id', 'heat_W', 'inlet_C', 'flow_L_min', 'max_temp_C']


def read_cases(path):
    rows = []
    with path.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.reader(stream, strict=True)
        header = next(reader, None)
        if header is None or len(header) != len(FIELDS) or set(header) != set(FIELDS):
            raise ValueError('CSV 헤더에는 다음 열이 각각 한 번 있어야 합니다: ' + ','.join(FIELDS))
        while True:
            line = reader.line_num + 1
            values = next(reader, None)
            if values is None:
                break
            if len(values) != len(header):
                raise ValueError(f'원본 {line}행: 열 개수가 헤더와 다릅니다.')
            rows.append({'source_row': line, **dict(zip(header, values))})
    return rows


def analyze(rows):
    by_id = defaultdict(list)
    for row in rows:
        by_id[row['case_id']].append(row)
    conflicts = {
        case_id: [row['source_row'] for row in group]
        for case_id, group in by_id.items()
        if len({tuple(row[key] for key in FIELDS) for row in group}) > 1
    }
    seen = {}
    summary, excluded = [], []
    for row in rows:
        identity = tuple(row[key] for key in FIELDS)
        reasons = []
        if row['case_id'] in conflicts:
            lines = ', '.join(map(str, conflicts[row['case_id']]))
            reasons.append(f'동일 case_id 값 충돌 (관련 원본 행: {lines})')
        if identity in seen:
            reasons.append(f'모든 값이 같은 중복 행 (최초 원본 행: {seen[identity]})')
        else:
            seen[identity] = row['source_row']
        if not row['case_id'].strip():
            reasons.append('case_id 누락')
        numbers = {}
        for field in FIELDS[1:]:
            raw = row[field].strip()
            if not raw:
                reasons.append('최고온도 누락' if field == 'max_temp_C' else f'{field} 누락')
                continue
            try:
                number = Decimal(raw)
                if not number.is_finite():
                    raise InvalidOperation
                numbers[field] = number
            except InvalidOperation:
                reasons.append(f'{field}: 유한한 숫자가 아님')
        if 'flow_L_min' in numbers and numbers['flow_L_min'] <= 0:
            reasons.append('유량이 0 이하')
        if 'heat_W' in numbers and numbers['heat_W'] != 100:
            reasons.append('발열량이 100 W가 아님')
        if 'inlet_C' in numbers and numbers['inlet_C'] != 20:
            reasons.append('입구 온도가 20℃가 아님')
        if reasons:
            excluded.append({**row, 'reason': '; '.join(reasons)})
        else:
            summary.append({
                **row,
                'temperature_status': '통과' if numbers['max_temp_C'] <= 50 else '미통과',
                'recommended': '아니오',
            })
    candidates = [row for row in summary if row['temperature_status'] == '통과']
    winner = None
    if candidates and not conflicts:
        winner = min(candidates, key=lambda row: (
            Decimal(row['flow_L_min']), Decimal(row['max_temp_C']), row['case_id']
        ))
        winner['recommended'] = '예'
    return summary, excluded, conflicts, winner


def write_csv(path, fields, rows):
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_outputs(out, source, rows, summary, excluded, conflicts, winner):
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / 'summary.csv', ['source_row', *FIELDS, 'temperature_status', 'recommended'], summary)
    write_csv(out / 'excluded.csv', ['source_row', *FIELDS, 'reason'], excluded)
    passed = sum(row['temperature_status'] == '통과' for row in summary)
    report = [
        '# 냉각 조건 비교 보고서', '',
        f'입력 파일: {source}', '',
        '## 추천 결과', '',
    ]
    if conflicts:
        report += ['오류: 동일 case_id에 서로 다른 값이 있어 최종 추천 보류.', '',
                   '충돌을 수정한 뒤 다시 실행해야 합니다. 충돌이 없는 행의 비교 결과는 참고용입니다.', '']
        for case_id, lines in conflicts.items():
            report.append(f'- {case_id!r}: 관련 원본 행 {", ".join(map(str, lines))}')
    elif winner:
        report += [
            f'추천 조건: **{winner["case_id"]}**', '',
            f'- 발열량: {winner["heat_W"]} W',
            f'- 입구 온도: {winner["inlet_C"]}℃',
            f'- 유량: {winner["flow_L_min"]} L/min',
            f'- 최고온도: {winner["max_temp_C"]}℃',
            f'- 원본 행 번호: {winner["source_row"]}',
        ]
    else:
        report += ['추천 없음: 온도 기준을 통과한 비교 가능한 조건이 없습니다.']
    report += [
        '', '## 판단 근거', '',
        '- 발열량 100 W와 입구 온도 20℃에 숫자로 정확히 일치하는 행만 비교합니다.',
        '- 유량은 0보다 커야 하며, 최고온도 50℃ 이하는 통과입니다.',
        '- 통과 행 중 유량 → 최고온도 → case_id 오름차순으로 하나를 추천합니다.',
        '- case_id는 Python 문자열의 대소문자를 구분하는 사전순으로 비교합니다.',
        '- 최고온도가 50℃를 초과한 유효 행도 summary.csv에 미통과로 남깁니다.',
        '', '## 데이터 처리 내역', '',
        f'- 전체 데이터 행: {len(rows)}',
        f'- 비교 가능한 행: {len(summary)}',
        f'- 온도 기준 통과: {passed}',
        f'- 온도 기준 미통과: {len(summary) - passed}',
        f'- 제외 행: {len(excluded)}',
        f'- 값 충돌 case_id 수: {len(conflicts)}',
        '- 원본 CSV는 수정하지 않았습니다.',
        '- 모든 열의 원본 문자열이 같은 중복은 최초 행만 사용합니다.',
        '- 최고온도 누락은 0℃로 대체하지 않습니다.',
        '- 헤더를 1행으로 세며, 여러 줄 CSV 레코드는 시작 물리 행 번호를 기록합니다.',
        '- 한 행의 제외 사유가 여러 개이면 모두 기록합니다.', '',
    ]
    report += [f'- 원본 {row["source_row"]}행 ({row["case_id"]!r}): {row["reason"]}' for row in excluded]
    report += [
        '', '## 분석 한계', '',
        '- 입력된 최고온도를 비교하며 열전달 시뮬레이션이나 측정값 검증은 하지 않습니다.',
        '- 온도·유량의 측정 오차, 불확도와 허용 오차는 반영하지 않습니다.',
        '- 단위는 입력 헤더의 W, ℃, L/min으로 가정하며 단위 변환은 하지 않습니다.',
        '- 압력 손실, 펌프 전력, 비용과 장비 제약은 평가하지 않습니다.',
        '- 추천은 제공된 조건 안에서만 유효하며 미측정 조건의 최적값을 뜻하지 않습니다.',
        '- 누락·비숫자·무한대 값은 제외합니다. 잘못된 CSV 구조는 오류로 종료합니다.',
        '',
    ]
    (out / 'report.md').write_text('\n'.join(report), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description='냉각 조건을 비교하고 최소 유량 조건을 추천합니다.')
    parser.add_argument('--input', required=True, type=Path, help='입력 CSV 경로')
    parser.add_argument('--out', required=True, type=Path, help='결과 폴더 (기존 결과 파일 덮어쓰기)')
    args = parser.parse_args()
    try:
        for name in ('summary.csv', 'excluded.csv', 'report.md'):
            target = args.out / name
            if target.resolve() == args.input.resolve() or (
                target.exists() and args.input.exists() and target.samefile(args.input)
            ):
                raise ValueError('결과 경로가 입력 파일과 같습니다. 다른 --out 경로를 사용하세요.')
        rows = read_cases(args.input)
        summary, excluded, conflicts, winner = analyze(rows)
        write_outputs(args.out, args.input, rows, summary, excluded, conflicts, winner)
    except (OSError, UnicodeError, csv.Error, ValueError) as error:
        print(f'오류: {error}', file=sys.stderr)
        print('이번 실행은 완료되지 않았습니다. 기존 결과 파일을 최신 결과로 사용하지 마세요.', file=sys.stderr)
        return 1
    if conflicts:
        for case_id, lines in conflicts.items():
            print(f'오류: case_id={case_id!r} 값 충돌, 원본 행 {lines}', file=sys.stderr)
        print('최종 추천 보류. 상세 내용은 report.md를 확인하세요.', file=sys.stderr)
        return 2
    print(f'분석 완료: 비교 {len(summary)}행, 제외 {len(excluded)}행')
    print(f'추천 조건: {winner["case_id"]}' if winner else '추천 없음')
    print(f'결과 폴더: {args.out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
