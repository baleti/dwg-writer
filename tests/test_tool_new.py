import os, json, tempfile, unittest
import dwgtool, dwgdoc

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@unittest.skipUnless(os.path.exists(os.path.join(HERE, 'templates', 'blank_2000.dwg')), 'local blank template missing')
class New(unittest.TestCase):
    def test_new_from_json(self):
        spec = {"layers": [{"name": "W", "color": 1}], "entities": [{"type": "line", "p1": [0, 0], "p2": [5, 5], "layer": "W"}, {"type": "circle", "c": [1, 1], "r": 2}]}
        with tempfile.TemporaryDirectory() as t:
            sp = os.path.join(t, 's.json'); json.dump(spec, open(sp, 'w'))
            for y in ('2000', '2018'):
                out = os.path.join(t, y + '.dwg'); self.assertEqual(dwgtool.build(sp, out, y), 0)
                d = dwgdoc.Doc(open(out, 'rb').read()); self.assertIn('w', d.layers()); self.assertEqual(len(d.entities('*Model_Space')), 2)


if __name__ == '__main__': unittest.main()
