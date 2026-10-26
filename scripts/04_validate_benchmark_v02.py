#!/usr/bin/env python3
"""Read-only benchmark checks: source docs, case counts, required fields and score status."""
from pathlib import Path
import csv, hashlib, sys
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'/'benchmark.csv'
files={"KB-001 V1.0":"KB_001_Employee_Policies_V1.txt","KB-002 V1.0":"KB_002_Policy_Version_Registry_V1.txt"}
with DATA.open(encoding="utf-8-sig",newline="") as f: rows=list(csv.DictReader(f))
errors=[]
ids=[r['Case_ID'] for r in rows]
if ids!=[f"TC{i:03}" for i in range(1,35)]: errors.append("编号不完整或顺序不正确")
for r in rows:
 cid=r['Case_ID']
 if not all(r.get(x) for x in ['Question','Expected_Answer','Reference_Evidence','Test_Type','Knowledge_Base_Set','Evaluation_Phase']):errors.append(cid+':关键字段为空')
 for key in [a.strip() for a in r['Knowledge_Base_Set'].split('+')]:
  if key not in files: errors.append(cid+':未知知识库 '+key)
  elif not (ROOT/'knowledge_base'/files[key]).exists():errors.append(cid+':文件不存在 '+key)
 if r['Evaluation_Phase']=='Benchmark' and not all(r.get(k) for k in ['Actual_Response','Factual_Correctness','Citation_Correctness','Answer_Completeness','Groundedness']):errors.append(cid+':正式测试缺少回答或评分')
bench=[r for r in rows if r['Evaluation_Phase'].lower()=='benchmark']
from collections import Counter
counts=Counter(r['Test_Type'] for r in bench)
expected={'Fact Retrieval':6,'Conditional Reasoning':6,'Multi-condition Reasoning':6,'Unanswerable':6,'Conflicting Information':6}
if dict(counts)!=expected: errors.append('类别配额不符合6x5设计: '+str(dict(counts)))
print('基准数据检查：'+('FAIL' if errors else 'PASS'))
print('总案例：',len(rows),'Pilot：',len(rows)-len(bench),'Benchmark：',len(bench))
print('Benchmark分布：',dict(sorted(counts.items())))
print('已完成正式案例：',sum(bool(r.get('Actual_Response')) for r in bench),'/',len(bench))
if errors:
 for x in errors: print('ERROR:',x)
 sys.exit(1)
