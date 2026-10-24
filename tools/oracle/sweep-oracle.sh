#!/bin/bash
# run the oracle over every corpus file sequentially; summary table in oracle-out/_sweep.tsv
cd ~/dwg-research
: > oracle-out/_sweep.tsv
for f in corpus/*.dwg; do
  s=$(basename $f .dwg)
  [ -f oracle-out/$s/done.flag ] && continue
  t=$(date +%s)
  tools/oracle/dwgq run $f --timeout 300 > oracle-out/_last.log 2>&1
  printf "%s\t%s\t%ss\t%s\n" $s "$(grep -c '"ok":  true' oracle-out/_last.log)/3" $(( $(date +%s)-t )) "$(ls oracle-out/$s/plots 2>/dev/null | grep -c pdf)pdf" >> oracle-out/_sweep.tsv
done
echo FINISHED >> oracle-out/_sweep.tsv
