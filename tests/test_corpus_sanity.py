"""Regression checks against the local corpus and AutoCAD dumps (skipped when the proprietary files are absent)."""
import os, json, unittest
ROOT = os.path.join(os.path.dirname(__file__), '..')
def have(stem): return os.path.exists(os.path.join(ROOT, 'corpus', stem + '.dwg')) and os.path.exists(os.path.join(ROOT, 'oracle-out', stem, 'dump.json'))
UNITS = {'Undefined': 0, 'Inches': 1, 'Feet': 2, 'Millimeters': 4, 'Centimeters': 5, 'Meters': 6}


class CorpusSanity(unittest.TestCase):
    def test_insunits_equal_dump(self):
        import dwgmodel
        n = 0
        for stem in ('AC1015_40_ecfe783b', 'AC1021_01_903df59c', 'AC1024_02_c9e40a32', 'AC1027_13_048c555f', 'AC1032_00_c95ae221'):
            if not have(stem): continue
            h = dwgmodel.Model(open(os.path.join(ROOT, 'corpus', stem + '.dwg'), 'rb').read()).header()
            j = json.load(open(os.path.join(ROOT, 'oracle-out', stem, 'dump.json')))['header']
            self.assertEqual(h.get('INSUNITS'), UNITS[j['Insunits']], stem); n += 1
        if not n: self.skipTest('corpus missing')

    def test_text_alignment_kept(self):
        import dwgmodel
        stem = 'AC1027_13_048c555f'
        if not have(stem): self.skipTest('corpus missing')
        m = dwgmodel.Model(open(os.path.join(ROOT, 'corpus', stem + '.dwg'), 'rb').read())
        al = [(e['halign'], e['valign']) for b, e in m.entities() if e['kind'] == 'TEXT']
        self.assertIn((5, 0), al); self.assertIn((2, 2), al)

    def test_u_blocks_not_self_referenced(self):
        import dwgmodel, collections
        stem = 'AC1021_10_bcb101ca'
        if not have(stem): self.skipTest('corpus missing')
        m = dwgmodel.Model(open(os.path.join(ROOT, 'corpus', stem + '.dwg'), 'rb').read())
        j = json.load(open(os.path.join(ROOT, 'oracle-out', stem, 'dump.json')))
        ora = collections.Counter(); [ora.update(b['entity_counts']) for b in j['blocks']]
        self.assertEqual(sum(1 for b, e in m.entities() if e['kind'] == 'LINE'), ora['LINE'])


if __name__ == '__main__':
    unittest.main()
