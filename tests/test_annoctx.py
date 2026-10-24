"""MTEXT annotation-scale context data: the default context equals the entity's own geometry (skipped without the proprietary corpus)."""
import os, glob, unittest
ROOT = os.path.join(os.path.dirname(__file__), '..')


class AnnoCtx(unittest.TestCase):
    def test_default_context_equals_entity(self):
        import dwgmodel
        fs = glob.glob(os.path.join(ROOT, 'corpus', 'AC1027_13_*.dwg'))
        if not fs: self.skipTest('corpus missing')
        m = dwgmodel.Model(open(fs[0], 'rb').read())
        ent = {e['handle']: e for _, e in m.entities() if e.get('kind') == 'MTEXT'}
        n = 0
        for h, ctxs in m.annotation_contexts().items():
            for c in ctxs:
                if c['kind'] == 'MTEXT' and c['default'] and h in ent:
                    e = ent[h]; n += 1
                    self.assertAlmostEqual(c['width'], e['width'], 6); self.assertAlmostEqual(c['ext_w'], e['ext_w'], 6)
                    self.assertEqual(c['attachment'], e['attachment'])
                    for a, b in zip(c['ins'], e['ins']): self.assertAlmostEqual(a, b, 6)
        self.assertGreater(n, 300)
        led = {e['handle']: e for _, e in m.entities() if e.get('kind') == 'LEADER'}
        k = 0
        for h, ctxs in m.annotation_contexts().items():
            for c in ctxs:
                if c['kind'] == 'LEADER' and c['default'] and h in led:
                    k += 1; self.assertEqual(len(c['pts']), len(led[h]['pts']))
                    for p, q in zip(c['pts'], led[h]['pts']):
                        for a, b in zip(p, q): self.assertAlmostEqual(a, b, 6)
        self.assertGreater(k, 200)


if __name__ == '__main__':
    unittest.main()
