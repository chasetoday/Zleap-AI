#!/usr/bin/env python3
"""Validate scores and print descriptive benchmark metrics. No model API calls."""
from pathlib import Path
import csv,collections,json
ROOT=Path(__file__).resolve().parents[1]
scores_path=ROOT/'outputs/scoring_benchmark_30.csv'
data_path=ROOT/'data/processed/eval_cases_benchmark_v03_scored.csv'
with scores_path.open(encoding='utf-8-sig',newline='') as f:scores=list(csv.DictReader(f))
with data_path.open(encoding='utf-8-sig',newline='') as f:cases={r['Case_ID']:r for r in csv.DictReader(f)}
assert len(scores)==30
assert [r['Case_ID'] for r in scores]==[f'TC{i:03}' for i in range(5,35)]
metrics=['Factual_Correctness','Citation_Correctness','Answer_Completeness','Groundedness']
for r in scores:
 assert all(r[x] in ('Pass','Fail','N/A') for x in metrics),(r['Case_ID'],r)
 assert r['Case_ID'] in cases and cases[r['Case_ID']]['Evaluation_Phase']=='Benchmark'
print('Benchmark评测案例：',len(scores))
for m in metrics:
 counts=collections.Counter(r[m] for r in scores)
 denom=counts['Pass']+counts['Fail']
 print(f'{m}: Pass {counts["Pass"]}/{denom} ({counts["Pass"]/denom:.1%})，N/A {counts["N/A"]}')
full=sum(all(r[m]=='Pass' for m in metrics) for r in scores)
print(f'四维全部通过：{full}/{len(scores)} ({full/len(scores):.1%})')
bytype=collections.defaultdict(list)
for r in scores:bytype[cases[r['Case_ID']]['Test_Type']].append(r)
for typ,rr in sorted(bytype.items()):
 pass_n=sum(all(r[m]=='Pass' for m in metrics) for r in rr)
 print(f'{typ}: {pass_n}/{len(rr)}')
print('复核标记：',', '.join(r['Case_ID'] for r in scores if any(r[m]=='Fail' for m in metrics)))
print('注意：分数为Rubric初评标签（AI辅助，尚待独立人工复核）；本脚本仅汇总，不自动打分。')
