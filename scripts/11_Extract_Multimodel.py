#!/usr/bin/env python3
"""
Generalized, model-agnostic flower-colour extractor for the multi-model benchmark.

Runs ANY HuggingFace instruct model (Qwen, Llama, etc.) over one or more input
CSVs and writes a per-row free-text colour prediction. Loads the model ONCE and
processes every --task, so a single GPU job can extract both the 100-row gold set
(for evaluation) and the full treatments file (for the dataset).

Design goals:
  * IDENTICAL prompt to the original step 02 baseline, so results are comparable
    across models and against the existing Qwen-7B run.
  * fp16 + device_map="auto" -> shards a 70B/72B model across all allocated GPUs
    with no extra dependencies (no bitsandbytes needed).
  * Deterministic (greedy) decoding.
  * Resumable: re-running skips ids already present in the output file.

SAFE BY DESIGN: only reads inputs and writes to the paths you pass on --task.
Nothing in the original pipeline is touched.

Usage
-----
  python 11_Extract_Multimodel.py \
      --model Qwen/Qwen2.5-72B-Instruct \
      --task "Processed Data/experiments/gold_set_template.csv::raw_text_snippet::species_id::Processed Data/experiments/benchmark/gold_pred_qwen72b.csv" \
      --task "Processed Data/experiments/species_descriptions_treatments.csv::raw_text::species_id::Processed Data/experiments/benchmark/treatments_pred_qwen72b.csv"

Each --task is  INPUT_CSV::TEXT_COLUMN::ID_COLUMN::OUTPUT_CSV
"""

import argparse
import csv
import os
import sys
from pathlib import Path

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

BASE_DIR = (
    Path(os.environ["THESIS_ROOT"]).expanduser().resolve()
    if os.environ.get("THESIS_ROOT")
    else Path(__file__).resolve().parents[1]
)
# IDENTICAL prompt to the original step-02 extractor,
# so cross-model differences reflect the MODEL, not the prompt.
SYSTEM_MESSAGE = (
    "You are an expert botanist. Your ONLY job is to extract the flower colour "
    "from Flora of India species descriptions. "
    "Return a very short phrase like 'flowers white', 'flowers yellow with red centre', "
    "'flowers blue or purple', etc. If flower colour is not mentioned, return exactly "
    "'no flower colour mentioned'. Do NOT add explanations."
)

csv.field_size_limit(sys.maxsize)


def load_model_and_tokenizer(model_name: str):
    token_kwargs = {}
    hf_token = os.environ.get("HF_TOKEN")
    if hf_token:
        token_kwargs["token"] = hf_token

    print(f"Loading tokenizer and model: {model_name}", flush=True)
    # Prefer local cache when present, but allow a light HF metadata call if needed
    # (strict offline mode breaks transformers' mistral-regex check).
    load_kwargs = dict(trust_remote_code=True, **token_kwargs)
    try:
        tokenizer = AutoTokenizer.from_pretrained(
            model_name, local_files_only=True, **load_kwargs
        )
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            local_files_only=True,
            torch_dtype=torch.float16,
            device_map="auto",
            **load_kwargs,
        )
    except Exception as e:
        print(f"local_files_only load failed ({e}); retrying with network...", flush=True)
        tokenizer = AutoTokenizer.from_pretrained(model_name, **load_kwargs)
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=torch.float16,
            device_map="auto",
            **load_kwargs,
        )
    model.eval()
    # first parameter's device is where we place the input ids
    return tokenizer, model


def infer_flower_color(tokenizer, model, description: str, max_new_tokens: int) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_MESSAGE},
        {"role": "user",
         "content": f"Species description:\n\n{description}\n\nWhat is the flower colour?"},
    ]
    inputs = tokenizer.apply_chat_template(
        messages, return_tensors="pt", add_generation_prompt=True,
    )
    # place on the device of the model's input embeddings (works with sharded models)
    inputs = inputs.to(model.device)
    with torch.no_grad():
        outputs = model.generate(
            inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )
    generated_ids = outputs[0][inputs.shape[-1]:]
    return tokenizer.decode(generated_ids, skip_special_tokens=True).strip()


def already_done_ids(path: Path, id_col: str):
    done = set()
    if path.exists():
        with open(path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                done.add(row.get(id_col, ""))
    return done


def resolve(p: str) -> Path:
    q = Path(p)
    return q if q.is_absolute() else BASE_DIR / q


def run_task(tokenizer, model, spec: str, max_new_tokens: int):
    parts = spec.split("::")
    if len(parts) != 4:
        raise ValueError(
            f"--task must be INPUT::TEXT_COL::ID_COL::OUTPUT, got: {spec!r}")
    in_csv, text_col, id_col, out_csv = parts
    in_path, out_path = resolve(in_csv), resolve(out_csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not in_path.exists():
        raise FileNotFoundError(f"Input CSV not found: {in_path}")

    # utf-8-sig tolerates a BOM (the gold set header has one)
    with open(in_path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        print(f"  (no rows in {in_path.name}, skipping)", flush=True)
        return
    if text_col not in rows[0] or id_col not in rows[0]:
        raise KeyError(
            f"Columns {text_col!r}/{id_col!r} not in {in_path.name}. "
            f"Available: {list(rows[0].keys())}")

    out_fields = [id_col, "flower_color_free_text"]
    done = already_done_ids(out_path, id_col)
    mode = "a" if done else "w"
    print(f"\n=== TASK: {in_path.name} -> {out_path.name} ===", flush=True)
    print(f"  rows={len(rows)}  already_done={len(done)}  mode={mode}", flush=True)

    with open(out_path, mode, newline="", encoding="utf-8") as f_out:
        writer = csv.DictWriter(f_out, fieldnames=out_fields)
        if mode == "w":
            writer.writeheader()
        count = 0
        for row in rows:
            rid = row.get(id_col, "")
            if rid in done:
                continue
            description = (row.get(text_col) or "").strip()
            if not description:
                pred = "no flower colour mentioned"
            else:
                try:
                    pred = infer_flower_color(
                        tokenizer, model, description, max_new_tokens)
                except Exception as e:  # noqa: BLE001
                    pred = f"ERROR: {e}"
            writer.writerow({id_col: rid, "flower_color_free_text": pred})
            f_out.flush()
            count += 1
            if count % 25 == 0:
                print(f"  processed {count} new rows...", flush=True)
        print(f"  DONE task: {count} new rows -> {out_path}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="HF model id")
    ap.add_argument("--task", action="append", required=True,
                    help="INPUT_CSV::TEXT_COL::ID_COL::OUTPUT_CSV (repeatable)")
    ap.add_argument("--max-new-tokens", type=int, default=32)
    args = ap.parse_args()

    tokenizer, model = load_model_and_tokenizer(args.model)
    for spec in args.task:
        run_task(tokenizer, model, spec, args.max_new_tokens)
    print("\nALL TASKS COMPLETE.", flush=True)


if __name__ == "__main__":
    main()
