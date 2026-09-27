#!/usr/bin/env python3
"""
Colour extraction for recovered lost-species treatments.

Same prompt and model as 02_Extract_Flower_Colour.py, different I/O:
  READS  : Processed Data/experiments/recovered_descriptions_for_extract.csv
  WRITES : Processed Data/experiments/flower_color_recovered.csv

Resumable. Requires 04c_Recover_Lost_Treatments.py to have finished first.
"""

from __future__ import annotations

import csv
import os
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

BASE = (
    Path(os.environ["THESIS_ROOT"]).expanduser().resolve()
    if os.environ.get("THESIS_ROOT")
    else Path(__file__).resolve().parents[1]
)
INPUT_CSV = BASE / "Processed Data" / "experiments" / "recovered_descriptions_for_extract.csv"
OUTPUT_CSV = BASE / "Processed Data" / "experiments" / "flower_color_recovered.csv"
MODEL_NAME = "Qwen/Qwen2.5-7B-Instruct"
MAX_NEW_TOKENS = 32
MAX_DESC_CHARS = 3000

SYSTEM_MESSAGE = (
    "You are an expert botanist. Your ONLY job is to extract the flower colour "
    "from Flora of India species descriptions. "
    "Return a very short phrase like 'flowers white', 'flowers yellow with red centre', "
    "'flowers blue or purple', etc. If flower colour is not mentioned, return exactly "
    "'no flower colour mentioned'. Do NOT add explanations."
)

def resolve_model_path(model_id: str) -> str:
    """Prefer local HF snapshot so offline compute nodes can load the model."""
    if Path(model_id).is_dir():
        return model_id
    hf_home = os.environ.get("HF_HOME", str(Path.home() / ".cache" / "huggingface"))
    snapshots = Path(hf_home) / "hub" / f"models--{model_id.replace('/', '--')}" / "snapshots"
    if snapshots.is_dir():
        for d in sorted(snapshots.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            if (d / "config.json").exists() and (d / "tokenizer_config.json").exists():
                print(f"Using cached snapshot: {d}", flush=True)
                return str(d)
    return model_id

def load_model_and_tokenizer():
    path = resolve_model_path(MODEL_NAME)
    tokenizer = AutoTokenizer.from_pretrained(path, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        path,
        trust_remote_code=True,
        torch_dtype=torch.bfloat16,
        device_map="auto",
    )
    model.eval()
    return tokenizer, model

def infer_flower_color(tokenizer, model, description: str) -> str:
    desc = (description or "")[:MAX_DESC_CHARS]
    messages = [
        {"role": "system", "content": SYSTEM_MESSAGE},
        {"role": "user",
         "content": f"Species description:\n\n{desc}\n\nWhat is the flower colour?"},
    ]
    inputs = tokenizer.apply_chat_template(
        messages, return_tensors="pt", add_generation_prompt=True,
    ).to(model.device)
    with torch.no_grad():
        outputs = model.generate(
            inputs,
            max_new_tokens=MAX_NEW_TOKENS,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )
    generated_ids = outputs[0][inputs.shape[-1]:]
    return tokenizer.decode(generated_ids, skip_special_tokens=True).strip()

def already_done_ids(path: Path) -> set[str]:
    done = set()
    if path.exists():
        with path.open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                done.add(row.get("species_id", ""))
    return done

def main():
    if not INPUT_CSV.exists():
        raise SystemExit(
            f"Missing {INPUT_CSV} - run 04c_Recover_Lost_Treatments.py / "
            f"run_04c_recover_lost.slurm first")

    rows = list(csv.DictReader(INPUT_CSV.open(encoding="utf-8")))
    if not rows:
        raise SystemExit(f"No rows in {INPUT_CSV}")
    out_fields = list(rows[0].keys()) + ["flower_color_free_text"]

    done = already_done_ids(OUTPUT_CSV)
    mode = "a" if done else "w"
    print(f"Total: {len(rows)}; already done: {len(done)}; mode={mode}", flush=True)

    tokenizer, model = load_model_and_tokenizer()
    with OUTPUT_CSV.open(mode, newline="", encoding="utf-8") as f_out:
        writer = csv.DictWriter(f_out, fieldnames=out_fields)
        if mode == "w":
            writer.writeheader()
        count = 0
        for row in rows:
            if row["species_id"] in done:
                continue
            try:
                colour = infer_flower_color(tokenizer, model, row.get("raw_text", ""))
            except Exception as e:
                colour = f"ERROR: {e}"
            row["flower_color_free_text"] = colour
            writer.writerow(row)
            f_out.flush()
            count += 1
            if count % 25 == 0:
                print(f"Processed {count} ...", flush=True)
    print(f"DONE. Processed {count} new. Output: {OUTPUT_CSV}", flush=True)

if __name__ == "__main__":
    main()
