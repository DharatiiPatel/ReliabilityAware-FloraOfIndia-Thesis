#!/usr/bin/env python3
"""
Colour extraction for ALL new expansion texts (recovered + fascicle).

Same prompt/model as 02. I/O under expansion/ only.

  READS  : Processed Data/experiments/expansion/new_descriptions_for_extract.csv
  WRITES : Processed Data/experiments/expansion/flower_color_new.csv
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
INPUT_CSV = BASE / "Processed Data" / "experiments" / "expansion" / "new_descriptions_for_extract.csv"
OUTPUT_CSV = BASE / "Processed Data" / "experiments" / "expansion" / "flower_color_new.csv"
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

def already_done_ids(path: Path) -> set[str]:
    done = set()
    if path.exists():
        with path.open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                done.add(row.get("species_id", ""))
    return done

def infer(tokenizer, model, description: str) -> str:
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
        out = model.generate(
            inputs, max_new_tokens=MAX_NEW_TOKENS, do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )
    return tokenizer.decode(out[0][inputs.shape[-1]:], skip_special_tokens=True).strip()

def main():
    if not INPUT_CSV.exists():
        raise SystemExit(f"Missing {INPUT_CSV}")
    rows = list(csv.DictReader(INPUT_CSV.open(encoding="utf-8")))
    if not rows:
        raise SystemExit("No rows to extract")
    fields = list(rows[0].keys()) + ["flower_color_free_text"]
    done = already_done_ids(OUTPUT_CSV)
    mode = "a" if done else "w"
    print(f"Total {len(rows)}; done {len(done)}; mode={mode}", flush=True)

    path = resolve_model_path(MODEL_NAME)
    tokenizer = AutoTokenizer.from_pretrained(path, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        path, trust_remote_code=True, torch_dtype=torch.bfloat16, device_map="auto")
    model.eval()

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_CSV.open(mode, newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if mode == "w":
            w.writeheader()
        n = 0
        for row in rows:
            if row["species_id"] in done:
                continue
            try:
                row["flower_color_free_text"] = infer(tokenizer, model, row.get("raw_text", ""))
            except Exception as e:
                row["flower_color_free_text"] = f"ERROR: {e}"
            w.writerow(row)
            f.flush()
            n += 1
            if n % 25 == 0:
                print(f"Processed {n}...", flush=True)
    print(f"DONE. {n} new -> {OUTPUT_CSV}", flush=True)

if __name__ == "__main__":
    main()
