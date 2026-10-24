import glob, os, unittest, dwgmodel

CORPUS = os.path.expanduser('~/dwg-research/corpus')


class LayoutOptions(unittest.TestCase):
    def test_plot_options_match_flag_word(self):
        fs = sorted(glob.glob(os.path.join(CORPUS, 'AC1032*.dwg')), key=os.path.getsize)[:1]
        if not fs: self.skipTest('no local corpus')
        m = dwgmodel.Model(open(fs[0], 'rb').read())
        n = 0
        for l in m.layouts():
            if 'plot_flags' not in l: continue
            n += 1
            for bit, name in dwgmodel.PLOT_FLAG_BITS: self.assertEqual(l['plot_options'][name], bool(l['plot_flags'] >> bit & 1))
            self.assertTrue(l['plot_options']['PlotPlotStyles'] or l['plot_flags'] >> 5 & 1 == 0)
        self.assertGreater(n, 0)

    def test_layer_overrides_shape(self):
        fs = sorted(glob.glob(os.path.join(CORPUS, 'AC1032*.dwg')), key=os.path.getsize)[:1]
        if not fs: self.skipTest('no local corpus')
        m = dwgmodel.Model(open(fs[0], 'rb').read())
        for layer, d in m.layer_overrides().items():
            self.assertIn(layer, m.layers)
            for vp, v in d.items(): self.assertIsInstance(v, dict)





class NamedViews(unittest.TestCase):
    def test_ucs_matches_autocad(self):
        fs = glob.glob(os.path.join(CORPUS, 'AC1027_23*.dwg'))
        if not fs: self.skipTest('no local corpus')
        m = dwgmodel.Model(open(fs[0], 'rb').read())
        u = {x['name']: x for x in m.ucs_list()}
        self.assertIn('REVIT60-Internal', u)
        self.assertEqual(u['REVIT60-Internal']['xaxis'], (1.0, 0.0, 0.0))
        self.assertEqual(u['REVIT60-Internal']['yaxis'], (0.0, 1.0, 0.0))
if __name__ == '__main__': unittest.main()
