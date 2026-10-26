#!/usr/bin/env python3
"""Minimal auditable lexical RAG baseline: section chunking -> BM25 retrieval -> Qwen.

No extra packages needed. --dry-run is offline and free; --run invokes a billed API.
This is NOT a vector/embedding RAG implementation. It retrieves actual source chunks.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import getpass
import hashlib
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "KB-001 V1.0": "KB_001_Employee_Policies_V1.txt",
    "KB-002 V1.0": "KB_002_Policy_Version_Registry_V1.txt",
}
API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"


def digest(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def tokens(s: str) -> list[str]:
    """Simple dependency-free tokens for Chinese + English + numbers."""
    s = s.lower()
    out = []
    for t in re.findall(r"[\u4e00-\u9fff]+|[a-z]+|\d+(?:\.\d+)?", s):
        if re.fullmatch(r"[\u4e00-\u9fff]+", t):
            out.extend(t[i:i+2] for i in range(max(0, len(t)-1)))
            if len(t) == 1:
                out.append(t)
        else:
            out.append(t)
    return out


def split_sections(name: str, content: str) -> list[dict]:
    """One chunk per numbered policy subsection, with traceable source metadata."""
    lines = [s.strip() for s in content.splitlines() if s.strip()]
    result = []
    chapter = ""
    section = ""
    heading = ""
    body = []
    meta = lines[:5]

    def flush():
        if section and body:
            chunk_text = "\n".join(body)
            result.append({
                "id": f"{name} §{section}",
                "source": name,
                "section": section,
                "heading": heading,
                "chapter": chapter,
                "text": chunk_text,
                "retrieval_text": f"{name} {chapter} {section} {heading}\n{chunk_text}",
            })

    for ln in lines[5:]:
        if re.match(r"^第[一二三四五六七八九十\d]+章", ln):
            flush()
            chapter = ln
            section = ""
            heading = ""
            body = []
        elif re.match(r"^\d+\.\d+\s+", ln):
            flush()
            m = re.match(r"^(\d+\.\d+)\s+(.+)$", ln)
            section, heading = m.group(1), m.group(2)
            body = []
        elif section:
            body.append(ln)
        else:
            # Unnumbered chapter (KB-001 chapter 4) gets its own chunk.
            if not section:
                section = chapter or "document"
                heading = chapter
            body.append(ln)
    flush()
    if not result:
        raise ValueError(f"文件未识别出任何可检索章节: {name}")
    return result


def load_corpus(row: dict) -> tuple[list[dict], dict]:
    chunks, manifest = [], {}
    names = [t.strip() for t in row["Knowledge_Base_Set"].split("+")]
    for name in names:
        if name not in FILES:
            raise ValueError(f"未知知识库编号: {name}")
        path = ROOT / "knowledge_base" / FILES[name]
        raw = path.read_bytes()
        text = raw.decode("utf-8-sig")
        manifest[name] = digest(raw)
        chunks.extend(split_sections(name, text))
    return chunks, manifest


def bm25_retrieve(query: str, chunks: list[dict], top_k: int) -> list[dict]:
    docs = [Counter(tokens(c["retrieval_text"])) for c in chunks]
    lengths = [sum(c.values()) for c in docs]
    avg_len = sum(lengths) / max(len(lengths), 1)
    n = len(chunks)
    terms = set(tokens(query))
    df = Counter(t for counter in docs for t in counter)
    ranked = []
    for i, freqs in enumerate(docs):
        score = 0.0
        for term in terms:
            tf = freqs.get(term, 0)
            if not tf:
                continue
            idf = math.log(1 + (n - df[term] + 0.5) / (df[term] + 0.5))
            score += idf * (tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * lengths[i] / max(avg_len, 1))))
        ranked.append({**chunks[i], "retrieval_score": round(score, 6)})
    ranked.sort(key=lambda r: (-r["retrieval_score"], r["id"]))
    return [r for r in ranked if r["retrieval_score"] > 0][:top_k]


def prepare(row: dict, top_k: int):
    chunks, manifest = load_corpus(row)
    hits = bm25_retrieve(row["Question"], chunks, top_k)
    context = "\n\n".join(
        f"【片段 {i}｜{hit['id']}｜{hit['heading']}】\n{hit['text']}"
        for i, hit in enumerate(hits, start=1)
    ) if hits else "（没有找到相关章节。）"
    return chunks, hits, manifest, context


def main():
    p = argparse.ArgumentParser(description="Sparse/BM25 RAG for synthetic policy evaluation")
    flags = p.add_mutually_exclusive_group(required=True)
    flags.add_argument("--dry-run", action="store_true", help="只检索，不调用API，无费用")
    flags.add_argument("--run", action="store_true", help="真正调用Qwen API，会产生费用")
    p.add_argument("--start-case", default="TC009")
    p.add_argument("--limit", type=int, default=1)
    p.add_argument("--top-k", type=int, default=3)
    p.add_argument("--model", default="qwen3.7-plus")
    p.add_argument("--endpoint", default=os.getenv("QWEN_API_ENDPOINT", API_URL))
    args = p.parse_args()
    if not 1 <= args.limit <= 30 or not 1 <= args.top_k <= 6:
        sys.exit("limit必须在1-30之间，top-k必须在1-6之间")

    path = ROOT / "data" / "benchmark.csv"
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r.get("Evaluation_Phase", "").lower() == "benchmark"]
    ids = [r["Case_ID"] for r in rows]
    if args.start_case not in ids:
        sys.exit("找不到测试编号: " + args.start_case)
    selected = rows[ids.index(args.start_case):][:args.limit]

    base_prompt = (ROOT / "config" / "evaluation_prompt.txt").read_text(encoding="utf-8")
    # Reuse the same baseline instructions to make full-context vs retrieval more comparable.
    # One word changes: "知识库文件" now refers to retrieved sections provided below.
    print("模式：" + ("DRY RUN（只检索，不收费）" if args.dry_run else "LIVE RAG（调用Qwen API，可能收费）"))
    print("检索：章节切块 + 词法BM25；不使用embedding/vector DB")
    print("模型：" + args.model + "；非思考模式")
    prepared = []
    for r in selected:
        chunks, hits, manifest, context = prepare(r, args.top_k)
        print(f"{r['Case_ID']}: 知识库包含{len(chunks)}个章节，检索{len(hits)}个章节")
        for h in hits:
            print(f"  {h['id']} | BM25={h['retrieval_score']:.3f}")
        prepared.append((r, chunks, hits, manifest, context))
    if args.dry_run:
        print("结束：仅测试检索，没有调用API。")
        return

    key = os.getenv("DASHSCOPE_API_KEY", "").strip() or getpass.getpass("请输入API Key（不会显示）: ").strip()
    if not key:
        sys.exit("API Key为空；未调用API")
    outdir = ROOT / "outputs" / "rag_runs"
    outdir.mkdir(parents=True, exist_ok=True)
    dest = outdir / ("rag_" + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ".jsonl")
    for r, chunks, hits, manifest, context in prepared:
        # Only evidence retrieved by the search stage is visible to Qwen.
        messages = [
            {"role": "system", "content": base_prompt},
            {"role": "user", "content": "【本次检索到的知识库章节】\n" + context + "\n\n【本次测试问题】\n" + r["Question"]},
        ]
        payload = {"model": args.model, "messages": messages, "max_tokens": 512,
                   "stream": False, "enable_thinking": False}
        entry = {
            "case_id": r["Case_ID"], "status": None,
            "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "question": r["Question"], "kb_hashes": manifest, "model_requested": args.model,
            "retriever": "section_bm25_character_bigrams_v1", "top_k": args.top_k,
            "total_chunks": len(chunks), "retrieved_chunks": [
                {"id": h["id"], "score": h["retrieval_score"], "text": h["text"]} for h in hits],
            "retrieved_characters": len(context),
            "prompt_sha256": digest(base_prompt.encode("utf-8")),
            "parameters": {"enable_thinking": False, "max_tokens": 512, "stream": False},
        }
        req = urllib.request.Request(args.endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + key}, method="POST")
        started = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                parsed = json.loads(resp.read().decode("utf-8"))
            choice = (parsed.get("choices") or [{}])[0]
            content = (choice.get("message") or {}).get("content") or ""
            if isinstance(content, list):
                content = "".join(c.get("text", "") for c in content if isinstance(c, dict))
            entry.update({"status": "ok" if str(content).strip() else "empty_answer",
                          "answer": str(content), "model_returned": parsed.get("model"),
                          "finish_reason": choice.get("finish_reason"), "usage": parsed.get("usage"),
                          "elapsed_seconds": round(time.monotonic() - started, 3)})
            print(f"{r['Case_ID']}: {entry['status']}，回答{len(str(content))}字符")
        except urllib.error.HTTPError as ex:
            entry.update({"status": "http_error", "http_status": ex.code,
                          "error_body": ex.read().decode("utf-8", "replace")[:800]})
            print(f"{r['Case_ID']}: HTTP {ex.code}")
        except Exception as ex:
            entry.update({"status": "error", "error": str(ex)[:300]})
            print(f"{r['Case_ID']}: ERROR {str(ex)[:200]}")
        with dest.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        if entry["status"] != "ok":
            print("检测到错误，已停止后续调用")
            break
    print("已保存：" + str(dest.relative_to(ROOT)))
    print("这是RAG回答原始结果；评分仍须按既定Rubric复核。")


if __name__ == "__main__":
    main()
