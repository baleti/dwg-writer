"""R12 (AC1009) reader against the AutoCAD dumps (skipped when the proprietary files are absent)."""
import os, json, collections, unittest
ROOT = os.path.join(os.path.dirname(__file__), '..')
def have(stem): return os.path.exists(os.path.join(ROOT, 'corpus', stem + '.dwg')) and os.path.exists(os.path.join(ROOT, 'oracle-out', stem, 'dump.json'))


class R12(unittest.TestCase):
    def test_block_entity_counts_equal_autocad(self):
        import dwgr12
        n = 0
        for stem in ('AC1009_54_023f53f0', 'AC1009_51_1c590374'):
            if not have(stem): continue
            m = dwgr12.Model12(open(os.path.join(ROOT, 'corpus', stem + '.dwg'), 'rb').read())
            ours = collections.defaultdict(collections.Counter)
            for bn, e in m.entities():
                if e['kind'] not in ('VERTEX2D', 'SEQEND', 'ATTRIB'): ours[bn][{'POLYLINE2D': 'LWPOLYLINE', 'DIM_LINEAR': 'DIMENSION'}.get(e['kind'], e['kind'])] += 1
            j = json.load(open(os.path.join(ROOT, 'oracle-out', stem, 'dump.json')))
            for blk in j['blocks']:
                t = collections.Counter({'POLYLINE': 'LWPOLYLINE'}.get(e['t'], e['t']) for e in blk.get('entities', []) if e['t'] != 'ATTRIB')
                self.assertEqual(dict(ours.get(blk['name'], {})), dict(t), (stem, blk['name']))
            n += 1
        if not n: self.skipTest('corpus missing')


class R14(unittest.TestCase):
    def test_polylines_and_spaces_equal_autocad(self):
        import dwgmodel
        n = 0
        for stem in ('AC1014_18_d634d535', 'AC1014_48_5e2623e9'):
            if not have(stem): continue
            m = dwgmodel.Model(open(os.path.join(ROOT, 'corpus', stem + '.dwg'), 'rb').read())
            c = collections.Counter(e['kind'] for bn, e in m.entities() if e['kind'] in ('POLYLINE2D', 'POLYLINE3D', 'LWPOLYLINE'))
            j = json.load(open(os.path.join(ROOT, 'oracle-out', stem, 'dump.json')))
            t = collections.Counter(e['t'] for b in j['blocks'] for e in b.get('entities', []) if e['t'] in ('POLYLINE', 'LWPOLYLINE'))
            self.assertEqual(sum(c.values()), sum(t.values()), stem)
            n += 1
        if not n: self.skipTest('corpus missing')

    def test_paper_space_not_flooded(self):
        import dwgmodel
        stem = 'AC1014_06_b7993814'
        if not have(stem): self.skipTest('corpus missing')
        m = dwgmodel.Model(open(os.path.join(ROOT, 'corpus', stem + '.dwg'), 'rb').read())
        paper = sum(1 for bn, e in m.entities() if bn == '*PAPER_SPACE')
        self.assertLess(abs(paper - 517), 10)


class Extraction(unittest.TestCase):
    def test_dwg2text_old_versions_have_entities(self):
        import dwg2text
        n = 0
        for stem in ('AC1009_54_023f53f0', 'AC1012_46_ab33ce98', 'AC1014_37_310a73af'):
            f = os.path.join(ROOT, 'corpus', stem + '.dwg')
            if not os.path.exists(f): continue
            res, rc = dwg2text.extract(f) if hasattr(dwg2text, 'extract') else (None, None)
            if res is None: self.skipTest('no extract() API')
            self.assertGreater(sum(res['entity_counts'].values()), 100, stem)
            self.assertFalse([e for e in res['errors'] if e.startswith(('entities', 'images'))], stem)
            n += 1
        if not n: self.skipTest('corpus missing')

    def test_dwg2text_every_version(self):
        import dwg2text
        n = 0
        for stem in ('AC1015_40_ecfe783b', 'AC1018_42_929ace9f', 'AC1021_01_903df59c', 'AC1024_02_c9e40a32', 'AC1027_16_919d9f20', 'AC1032_00_c95ae221'):
            f = os.path.join(ROOT, 'corpus', stem + '.dwg')
            if not os.path.exists(f): continue
            res, rc = dwg2text.extract(f)
            self.assertEqual((res['status'], rc), ('ok', 0), stem)
            self.assertGreater(sum(res['entity_counts'].values()), 10, stem)
            n += 1
        if not n: self.skipTest('corpus missing')
