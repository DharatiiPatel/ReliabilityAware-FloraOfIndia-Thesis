import os
import csv
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE = (
    Path(os.environ["THESIS_ROOT"]).expanduser().resolve()
    if os.environ.get("THESIS_ROOT")
    else Path(__file__).resolve().parents[1]
)
sys.path.insert(0, str(BASE / "scripts"))
from lib.volume_match import (  # noqa: E402
    TARGET_VOLUME_NUMBERS,
    parse_volume_number,
    title_matches_target_volumes,
)

base_url = "https://bsi.gov.in/page/en/flora-of-india"

# Exact volume numbers (not substring titles). Vol. 1 must not match Vol. 10–13.
TARGET_VOLUMES = TARGET_VOLUME_NUMBERS

output_csv = str(BASE / "raw_data" / "flora_of_india_volumes.csv")

response = requests.get(base_url)
if response.status_code != 200:
    print(f"Failed to fetch page: status code {response.status_code}")
    exit(1)

soup = BeautifulSoup(response.text, "html.parser")
rows = soup.select("table tr")

volume_data = []

for row in rows:
    cells = row.find_all("td")
    if len(cells) < 3:
        continue
    title = cells[1].text.strip()
    link_tag = cells[2].find("a")
    pdf_link = link_tag["href"] if link_tag else None

    if title_matches_target_volumes(title, TARGET_VOLUMES) and pdf_link:
        if not pdf_link.startswith("http"):
            pdf_link = "https://bsi.gov.in" + pdf_link

        vol_n = parse_volume_number(title)
        volume_data.append([title, pdf_link, vol_n])
        print(f"Found volume: {title} (parsed={vol_n}), PDF link: {pdf_link}")

with open(output_csv, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["Volume Title", "PDF URL", "VolumeNumber"])
    writer.writerows(volume_data)

print(f"Scraping complete. Volume links saved to {output_csv}")
print(f"Target volume numbers: {sorted(TARGET_VOLUMES)}")
