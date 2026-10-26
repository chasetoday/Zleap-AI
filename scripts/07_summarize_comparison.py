#!/usr/bin/env python3
"""Verify and summarize the saved full-context and BM25 RAG comparison; offline."""
from pathlib import Path
import csv,json
ROOT=Path(__file__).resolve().parents[1]
O=ROOT/'outputs'
S=['Factual_Correctness','Citation_Correctness','Answer_Completeness','Groundedness']
def rows(p):
    with p.open('r',encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def logs(path):
    with path.open('r',encoding='utf8') as f:return [json.loads(s) for s in f if s.strip()]
B=rows(O/'scoring_benchmark_30.csv');R=rows(O/'scoring_rag_30.csv')
assert len(B)==len(R)==30
for d in [B,R]:
    assert sorted(x['Case_ID'] for x in d)==[f'TC{i:03d}' for i in range(5,35)]
    for x in d:assert all(x[k] in ('Pass','Fail','N/A') for k in S)
base={}
for fn in ['qwen_20261026T041501Z.jsonl','qwen_20261026T041845Z.jsonl','qwen_20261026T043711Z.jsonl']:
    for x in logs(O/'public_runs'/fn):base[x['case_id']]=x
rag={x['case_id']:x for x in logs(O/'public_runs'/'rag_20261026T052311Z.jsonl')}
assert len(base)==30 and len(rag)==30 and set(base)==set(rag)
for case_id,b in base.items():
    r=rag[case_id]
    assert b['status']=='ok' and r['status']=='ok'
    assert b['question']==r['question']
    assert b['prompt_sha256']==r['prompt_sha256']
    assert b['source_kb_sha256']==r['kb_hashes']
    assert not b['parameters']['enable_thinking'] and not r['parameters']['enable_thinking']
def allpass(d):return sum(all(x[k]=='Pass' for k in S) for x in d)
def tot(d,key):return sum(x['usage'][key] for x in d.values())
print(f"四项全通过：全文 {allpass(B)}/30；RAG {allpass(R)}/30")
for k in S:print(f"{k}：全文 {sum(x[k]=='Pass' for x in B)}/30；RAG {sum(x[k]=='Pass' for x in R)}/30")
paired_rag={k:rag[k] for k in base}
for k in ['prompt_tokens','completion_tokens','total_tokens']:
    a=tot(base,k);b=tot(paired_rag,k)
    print(f"配对30条 {k}: full={a:,}, RAG={b:,}, reduction={(a-b)*100/a:.2f}%")
# Verify stored paired CSV equals actual API usage and score entries
P=rows(O/'paired_comparison_30.csv')
assert len(P)==30 and set(x['Case_ID'] for x in P)==set(base)
by_id={x['Case_ID']:x for x in P}
for case_id,b in base.items():
    r=rag[case_id]; row=by_id[case_id]
    for prefix,source in [('Full_Context',b),('RAG',r)]:
        for suffix,usage in [('Input_Tokens','prompt_tokens'),('Output_Tokens','completion_tokens'),('Total_Tokens','total_tokens')]:
            assert int(row[f'{prefix}_{suffix}'])==source['usage'][usage],(case_id,prefix,suffix)
print('PASS: 30 scores checked, 30 API pairs and CSV validated; offline, no model call')
