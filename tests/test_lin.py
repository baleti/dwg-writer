import math, unittest
import dwglin


class LinTests(unittest.TestCase):
    def test_simple(self):
        r = dwglin.parse_lin("*DASHED,Dashed __ __\nA,12.5,-6.25\n")
        self.assertEqual(r['DASHED'], ('Dashed __ __', [12.5, -6.25]))

    def test_comments_blank_crlf_case(self):
        t = ";c\r\n\r\n*dot ,Dot . .  ; trailing\r\na, 0 , -.25\r\n"
        r = dwglin.parse_lin(t)
        self.assertEqual(r['DOT'], ('Dot . .', [0.0, -0.25]))

    def test_no_description_and_no_newline(self):
        r = dwglin.parse_lin("*DOT\nA,0,-1e-3")
        self.assertEqual(r['DOT'], ('', [0.0, -0.001]))

    def test_text(self):
        r = dwglin.parse_lin('*GAS,Gas line\nA,12.5,-2.5,["GA,S]",STANDARD,s=1.0,R=90,X=-1.0,Y=-0.5],-2.5\n')
        d = r['GAS'][1]
        self.assertEqual(d[0], 12.5)
        self.assertEqual(d[2], -2.5)
        e = d[1]
        self.assertEqual(e['text'], 'GA,S]'); self.assertEqual(e['style'], 'STANDARD')
        self.assertAlmostEqual(e['rotation'], math.pi / 2); self.assertEqual((e['x'], e['y'], e['scale']), (-1.0, -0.5, 1.0))
        self.assertNotIn('absolute', e)

    def test_text_length_belongs_to_preceding_number(self):
        r = dwglin.parse_lin('*T,t\nA,5,-2.5,["X",STANDARD,A=45],-2.5\n')
        e = r['T'][1][1]
        self.assertEqual(e['length'], -2.5)
        self.assertTrue(e['absolute']); self.assertAlmostEqual(e['rotation'], math.pi / 4)

    def test_shape(self):
        r = dwglin.parse_lin('*S,s\nA,5,-5,[BOX,ltypeshp.shx,S=0.1,X=-0.1],-5\n')
        e = r['S'][1][1]
        self.assertEqual((e['shape_name'], e['shxfile'], e['scale'], e['x']), ('BOX', 'ltypeshp.shx', 0.1, -0.1))
        r = dwglin.parse_lin('*S,s\nA,5,[130,ltypeshp.shx],-5\n')
        self.assertEqual(r['S'][1][0]['shape'], 130)      # the element directly follows the length 5, so it carries length 5 and sits at index 0

    def test_errors_and_duplicates(self):
        with self.assertRaises(ValueError) as c:
            dwglin.parse_lin('*A,x\nA,1,abc\n')
        self.assertIn('2', str(c.exception))
        with self.assertRaises(ValueError):
            dwglin.parse_lin('A,1,-1\n')
        r = dwglin.parse_lin('*A,one\nA,1,-1\n*a,two\nA,2,-2\n')
        self.assertEqual(r['A'], ('two', [2.0, -2.0]))


if __name__ == '__main__':
    unittest.main()
