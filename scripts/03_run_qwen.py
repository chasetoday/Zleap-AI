#!/usr/bin/env python3
"""Dry-run or bounded API evaluation. Only --run invokes a billed external model."""
from pathlib import Path
import argparse,csv,datetime,hashlib,json,os,sys,urllib.request,urllib.error,time,getpass
ROOT=Path(__file__).resolve().parents[1]
FILES={'KB-001 V1.0':'KB_001_Employee_Policies_V1.txt','KB-002 V1.0':'KB_002_Policy_Version_Registry_V1.txt'}
def sha(b):return hashlib.sha256(b).hexdigest()
def docs_for(row):
    blocks=[]; manifest={}
    for name in [v.strip() for v in row['Knowledge_Base_Set'].split('+')]:
        if name not in FILES:raise ValueError('未识别的知识库：'+name)
        p=ROOT/'knowledge_base'/FILES[name]
        b=p.read_bytes();txt=b.decode('utf-8-sig')
        manifest[name]=sha(b)
        blocks.append(f'【知识库：{name}】\n{txt}')
    return '\n\n'.join(blocks),manifest
def call(endpoint,key,model,messages):
    payload={'model':model,'messages':messages,'max_tokens':512,'stream':False,'enable_thinking':False}
    req=urllib.request.Request(endpoint,data=json.dumps(payload,ensure_ascii=False).encode('utf-8'),headers={'Content-Type':'application/json','Authorization':'Bearer '+key},method='POST')
    with urllib.request.urlopen(req,timeout=90) as f:
        response=json.loads(f.read().decode('utf-8'))
    choices=response.get('choices') or []
    msg=(choices[0].get('message') or {}) if choices else {}
    content=msg.get('content') or ''
    if isinstance(content,list):content=''.join(x.get('text','') for x in content if isinstance(x,dict))
    return response,str(content)
def main():
    p=argparse.ArgumentParser(description='Qwen knowledge assistant evaluation, each case independent')
    group=p.add_mutually_exclusive_group(required=True)
    group.add_argument('--dry-run',action='store_true',help='不联网，不计费，仅检查输入')
    group.add_argument('--run',action='store_true',help='真实API请求，可能收费')
    p.add_argument('--limit',type=int,default=1,help='本次最多请求多少条，默认1条')
    p.add_argument('--model',default='qwen3.7-plus',help='API模型ID，请从阿里云百炼控制台核对')
    p.add_argument('--start-case',default='TC005',help='从哪条Benchmark开始（默认TC005）')
    p.add_argument('--endpoint',default=os.getenv('QWEN_API_ENDPOINT','https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions'),help='API HTTP endpoint，必须与API Key地域匹配')
    args=p.parse_args()
    if not 1<=args.limit<=30:sys.exit('单次只允许1至30条')
    path=ROOT/'data'/'benchmark.csv'
    with path.open(encoding='utf-8-sig',newline='') as f: allcases=list(csv.DictReader(f))
    cases=[r for r in allcases if r.get('Evaluation_Phase','').lower()=='benchmark']
    ids=[x['Case_ID'] for x in cases]
    if args.start_case not in ids:sys.exit('未找到可运行的Benchmark起始编号：'+args.start_case)
    cases=cases[ids.index(args.start_case):][:args.limit]
    if not cases:sys.exit('没有待运行的测试题')
    sys_prompt=(ROOT/'config'/'evaluation_prompt.txt').read_text(encoding='utf-8')
    prepared=[]
    for row in cases:
        doc,manifest=docs_for(row)
        messages=[{'role':'system','content':sys_prompt},{'role':'user','content':doc+'\n\n【本次测试问题】\n'+row['Question']}]
        prepared.append((row,messages,manifest))
    print('模式：'+('DRY RUN（不调用API）' if args.dry_run else 'LIVE（真实API，可能收费）'))
    print('测试案例：'+','.join(x[0]['Case_ID'] for x in prepared))
    print('模型ID：'+args.model)
    print('思考模式：关闭（enable_thinking=false）')
    print('提示词SHA256：'+sha(sys_prompt.encode('utf-8'))[:12]+'…')
    for row,msg,manifest in prepared:
        print(row['Case_ID'],'知识库：'+', '.join(manifest.keys()),'问题字符数：'+str(len(row['Question'])))
    if args.dry_run:return
    key=os.getenv('DASHSCOPE_API_KEY','').strip()
    if not key:
        key=getpass.getpass('请输入 API Key（输入不会显示，按回车继续）：').strip()
    if not key:sys.exit('API Key 为空；没有发送任何API请求。')
    # Explicit user action: --run. No automatic retries to avoid unintended charges.
    output_dir=ROOT/'outputs'/'qwen_runs';output_dir.mkdir(parents=True,exist_ok=True)
    out=output_dir/('qwen_'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.jsonl')
    for row,messages,manifest in prepared:
        result={'case_id':row['Case_ID'],'phase':'Benchmark','source_kb_sha256':manifest,'prompt_sha256':sha(sys_prompt.encode('utf-8')),'model_requested':args.model,'endpoint':args.endpoint,'timestamp_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'question':row['Question'],'parameters':{'max_tokens':512,'stream':False,'enable_thinking':False,'sampling':'API default'},'status':None}
        try:
            response,answer=call(args.endpoint,key,args.model,messages)
            result.update({'status':'ok','model_returned':response.get('model'),'answer':answer,'usage':response.get('usage'),'request_id':response.get('id'),'finish_reason':(response.get('choices') or [{}])[0].get('finish_reason')})
            if not answer.strip():
                result['status']='empty_answer'
                print(row['Case_ID']+' 收到空回答，需检查响应和模型配置')
            else:
                print(row['Case_ID']+' 已收到回答（'+str(len(answer))+'字符）')
        except urllib.error.HTTPError as ex:
            result.update({'status':'http_error','error_code':ex.code,'error_body':ex.read().decode('utf-8',errors='replace')[:1000]})
            print(row['Case_ID']+' API错误：HTTP '+str(ex.code))
        except Exception as ex:
            result.update({'status':'error','error':str(ex)[:300]})
            print(row['Case_ID']+' 运行错误：'+str(ex)[:160])
        with out.open('a',encoding='utf-8',newline='\n') as f:f.write(json.dumps(result,ensure_ascii=False)+'\n')
        if result['status']!='ok':break
    print('原始结果已保存：'+str(out.relative_to(ROOT)))
    print('本工具不自动判定Pass/Fail，评分需按固定Rubric人工复核。')
if __name__=='__main__':main()
