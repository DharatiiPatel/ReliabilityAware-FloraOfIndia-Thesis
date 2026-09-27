#!/usr/bin/env python3
"""
Retrieval-augmented (few-shot) flower-colour extraction on the gold set.

Retrieval (no GPU needed for indexing):
  - Build a TF-IDF index over labelled gold-set rows (leave-one-out at query time
    so we never retrieve the query's own gold label — no leakage).
  - For each query description, retrieve the top-k most similar OTHER gold
    descriptions as exemplars.

Generation:
  - Same base instruction as the zero-shot extractor, plus retrieved exemplars
    (description snippet + gold free-text answer).
  - Optional abstention: model may return 'uncertain' when colour is ambiguous;
    those are scored as UNKNOWN for coarse metrics, and also reported separately
    as coverage.

Usage
-----
  # CPU: build retrieval demos only (debug)
  python 15_RAG_Extract_Gold.py --dump-demos 3

  # GPU: run RAG extraction over the gold set
  python 15_RAG_Extract_Gold.py --model Qwen/Qwen2.5-7B-Instruct --top-k 3
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import re
import sys
from pathlib import Path

BASE = (
    Path(os.environ["THESIS_ROOT"]).expanduser().resolve()
    if os.environ.get("THESIS_ROOT")
    else Path(__file__).resolve().parents[1]
)
EXP = BASE / "Processed Data" / "experiments"
GOLD = EXP / "gold_set_labeled.csv"
OUTDIR = EXP / "categorizer_evaluation"

csv.field_size_limit(sys.maxsize)

SYSTEM_RAG = (
    "You are an expert botanist. Your ONLY job is to extract the flower colour "
    "from Flora of India species descriptions. "
    "Return a very short phrase like 'flowers white', 'flowers yellow with red centre', "
    "'flowers blue or purple', etc. "
    "If flower colour is not mentioned, return exactly 'no flower colour mentioned'. "
    "If the colour is genuinely ambiguous or the text looks like a genus key/header "
    "rather than a species treatment, return exactly 'uncertain'. "
    "Use ONLY flower/petal/corolla colour — ignore fruit, berry, seed, and leaf colours. "
    "When multiple flower colours are listed, report the first (primary) colour mentioned. "
    "Do NOT add explanations."
)


def tokenize(text: str):
    return re.findall(r"[a-z]{3,}", (text or "").lower())


def build_tfidf(docs):
    """Pure-Python TF-IDF. Returns (vindex, idf_list, row_vectors)."""
    tokenized = [tokenize(d) for d in docs]
    df = {}
    for toks in tokenized:
        for t in set(toks):
            df[t] = df.get(t, 0) + 1
    vocab = sorted([t for t, c in df.items() if c >= 2])
    if len(vocab) > 8000:
        vocab = sorted(vocab, key=lambda t: -df[t])[:8000]
        vocab = sorted(vocab)
    vindex = {t: i for i, t in enumerate(vocab)}
    n = len(docs)
    idf = [0.0] * len(vocab)
    for t, i in vindex.items():
        idf[i] = math.log((1 + n) / (1 + df[t])) + 1.0
    rows = []
    for toks in tokenized:
        tf = {}
        for t in toks:
            if t in vindex:
                tf[t] = tf.get(t, 0) + 1
        vec = {}
        for t, c in tf.items():
            vec[vindex[t]] = c * idf[vindex[t]]
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        rows.append({i: v / norm for i, v in vec.items()})
    return vindex, idf, rows


def vectorize(text, vindex, idf):
    toks = tokenize(text)
    tf = {}
    for t in toks:
        if t in vindex:
            tf[t] = tf.get(t, 0) + 1
    vec = {vindex[t]: c * idf[vindex[t]] for t, c in tf.items()}
    norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
    return {i: v / norm for i, v in vec.items()}


def cosine(a: dict, b: dict) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(v * b.get(i, 0.0) for i, v in a.items())


def load_gold():
    with open(GOLD, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    labelled = [r for r in rows if (r.get("gold_category") or "").strip()
                and (r.get("gold_free_text") or "").strip()
                and (r.get("raw_text_snippet") or "").strip()]
    return rows, labelled


def retrieve(query_text, query_sid, labelled, row_vecs, vindex, idf, top_k):
    """Leave-one-out: exclude exemplars with the same species_id."""
    qv = vectorize(query_text, vindex, idf)
    scored = []
    for i, r in enumerate(labelled):
        if r["species_id"] == query_sid:
            continue
        scored.append((cosine(qv, row_vecs[i]), i))
    scored.sort(reverse=True)
    demos = []
    for sim, i in scored[:top_k]:
        r = labelled[i]
        demos.append({
            "species_id": r["species_id"][:80],
            "snippet": (r["raw_text_snippet"] or "")[:500],
            "answer": r["gold_free_text"].strip(),
            "sim": float(sim),
        })
    return demos


def build_user_message(description: str, demos) -> str:
    parts = ["Here are similar labelled examples from Flora of India:\n"]
    for j, d in enumerate(demos, 1):
        parts.append(
            f"Example {j}:\n"
            f"Description: {d['snippet']}\n"
            f"Flower colour: {d['answer']}\n"
        )
    parts.append(
        f"\nNow extract the flower colour for this description:\n\n{description}\n\n"
        f"What is the flower colour?"
    )
    return "".join(parts) if demos else (
        f"Species description:\n\n{description}\n\nWhat is the flower colour?"
    )


def load_model(model_name: str):
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM

    token_kwargs = {}
    hf_token = os.environ.get("HF_TOKEN")
    if not hf_token and Path.home().joinpath(".hf_token").exists():
        hf_token = Path.home().joinpath(".hf_token").read_text().strip()
    if hf_token:
        token_kwargs["token"] = hf_token

    print(f"Loading {model_name}", flush=True)
    tokenizer = AutoTokenizer.from_pretrained(
        model_name, trust_remote_code=True, **token_kwargs
    )
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        trust_remote_code=True,
        torch_dtype=torch.float16,
        device_map="auto",
        **token_kwargs,
    )
    model.eval()
    return tokenizer, model


def infer(tokenizer, model, user_msg: str, max_new_tokens: int = 32) -> str:
    import torch
    messages = [
        {"role": "system", "content": SYSTEM_RAG},
        {"role": "user", "content": user_msg},
    ]
    inputs = tokenizer.apply_chat_template(
        messages, return_tensors="pt", add_generation_prompt=True,
    ).to(model.device)
    with torch.no_grad():
        outputs = model.generate(
            inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )
    gen = outputs[0][inputs.shape[-1]:]
    return tokenizer.decode(gen, skip_special_tokens=True).strip()


def already_done(path: Path):
    done = set()
    if path.exists():
        with open(path, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                done.add(r["species_id"])
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="")
    ap.add_argument("--top-k", type=int, default=3)
    ap.add_argument("--dump-demos", type=int, default=0,
                    help="Print demos for first N gold rows and exit")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    OUTDIR.mkdir(parents=True, exist_ok=True)
    all_rows, labelled = load_gold()
    docs = [r["raw_text_snippet"] for r in labelled]
    vindex, idf, row_vecs = build_tfidf(docs)
    print(f"Indexed {len(labelled)} labelled exemplars; vocab={len(vindex)}", flush=True)

    if args.dump_demos:
        for r in all_rows[: args.dump_demos]:
            demos = retrieve(r["raw_text_snippet"], r["species_id"],
                             labelled, row_vecs, vindex, idf, args.top_k)
            print("=" * 60)
            print("QUERY:", r["species_id"][:70])
            print("gold:", r.get("gold_free_text"), "/", r.get("gold_category"))
            for d in demos:
                print(f"  sim={d['sim']:.3f} -> {d['answer']!r} | {d['species_id'][:50]}")
        return

    if not args.model:
        raise SystemExit("Provide --model for extraction, or --dump-demos for debug")

    out_path = Path(args.out) if args.out else OUTDIR / "gold_pred_qwen7b_rag.csv"
    done = already_done(out_path)
    mode = "a" if done else "w"
    print(f"Writing {out_path} (already done={len(done)})", flush=True)

    tokenizer, model = load_model(args.model)

    with open(out_path, mode, newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "species_id", "flower_color_free_text", "n_demos", "demo_answers"
        ])
        if mode == "w":
            w.writeheader()
        count = 0
        for r in all_rows:
            sid = r["species_id"]
            if sid in done:
                continue
            desc = r.get("raw_text_snippet") or ""
            demos = retrieve(desc, sid, labelled, row_vecs, vindex, idf, args.top_k)
            user_msg = build_user_message(desc, demos)
            try:
                pred = infer(tokenizer, model, user_msg)
            except Exception as e:  # noqa: BLE001
                pred = f"ERROR: {e}"
            w.writerow({
                "species_id": sid,
                "flower_color_free_text": pred,
                "n_demos": len(demos),
                "demo_answers": " || ".join(d["answer"] for d in demos),
            })
            f.flush()
            count += 1
            if count % 10 == 0:
                print(f"  processed {count}...", flush=True)
    print(f"DONE. new={count} -> {out_path}", flush=True)


if __name__ == "__main__":
    main()
