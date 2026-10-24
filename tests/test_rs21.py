import glob, os, unittest, dwgr21, dwgrs21, r21

CORPUS = os.path.expanduser('~/dwg-research/corpus')


class Rs21(unittest.TestCase):
    def test_pages_reencode(self):
        fs = sorted(glob.glob(os.path.join(CORPUS, 'AC1021*.dwg')))[:2]
        if not fs: self.skipTest('no local corpus')
        n = 0
        for f in fs:
            buf = open(f, 'rb').read(); info = dwgr21.open_r21(buf)
            for name, s in info['sections'].items():
                if s['encoded'] == 1: continue
                for ent in s['pages'][:3]:
                    off, size, pid, usz, csz = ent[:5]
                    pos, psz = info['pagemap']['pages'][pid]
                    k = -(-csz // 251)
                    self.assertEqual(dwgrs21.encode_page(dwgr21._rs_bytes(buf, pos, psz, 251, k)), bytes(buf[pos:pos + k * 255]), (f, name, pid))
                    n += 1
        self.assertGreater(n, 0)

    def test_system_pages_reencode(self):
        fs = sorted(glob.glob(os.path.join(CORPUS, 'AC1021*.dwg')))
        if not fs: self.skipTest('no local corpus')
        for f in fs:
            buf = open(f, 'rb').read(); blk = buf[0x80:0x80 + 0x3d8]
            data = b''.join(blk[k:0x2fd:3][:239] for k in range(3))
            self.assertEqual(dwgrs21.encode_system(data, 3), bytes(blk[:765]), f)
            q = r21.system_header(buf); pm = r21.page_map(buf, q); k = pm['k']; off = q[7] + 0x480
            raw = bytes(buf[off:off + 255 * k]); d2 = b''.join(raw[j::k][:239] for j in range(k))
            self.assertEqual(dwgrs21.encode_system(d2, k), raw, f)


if __name__ == '__main__': unittest.main()
