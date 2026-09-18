import gzip
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('checker', Path(__file__).parents[1] / 'scripts/check_scan_pins.py')
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)

PIN = '''Version 1.0;
PinDescription { Resource DPin {
 DATA_0;
 RESULT;
 AUX;
 Group nested { DATA_0 }
 Group stm_scan_in { nested }
 Group stm_scan_out { RESULT }
 Group stm_scan_nonclk_dpin { AUX }
} }
'''
STIL = '''STIL 1.0;
// ScanStructures { fake }
Ann {* ignored ScanStructures { } *}
ScanStructures {
 ScanChain c {
  ScanIn "data"[0];
  ScanOut "RESULT";
  ScanMasterClock "CLK";
 }
}
'''


class CheckerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.pin = self.root / 'example_ddr_rev0.pin'
        self.pin.write_text(PIN)
        self.groups = checker.load_groups(self.pin, checker.DEFAULT_GROUPS)

    def run_stil(self, text=STIL, compressed=False):
        path = self.root / ('sample.stil.gz' if compressed else 'sample.stil')
        if compressed:
            with gzip.open(path, 'wt') as stream:
                stream.write(text)
        else:
            path.write_text(text)
        return checker.check_file(path, self.groups)

    def test_plain_and_gzip(self):
        for compressed in (False, True):
            result = self.run_stil(compressed=compressed)
            self.assertEqual(result['status'], 'PASS')
            self.assertEqual(result['pins'][0]['line'], 6)
            self.assertEqual(result['clocks_info_only'], ['CLK'])

    def test_union_not_direction(self):
        result = self.run_stil(STIL.replace('"data"[0]', '"RESULT"').replace('ScanOut "RESULT"', 'ScanOut "AUX"'))
        self.assertEqual(result['status'], 'PASS')

    def test_missing_pin(self):
        result = self.run_stil(STIL.replace('"RESULT"', '"MISSING"'))
        self.assertEqual(result['status'], 'FAIL')
        self.assertEqual(result['pins'][1]['groups'], [])

    def test_absent_scanin(self):
        result = self.run_stil(STIL.replace('  ScanIn "data"[0];\n', ''))
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['absent_fields'], [{'chain': 'c', 'field': 'ScanIn'}])

    def test_no_pins_not_pass(self):
        self.assertEqual(self.run_stil('STIL 1.0;\n')['status'], 'UNDETERMINED')

    def test_multiple_blocks(self):
        self.assertEqual(self.run_stil(STIL + STIL)['chains'], 2)

    def test_comments_and_braces_in_quotes(self):
        text = STIL.replace('ScanChain c', 'ScanChain "c{foo}"').replace('ScanIn', '/* fake { } */ ScanIn')
        self.assertEqual(self.run_stil(text)['status'], 'PASS')

    def test_malformed_declaration(self):
        self.assertEqual(self.run_stil(STIL.replace('"data"[0];', '"data"[0]'))['status'], 'ERROR')

    def test_unclosed_block(self):
        self.assertEqual(self.run_stil(STIL.rsplit('}', 1)[0])['status'], 'ERROR')

    def test_unclosed_comment(self):
        self.assertEqual(self.run_stil(STIL + '/*')['status'], 'ERROR')

    def test_normalization(self):
        for value in ('"data"[0]', '"data[0]"', 'data[0]'):
            self.assertEqual(checker.normalize(value), 'DATA_0')
        with self.assertRaises(checker.ParseError):
            checker.normalize('"data"[0..3]')

    def test_missing_group(self):
        with self.assertRaises(checker.ParseError):
            checker.load_groups(self.pin, ('missing',))

    def test_group_cycle(self):
        self.pin.write_text(PIN.replace('Group nested { DATA_0 }', 'Group nested { stm_scan_in }'))
        with self.assertRaises(checker.ParseError):
            checker.load_groups(self.pin, checker.DEFAULT_GROUPS)

    def test_unknown_group_member(self):
        self.pin.write_text(PIN.replace('Group nested { DATA_0 }', 'Group nested { UNKNOWN }'))
        with self.assertRaises(checker.ParseError):
            checker.load_groups(self.pin, checker.DEFAULT_GROUPS)

    def test_truncated_gzip(self):
        path = self.root / 'bad.stil.gz'
        path.write_bytes(gzip.compress(STIL.encode())[:-8])
        self.assertEqual(checker.check_file(path, self.groups)['status'], 'ERROR')


if __name__ == '__main__':
    unittest.main()