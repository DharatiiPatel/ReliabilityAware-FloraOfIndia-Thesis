import csv
import os
from pathlib import Path

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

"""
Extract flower colour from treatment descriptions with Qwen2.5-7B-Instruct.

Reads  : Processed Data/experiments/species_descriptions_treatments.csv
Writes : Processed Data/experiments/flower_color_qwen_clean.csv
"""

BASE_DIR = (
    Path(os.environ["THESIS_ROOT"]).expanduser().resolve()
    if os.environ.get("THESIS_ROOT")
    else Path(__file__).resolve().parents[1]
)
INPUT_CSV = BASE_DIR / "Processed Data" / "experiments" / "species_descriptions_treatments.csv"
OUTPUT_CSV = BASE_DIR / "Processed Data" / "experiments" / "flower_color_qwen_clean.csv"

MODEL_NAME = "Qwen/Qwen2.5-7B-Instruct"
MAX_NEW_TOKENS = 32

SYSTEM_MESSAGE = (
    "You are an expert botanist. Your ONLY job is to extract the flower colour "
    "from Flora of India species descriptions. "
    "Return a very short phrase like 'flowers white', 'flowers yellow with red centre', "
    "'flowers blue or purple', etc. If flower colour is not mentioned, return exactly "
    "'no flower colour mentioned'. Do NOT add explanations."
)

def load_model_and_tokenizer():
    token_kwargs = {}
    hf_token = os.environ.get("HF_TOKEN")
    if hf_token:
        token_kwargs["token"] = hf_token

    print(f"Loading tokenizer and model: {MODEL_NAME}", flush=True)
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True, **token_kwargs)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        trust_remote_code=True,
        torch_dtype=torch.float16,
        device_map="auto",
        **token_kwargs,
    )
    model.eval()
    return tokenizer, model

def infer_flower_color(tokenizer, model, description: str) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_MESSAGE},
        {"role": "user", "content": f"Species description:\n\n{description}\n\nWhat is the flower colour?"},
    ]
    inputs = tokenizer.apply_chat_template(
        messages, return_tensors="pt", add_generation_prompt=True,
    ).to(model.device)
    with torch.no_grad():
        outputs = model.generate(
            inputs,
            max_new_tokens=MAX_NEW_TOKENS,
            do_sample=False,
            temperature=0.0,
            pad_token_id=tokenizer.eos_token_id,
        )
    generated_ids = outputs[0][inputs.shape[-1]:]
    return tokenizer.decode(generated_ids, skip_special_tokens=True).strip()

def already_done_ids(path: Path):
    """Resume support: return set of species_id already written."""
    done = set()
    if path.exists():
        with open(path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                done.add(row.get("species_id", ""))
    return done

def main():
    if not INPUT_CSV.exists():
        raise FileNotFoundError(f"Input CSV not found: {INPUT_CSV}")

    rows = list(csv.DictReader(open(INPUT_CSV, encoding="utf-8")))
    in_fields = list(rows[0].keys())
    out_fields = in_fields + ["flower_color_free_text"]

    done = already_done_ids(OUTPUT_CSV)
    mode = "a" if done else "w"
    print(f"Total species: {len(rows)}; already done: {len(done)}; mode={mode}", flush=True)

    tokenizer, model = load_model_and_tokenizer()
    print(f"Reading: {INPUT_CSV}\nWriting: {OUTPUT_CSV}", flush=True)

    with open(OUTPUT_CSV, mode, newline="", encoding="utf-8") as f_out:
        writer = csv.DictWriter(f_out, fieldnames=out_fields)
        if mode == "w":
            writer.writeheader()

        count = 0
        for row in rows:
            if row["species_id"] in done:
                continue
            description = row.get("raw_text", "")
            try:
                flower_color = infer_flower_color(tokenizer, model, description)
            except Exception as e:
                flower_color = f"ERROR: {e}"
            row["flower_color_free_text"] = flower_color
            writer.writerow(row)
            f_out.flush()
            count += 1
            if count % 25 == 0:
                print(f"Processed {count} new species...", flush=True)

    print(f"DONE. Processed {count} new species. Output: {OUTPUT_CSV}")

if __name__ == "__main__":
    main()
