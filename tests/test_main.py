import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HEADER = 'case_id,heat_W,inlet_C,flow_L_min,max_temp_C\n'


class CoolingCLITests(unittest.TestCase):
    def run_case(self, data):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source = base / 'input.csv'
            source.write_text(data, encoding='utf-8')
            before = source.read_bytes()
            out = base / 'results'
            process = subprocess.run(
                [sys.executable, str(ROOT / 'main.py'), '--input', str(source), '--out', str(out)],
                capture_output=True, text=True, encoding='utf-8',
            )
            self.assertEqual(before, source.read_bytes(), '입력 원본이 변경되었습니다')
            tables = []
            for name in ('summary.csv', 'excluded.csv'):
                if (out / name).exists():
                    with (out / name).open(encoding='utf-8-sig', newline='') as stream:
                        tables.append(list(csv.DictReader(stream)))
                else:
                    tables.append([])
            report = (out / 'report.md').read_text(encoding='utf-8') if (out / 'report.md').exists() else ''
            return process, *tables, report

    def test_supplied_data(self):
        process, summary, excluded, report = self.run_case((ROOT / 'data/cases.csv').read_text())
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual([r['case_id'] for r in summary], ['C01', 'C02', 'C03', 'C04', 'C07'])
        self.assertEqual([r['case_id'] for r in summary if r['recommended'] == '예'], ['C07'])
        self.assertEqual(sum(r['temperature_status'] == '통과' for r in summary), 4)
        self.assertEqual(summary[0]['temperature_status'], '미통과')
        self.assertEqual(summary[-1]['temperature_status'], '통과')
        self.assertEqual([r['source_row'] for r in excluded], ['6', '7', '8', '10', '11'])
        for row, reason in zip(excluded, ['중복', '최고온도 누락', '유량이 0 이하', '발열량', '입구 온도']):
            self.assertIn(reason, row['reason'])
        self.assertEqual(excluded[1]['max_temp_C'], '')
        for text in ('**C07**', '1.2 L/min', '50℃', '비교 가능한 행: 5', '제외 행: 5', '분석 한계'):
            self.assertIn(text, report)

    def test_ties_and_input_order(self):
        rows = ['Z,100,20,1,49', 'B,100,20,1,48', 'A,100,20,1,48', 'X,100,20,2,30']
        for ordering in (rows, list(reversed(rows))):
            process, summary, _, _ = self.run_case(HEADER + '\n'.join(ordering) + '\n')
            self.assertEqual(process.returncode, 0)
            self.assertEqual([r['case_id'] for r in summary if r['recommended'] == '예'], ['A'])

    def test_conflict_including_ineligible_row(self):
        data = HEADER + 'A,100,20,1,40\nA,150,20,1,40\nB,100,20,2,45\n'
        process, summary, excluded, report = self.run_case(data)
        self.assertEqual(process.returncode, 2)
        self.assertIn('값 충돌', process.stderr)
        self.assertIn('[2, 3]', process.stderr)
        self.assertTrue(all(r['recommended'] == '아니오' for r in summary))
        self.assertEqual(len(excluded), 2)
        self.assertIn('발열량', excluded[1]['reason'])
        self.assertIn('최종 추천 보류', report)

    def test_no_passing_and_empty_input(self):
        for data in (HEADER, HEADER + 'A,100,20,1,51\n'):
            process, summary, _, report = self.run_case(data)
            self.assertEqual(process.returncode, 0)
            self.assertTrue(all(r['recommended'] == '아니오' for r in summary))
            self.assertIn('추천 없음', report)

    def test_multiple_exclusions_and_invalid_numbers(self):
        data = HEADER + 'A,150,25,-1,\nB,100,20,NaN,40\nC,100,20,1,Infinity\nD,100,20,abc,40\n'
        process, summary, excluded, _ = self.run_case(data)
        self.assertEqual(process.returncode, 0)
        self.assertEqual(summary, [])
        self.assertEqual(len(excluded), 4)
        for reason in ('최고온도 누락', '유량이 0 이하', '발열량', '입구 온도'):
            self.assertIn(reason, excluded[0]['reason'])
        for row in excluded[1:]:
            self.assertIn('유한한 숫자가 아님', row['reason'])

    def test_numeric_targets_and_duplicate_first_row(self):
        data = HEADER + 'A,100.0,20.0,1.00,50.0\nA,100.0,20.0,1.00,50.0\n'
        process, summary, excluded, _ = self.run_case(data)
        self.assertEqual(process.returncode, 0)
        self.assertEqual(summary[0]['source_row'], '2')
        self.assertEqual(summary[0]['recommended'], '예')
        self.assertEqual(excluded[0]['source_row'], '3')

    def test_malformed_csv(self):
        for data in ('case_id,heat_W\nA,100\n', HEADER + 'A,100,20,1\n'):
            process, _, _, _ = self.run_case(data)
            self.assertEqual(process.returncode, 1)
            self.assertIn('오류', process.stderr)

    def test_reject_overwriting_input(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'summary.csv'
            source.write_text(HEADER + 'A,100,20,1,40\n', encoding='utf-8')
            before = source.read_bytes()
            process = subprocess.run(
                [sys.executable, str(ROOT / 'main.py'), '--input', str(source), '--out', directory],
                capture_output=True, text=True, encoding='utf-8',
            )
            self.assertEqual(process.returncode, 1)
            self.assertEqual(source.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
