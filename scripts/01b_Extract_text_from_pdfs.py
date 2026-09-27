from pdfminer.high_level import extract_text
import os
from pathlib import Path

BASE = (
    Path(os.environ["THESIS_ROOT"]).expanduser().resolve()
    if os.environ.get("THESIS_ROOT")
    else Path(__file__).resolve().parents[1]
)
raw_data_dir = str(BASE / "raw_data")
pdf_files = [
    "FLORA OF INDIA VOL.1.pdf",
    "FLORA OF INDIA VOL.2.pdf",
    "FLORA OF INDIA VOL.3.pdf",
    "FLORA OF INDIA VOL.4.pdf",
    "FLORA OF INDIA VOL.5.pdf",
    "FLORA OF INDIA VOL.12.pdf",
    "FLORA OF INDIA VOL.13.pdf",
    "FLORA OF INDIA VOL.23.pdf",
]

for pdf_file in pdf_files:
    pdf_path = os.path.join(raw_data_dir, pdf_file)
    text = extract_text(pdf_path)
    txt_file = pdf_file.replace(".pdf", ".txt")
    with open(os.path.join(raw_data_dir, txt_file), "w", encoding="utf-8") as f:
        f.write(text)
    print(f"Extracted text from {pdf_file} to {txt_file}")
