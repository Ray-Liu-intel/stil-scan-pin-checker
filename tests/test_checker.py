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

    def test_multiple_scan_master_clocks(self):
        for compressed in (False, True):
            result = self.run_stil(STIL.replace('ScanMasterClock "CLK";',
                                  'ScanMasterClock "CLK" "bus"[2] OTHER;'), compressed)
            self.assertEqual(result['status'], 'PASS')
            self.assertEqual(result['clocks_info_only'], ['BUS_2', 'CLK', 'OTHER'])
            self.assertEqual(len(result['pins']), 2)

    def test_invalid_scan_master_clock_list(self):
        result = self.run_stil(STIL.replace('ScanMasterClock "CLK";',
                              'ScanMasterClock "CLK" + "OTHER";'))
        self.assertEqual(result['status'], 'ERROR')

    def test_scanin_wrong_direction_fails(self):
        result = self.run_stil(STIL.replace('"data"[0]', '"RESULT"').replace('ScanOut "RESULT"', 'ScanOut "AUX"'))
        self.assertEqual(result['status'], 'FAIL')
        self.assertEqual(result['pins'][0]['failure'], 'DIRECTION_MISMATCH')
        self.assertTrue(result['pins'][1]['passed'])

    def test_scanout_wrong_direction_fails(self):
        result = self.run_stil(STIL.replace('ScanOut "RESULT"', 'ScanOut "data"[0]'))
        self.assertEqual(result['status'], 'FAIL')
        self.assertEqual(result['pins'][1]['failure'], 'DIRECTION_MISMATCH')

    def test_dpin_exempts_both_directions(self):
        result = self.run_stil(STIL.replace('"data"[0]', '"AUX"').replace('"RESULT"', '"AUX"'))
        self.assertEqual(result['status'], 'PASS')
        self.assertTrue(all(row['passed'] and not row['direction_matches'] for row in result['pins']))

    def test_custom_group_names_direction_order(self):
        self.groups = dict(zip(('custom_in', 'custom_out', 'custom_dp'), self.groups.values()))
        result = self.run_stil(STIL.replace('ScanOut "RESULT"', 'ScanOut "data"[0]'))
        self.assertEqual(result['status'], 'FAIL')
        self.assertEqual(result['pins'][1]['expected_group'], 'custom_out')

    def test_swapped_directions_block_channellink(self):
        text = STIL.replace('ScanIn "data"[0]', 'ScanIn "RESULT"').replace('ScanOut "RESULT"', 'ScanOut "data"[0]')
        result = self.body_result(text)
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(all(row['failure'] == 'DIRECTION_MISMATCH' for row in result['pins']))
        self.assertEqual(checker.export_channel_link(result, checker.DEFAULT_GROUPS[:2])['action'], 'SKIPPED')
        self.assertFalse((self.root / 'v1_Channellink').exists())

    def test_wrong_direction_with_dpin_passes_but_not_chl(self):
        self.groups['stm_scan_nonclk_dpin'].add('RESULT')
        result = self.body_result(STIL.replace('ScanIn "data"[0]', 'ScanIn "RESULT"'))
        self.assertEqual(result['status'], 'PASS')
        self.assertFalse(checker.channel_link_plan(result, checker.DEFAULT_GROUPS[:2])['eligible'])

    def test_both_direction_groups_allow_correct_role(self):
        self.groups['stm_scan_out'].add('DATA_0')
        result = self.body_result()
        self.assertEqual(result['status'], 'PASS')
        self.assertTrue(checker.channel_link_plan(result, checker.DEFAULT_GROUPS[:2])['eligible'])

    def test_missing_pin(self):
        result = self.run_stil(STIL.replace('"RESULT"', '"MISSING"'))
        self.assertEqual(result['status'], 'FAIL')
        self.assertEqual(result['pins'][1]['groups'], [])
        self.assertEqual(result['pins'][1]['failure'], 'PIN_NOT_FOUND')

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

    def body_result(self, text=STIL, filename='sample_body_v1_TC100.stil.gz'):
        path = self.root / filename
        path.write_bytes(gzip.compress(text.encode()) if filename.lower().endswith('.gz') else text.encode())
        return checker.check_file(path, self.groups)

    def test_channel_copy_and_repeat(self):
        result = self.body_result()
        source = Path(result['file'])
        original = source.read_bytes()
        plan = checker.export_channel_link(result, checker.DEFAULT_GROUPS[:2])
        destination = self.root / 'v1_Channellink/sample_body_v1_TC100_CHL.stil.gz'
        self.assertEqual(plan['action'], 'COPIED')
        self.assertEqual(destination.read_bytes(), original)
        self.assertEqual(source.read_bytes(), original)
        self.assertEqual(checker.export_channel_link(result, checker.DEFAULT_GROUPS[:2])['action'], 'ALREADY_EXISTS')
        self.assertEqual(checker.find_inputs(self.root), [source])

    def test_nonclk_only_is_not_channel_link(self):
        result = self.body_result(STIL.replace('"RESULT"', '"AUX"'))
        self.assertEqual(result['status'], 'PASS')
        self.assertFalse(checker.channel_link_plan(result, checker.DEFAULT_GROUPS[:2])['eligible'])

    def test_overlapping_groups_allow_channel_link(self):
        self.groups['stm_scan_nonclk_dpin'].add('DATA_0')
        result = self.body_result()
        self.assertTrue(checker.channel_link_plan(result, checker.DEFAULT_GROUPS[:2])['eligible'])

    def test_channel_link_skip_non_body_and_failed_inputs(self):
        cases = [('sample_setup_v1.stil', STIL),
                 ('sample_body_setup_v1.stil', STIL),
                 ('sample_body_v1.stil', STIL.replace('"RESULT"', '"MISSING"')),
                 ('empty_body_v1.stil', 'STIL 1.0;'),
                 ('bad_body_v1.stil', STIL + '/*')]
        for filename, text in cases:
            with self.subTest(filename=filename):
                result = self.body_result(text, filename)
                self.assertEqual(checker.export_channel_link(result, checker.DEFAULT_GROUPS[:2])['action'], 'SKIPPED')
        self.assertFalse((self.root / 'v1_Channellink').exists())

    def test_channel_link_dry_run(self):
        result = self.body_result()
        self.assertEqual(checker.export_channel_link(result, checker.DEFAULT_GROUPS[:2], True)['action'], 'WOULD_COPY')
        self.assertFalse((self.root / 'v1_Channellink').exists())

    def test_channel_link_conflict_never_overwrites(self):
        result = self.body_result()
        plan = checker.channel_link_plan(result, checker.DEFAULT_GROUPS[:2])
        destination = Path(plan['destination'])
        destination.parent.mkdir()
        destination.write_bytes(b'keep me')
        self.assertEqual(checker.export_channel_link(result, checker.DEFAULT_GROUPS[:2])['action'], 'ERROR')
        self.assertEqual(destination.read_bytes(), b'keep me')

    def test_channel_link_plain_stil_and_absent_scanin(self):
        result = self.body_result(STIL.replace('  ScanIn "data"[0];\n', ''), 'sample_body_V2.stil')
        plan = checker.export_channel_link(result, checker.DEFAULT_GROUPS[:2])
        self.assertEqual(plan['action'], 'COPIED')
        self.assertEqual(Path(plan['destination']).name, 'sample_body_V2_CHL.stil')
        self.assertEqual(Path(plan['destination']).parent.name, 'v2_Channellink')

    def test_channel_link_missing_or_ambiguous_version(self):
        for name in ('sample_body.stil', 'sample_body_v1_v2.stil'):
            result = self.body_result(filename=name)
            self.assertEqual(checker.channel_link_plan(result, checker.DEFAULT_GROUPS[:2])['action'], 'ERROR')

    def test_channel_link_generated_outputs_excluded(self):
        result = self.body_result(filename='sample_body_v1_CHL.stil')
        self.assertFalse(checker.channel_link_plan(result, checker.DEFAULT_GROUPS[:2])['eligible'])
        self.assertEqual(checker.find_inputs(self.root), [])


if __name__ == '__main__':
    unittest.main()