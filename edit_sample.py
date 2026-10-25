"""edit_sample.py: pick a stratified sample of real drawings from the catalogue into ~/dwg-edit-tests/src (git-excluded, local only).
Usage: edit_sample.py N [seed]. Reports only ids and aggregate counts."""
import csv, os, sys, random, shutil, collections
CENSUS = os.path.expanduser('~/dwg-research/campaign21/census.tsv'); DST = os.path.expanduser('~/dwg-edit-tests/src/')
QUOTA = {'AC1015': .08, 'AC1018': .12, 'AC1021': .15, 'AC1024': .22, 'AC1027': .18, 'AC1032': .25}
def main():
    n = int(sys.argv[1]); rng = random.Random(int(sys.argv[2]) if len(sys.argv) > 2 else 1)
    rows = [r for r in csv.reader(open(CENSUS), delimiter='\t')][1:]
    by = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in rows:
        if len(r) < 5 or r[1] not in QUOTA: continue
        try: s = int(r[2])
        except ValueError: continue
        if 60000 <= s <= 6000000 and os.path.exists(r[4]): by[r[1]][r[3] + '|' + os.path.dirname(r[4])].append(r)
    os.makedirs(DST, exist_ok=True); got = collections.Counter(); out = []
    for v, q in QUOTA.items():
        groups = list(by[v].values()); rng.shuffle(groups); k = max(1, round(n * q))
        for i in range(k):
            if not groups: break
            r = rng.choice(groups[i % len(groups)]); dst = '%s_%s.dwg' % (r[1], r[0])
            if not os.path.exists(DST + dst): shutil.copyfile(r[4], DST + dst)
            got[v] += 1; out.append((dst, r[2]))
    with open(os.path.expanduser('~/dwg-edit-tests/sample.tsv'), 'w') as f:
        for d, s in out: f.write('%s\t%s\n' % (d, s))
    print(dict(got), sum(got.values()))
main()
