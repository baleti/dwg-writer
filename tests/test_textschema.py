import unittest
import dwgtextschema as S

def good():
    return dict(file='a.dwg', schema_version=1, version='AC1032', status='ok', errors=[], size=10, codepage=30, summary={}, app=[], header={}, layers=['0'], blocks=[],
                layouts=[dict(name='Model', paper='', size_mm=[0.0, 0.0], viewports=0)], entity_counts={'LINE': 2}, text={'*Model_Space': ['a']}, attributes=[],
                dimension_text=[], items=[dict(kind='TEXT', block='*Model_Space', text='a')])

class T(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(S.validate(good()), [])

    def test_unsupported_needs_only_basics(self):
        self.assertEqual(S.validate(dict(file='a', schema_version=1, version='AC1009', status='unsupported', errors=['x'], size=5)), [])

    def test_missing_and_bad(self):
        r = good(); del r['layers']; r['status'] = 'weird'
        p = S.validate(r)
        self.assertTrue(any(x.startswith('status') for x in p)); self.assertTrue(any(x.startswith('layers') for x in p))

    def test_nested_paths(self):
        r = good(); r['layouts'][0]['viewports'] = 'x'
        p = S.validate(r); self.assertTrue(any(x.startswith('layouts[0].viewports') for x in p), p)

    def test_optional_types(self):
        r = good(); r['tables'] = [dict(handle='x', block='b', texts=['a'])]; r['images'] = [dict(path='p', count=1)]
        p = S.validate(r); self.assertTrue(any(x.startswith('tables[0].handle') for x in p), p)
        r['tables'][0]['handle'] = 5; self.assertEqual(S.validate(r), [])

    def test_extra_keys_allowed(self):
        r = good(); r['future'] = 1; self.assertEqual(S.validate(r), [])

    def test_wrong_schema_version(self):
        r = good(); r['schema_version'] = 2
        self.assertTrue(any(x.startswith('schema_version') for x in S.validate(r)))

if __name__ == '__main__':
    unittest.main()
