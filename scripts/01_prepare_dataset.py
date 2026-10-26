"""校验与规范化飞书导出的 AI 知识问答评测数据。"""
from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / 'data' / 'raw' / 'eval_cases_draft_v01.csv'
OUTPUT = ROOT / 'data' / 'processed' / 'eval_cases_clean_v01.csv'
REPORT = ROOT / 'outputs' / 'dataset_audit.json'

REQUIRED_COLUMNS = [
    'Case_ID', 'Question', 'Test_Type', 'Reference_Evidence',
    'Expected_Answer', 'Evaluation_Phase', 'Knowledge_Base_Set'
]
COLUMN_ALIASES = {'Factual_Response': 'Factual_Correctness'}
TYPE_ALIASES = {
    'Multi-step Rasoning': 'Multi-step Reasoning',
    'Multi-condition Rasoning': 'Multi-condition Reasoning',
}
SCORED_COLUMNS = [
    'Factual_Correctness', 'Citation_Correctness',
    'Answer_Completeness', 'Groundedness'
]


def main() -> None:
    if not INPUT.exists():
        raise SystemExit(f'找不到输入文件：{INPUT}\n请将飞书 CSV 放入 data/raw/ 目录。')

    with INPUT.open('r', encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        original_headers = reader.fieldnames or []
        data = list(reader)

    headers = [COLUMN_ALIASES.get(key, key) for key in original_headers]
    if len(headers) != len(set(headers)):
        raise SystemExit('出现重复列名：原表格中可能已同时存在 Factual_Response 和 Factual_Correctness。请人工核查。')

    missing_columns = sorted(set(REQUIRED_COLUMNS) - set(headers))
    if missing_columns:
        raise SystemExit(f'缺少必需字段：{missing_columns}')

    processed = []
    blank_rows = 0
    problems = []
    changes = Counter()

    for row_num, old_row in enumerate(data, start=2):
        row = {COLUMN_ALIASES.get(key, key): (value or '').strip()
               for key, value in old_row.items() if key is not None}
        if not any(row.values()):
            blank_rows += 1
            continue
        if not row.get('Case_ID'):
            problems.append(f'CSV第{row_num}行：存在内容但缺少 Case_ID')
            continue

        test_type = row.get('Test_Type', '')
        if test_type in TYPE_ALIASES:
            row['Test_Type'] = TYPE_ALIASES[test_type]
            changes['测试类型拼写更正'] += 1

        for column in SCORED_COLUMNS:
            if column in row and row[column].upper() == 'NA':
                row[column] = 'N/A'
                changes['评分 N/A 规范化'] += 1

        for key in REQUIRED_COLUMNS:
            if not row.get(key):
                problems.append(f"{row['Case_ID']}：字段 {key} 为空")
        if not re.fullmatch(r'TC\d{3}', row['Case_ID']):
            problems.append(f"测试编号不符合 TC001 格式：{row['Case_ID']}")
        if row.get('Evaluation_Phase') not in {'Pilot', 'Benchmark'}:
            problems.append(f"{row['Case_ID']}：Evaluation_Phase 不是 Pilot/Benchmark")

        for column in SCORED_COLUMNS:
            value = row.get(column, '').upper()
            if value and value not in {'PASS', 'FAIL', 'N/A'}:
                problems.append(f"{row['Case_ID']}：{column} 的评分值无效：{value}")

        processed.append(row)

    ids = [row['Case_ID'] for row in processed]
    dup_ids = [key for key, count in Counter(ids).items() if count > 1]
    if dup_ids:
        problems.append(f'重复的 Case_ID：{dup_ids}')

    report = {
        'raw_rows': len(data),
        'removed_blank_rows': blank_rows,
        'valid_case_rows': len(processed),
        'unique_case_ids': len(set(ids)),
        'phase_counts': dict(Counter(row.get('Evaluation_Phase') for row in processed)),
        'test_type_counts': dict(Counter(row.get('Test_Type') for row in processed)),
        'normalizations': dict(changes),
        'pilot_scored_rows': sum(row.get('Evaluation_Phase') == 'Pilot' and bool(row.get('Actual_Response')) for row in processed),
        'benchmark_unrun_rows': sum(row.get('Evaluation_Phase') == 'Benchmark' and not row.get('Actual_Response') for row in processed),
        'problems': problems,
        'model_name_note': 'Model_Name 源于用户原始记录；脚本未核验实际模型身份。',
    }

    if problems:
        print('数据存在待修复问题，未输出清洗数据：')
        for problem in problems:
            print(' -', problem)
        raise SystemExit(1)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, lineterminator='\n')
        writer.writeheader()
        writer.writerows(processed)

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')

    print('CSV 校验完成')
    print(f'有效案例：{len(processed)} 条（Pilot {report["phase_counts"].get("Pilot", 0)}，Benchmark {report["phase_counts"].get("Benchmark", 0)}）')
    print(f'已过滤完全空白行：{blank_rows} 行')
    print(f'已规范化测试类型：{changes["测试类型拼写更正"]} 处')
    print(f'已规范化 N/A 评分：{changes["评分 N/A 规范化"]} 处')
    print(f'清洗文件：{OUTPUT.relative_to(ROOT)}')
    print(f'校验报告：{REPORT.relative_to(ROOT)}')
    print('注意：模型名称仍需单独核验；知识库状态请运行 scripts/02_validate_knowledge_base.py。')


if __name__ == '__main__':
    main()
