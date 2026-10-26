#!/usr/bin/env python3
"""Validate project KB snapshots against existing evaluation case references. Stdlib only."""
from pathlib import Path
import csv, hashlib, json, sys
ROOT=Path(__file__).resolve().parents[1]
KB=ROOT/'knowledge_base'
DATA=ROOT/'data'/'benchmark.csv'
OUT=ROOT/'outputs'/'knowledge_base_audit.json'
FILES={
  'KB-001 V1.0':'KB_001_Employee_Policies_V1.txt',
  'KB-002 V1.0':'KB_002_Policy_Version_Registry_V1.txt',
}
EXPECTED={
 'KB-001 V1.0':['文件编号：KB-001','版本：V1.0','生效日期：2026年10月1日','每人每天最高报销80元','每人每晚最高报销500元','原则上不予报销'],
 'KB-002 V1.0':['文件编号：KB-002','版本：V1.0','2026年10月24日','V0.9','60元','400元','V1.1','100元','600元','尚未获得正式批准']
}
def sha(t):return hashlib.sha256(t).hexdigest()
def main():
    problems=[]; snaps={}
    for key,name in FILES.items():
        p=KB/name
        if not p.is_file():problems.append('文件缺失：'+str(p));continue
        b=p.read_bytes()
        try:t=b.decode('utf-8-sig')
        except UnicodeDecodeError:problems.append('文件不是UTF-8：'+name);continue
        absent=[phrase for phrase in EXPECTED[key] if phrase not in t]
        if absent:problems.append(name+' 缺少关键标记：'+repr(absent))
        snaps[key]={'name':name,'bytes':len(b),'sha256':sha(b),'lines':len(t.splitlines()),'missing_markers':absent}
    cases=[]
    if DATA.is_file():
        with DATA.open('r',encoding='utf-8-sig',newline='') as f: cases=list(csv.DictReader(f))
    else:problems.append('数据文件缺失：'+str(DATA))
    for row in cases:
        ids=[x.strip() for x in row['Knowledge_Base_Set'].split('+')]
        for item in ids:
            if item not in FILES:problems.append(row['Case_ID']+' 引用未知知识库：'+item)
            elif item not in snaps:problems.append(row['Case_ID']+' 知识库尚未就绪：'+item)
    report={'status':'PASS' if not problems else 'FAIL','case_count':len(cases),'knowledge_base':snaps,'issues':problems,'note':'KB-001 标题、版本与生效日期由原始设计文案恢复；本公开仓库不包含最初导出的原始文件。'}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('知识库检查：'+report['status'])
    print('有效案例：'+str(len(cases)))
    for key,val in snaps.items():print(f"{key}：{val['lines']} 行，SHA256={val['sha256'][:12]}…")
    print('检查报告：'+str(OUT.relative_to(ROOT)))
    if problems:
        print('\n'.join('问题：'+i for i in problems));sys.exit(1)
if __name__=='__main__':main()
