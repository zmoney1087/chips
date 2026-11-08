"""Tests for misleading datasheet matches, uncertainty, input safety and export."""
import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'build_device_report.py'
spec = importlib.util.spec_from_file_location('build_device_report', SCRIPT)
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.catalog = {'BMA280': {'url': 'https://example.com/bma280.pdf', 'manufacturer': 'Bosch', 'checked_on': '2026-11-08', 'verification': 'Test fixture'}}

    def inventory(self, identification='BMA280 accelerometer', tentative=False):
        path = self.root / 'sample_ifixit_chips.json'
        path.write_text(json.dumps({'metadata': {'brand': 'Example'}, 'devices': [
            {'name': 'Example device', 'chips': [{'identification': identification, 'tentative': tentative,
             'manufacturers_mentioned': ['Bosch', 'on'], 'sources': [{'url': 'javascript:alert(1)'}, {'url': 'https://www.ifixit.com/Guide/example/1'}]}]},
            {'name': 'No-chip-list device', 'chips': []}
        ]}))
        return path

    def test_exact_part_match_not_related_or_longer_part(self):
        self.assertEqual(len(report.find_datasheets('Bosch BMA280 (likely)', self.catalog)), 1)
        for text in ['BMA282', 'BMA2800', 'XBMA280', 'BMA280A', 'Unidentified accelerometer']:
            self.assertEqual(report.find_datasheets(text, self.catalog), [], text)

    def test_matching_document_does_not_confirm_tentative_identification(self):
        data = report.build_report([self.inventory('BMA280, possibly', tentative=True)], self.catalog)
        chip = data['devices'][0]['chips'][0]
        self.assertTrue(chip['tentative'])
        self.assertEqual(len(chip['datasheets']), 1)
        self.assertEqual(chip['manufacturers'], ['Bosch'])

    def test_unknown_chip_gets_search_not_fabricated_document(self):
        data = report.build_report([self.inventory('Apple 338S00000 unknown IC')], self.catalog)
        chip = data['devices'][0]['chips'][0]
        self.assertEqual(chip['datasheets'], [])
        self.assertTrue(chip['search_url'].startswith('https://www.google.com/search?'))
        self.assertTrue(chip['tentative'])

    def test_empty_records_and_multiple_roles_are_preserved(self):
        data = report.build_report([self.inventory('LPDDR4 RAM stacked over a processor')], self.catalog)
        self.assertEqual(data['stats']['records'], 2)
        self.assertEqual(data['stats']['with_chips'], 1)
        labels = [role['label'] for role in data['devices'][0]['chips'][0]['roles']]
        self.assertIn('Working memory', labels)
        self.assertIn('Processing or control', labels)

    def test_untrusted_urls_and_script_closing_text_stay_inert(self):
        data = report.build_report([self.inventory('</script><script>alert(1)</script>')], self.catalog)
        chip = data['devices'][0]['chips'][0]
        self.assertEqual(len(chip['sources']), 1)
        path = self.root / 'report.html'
        report.write_html(path, data)
        self.assertNotIn('</script><script>alert(1)</script>', path.read_text())
        self.assertIn('\\u003c/script\\u003e', path.read_text())
        for url in ['javascript:alert(1)', 'data:text/html,hi', 'https://user:pass@example.com', 'https://example.com\nfoo']:
            self.assertIsNone(report.safe_url(url))

    def test_coverage_index_is_rejected(self):
        path = self.root / 'coverage.json'
        path.write_text(json.dumps({'devices': [{'name': 'Device', 'chip_entry_count': 5}]}))
        with self.assertRaisesRegex(ValueError, 'coverage indexes'):
            report.build_report([path], self.catalog)

    def test_unverified_catalog_entry_is_rejected(self):
        path = self.root / 'catalog.json'
        path.write_text(json.dumps({'entries': {'BMA280': {'url': 'https://example.com/file.pdf'}}}))
        with self.assertRaisesRegex(ValueError, 'verification record'):
            report.load_catalog(path)

    def test_csv_does_not_execute_spreadsheet_formulas(self):
        data = report.build_report([self.inventory('=HYPERLINK("https://example.com")')], self.catalog)
        path = self.root / 'chips.csv'
        report.write_csv(path, data)
        with path.open(encoding='utf-8-sig', newline='') as f:
            rows = list(csv.reader(f))
        self.assertTrue(rows[1][2].startswith("'="))
        self.assertIn('Datasheet search (not verified)', rows[0])

    def test_outputs_cannot_overwrite_input_files(self):
        path = self.inventory()
        before = path.read_bytes()
        with self.assertRaises(SystemExit):
            report.main([str(path), '--output', str(path)])
        self.assertEqual(path.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
