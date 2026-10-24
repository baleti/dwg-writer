import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import dwgdoc

T = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'templates', 'blank_%s.dwg')


class LayoutEdit(unittest.TestCase):
    def test_rename_set_viewport(self):
        for v in ('2000', '2010', '2018'):
            if not os.path.exists(T % v): continue
            d = dwgdoc.Doc(open(T % v, 'rb').read())
            d.add_layer('HIDEME'); d.add_layout('Plan')
            d.add_viewport('Plan', (210, 148.5), (420, 297), paper_viewport=True)
            vp = d.add_viewport('Plan', (210, 148.5), (200, 150), view_center=(50, 50), scale=0.5)
            d.rename_layout('Plan', 'Plan A'); d.set_layout('Plan A', paper=(297, 210))
            d.set_viewport(vp, scale=1 / 50, view_center=(10, 20), frozen=['HIDEME'], size=(180, 120))
            d2 = dwgdoc.Doc(d.save())
            self.assertIn('Plan A', d2.layouts()); self.assertNotIn('Plan', d2.layouts())
            self.assertEqual(d2.get(d2.layouts()['Plan A'])['paper'], (297.0, 210.0))
            x = d2.get(vp)
            self.assertAlmostEqual(x['view_height'], 6000.0); self.assertEqual(x['view_center'], (10.0, 20.0)); self.assertEqual(len(x['frozen']), 1)
            self.assertEqual((x['width'], x['height']), (180.0, 120.0))
            with self.assertRaises(ValueError): d.rename_layout('Model', 'X')


if __name__ == '__main__':
    unittest.main()
