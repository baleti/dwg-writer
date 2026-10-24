import random,sys,collections
S="/tmp/claude-1000/-home-user1-dwg-research/436e3bc9-47f7-4afa-8749-73d77b7c9f1c/scratchpad/"
rows=[l.rstrip("\n").split("\t") for l in open(S+"cands.tsv")]
random.seed(1); random.shuffle(rows)
out=open(S+"magics2.tsv","w"); c=collections.Counter()
for p,sz in rows[600:2600]:
    try:
        with open(p,"rb") as f: m=f.read(6)
    except Exception as e: continue
    m=m.decode("latin1"); c[m]+=1; out.write(f"{m}\t{sz}\t{p}\n")
print(c)
