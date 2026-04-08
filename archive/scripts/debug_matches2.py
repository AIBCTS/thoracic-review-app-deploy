import re
import os
import unicodedata
from difflib import SequenceMatcher

BACKUP_FILE = "/Users/johan/Develop/research-projects/thoracic-review-app-deploy/data/library.bib.backup"
with open(BACKUP_FILE, 'r', encoding='utf-8') as f:
    text = f.read()

def parse_bib_entries(t):
    entries = []
    for match in re.finditer(r'@(\w+)\s*\{\s*([^,]+),', t):
        start = match.start()
        entry_type = match.group(1)
        key = match.group(2)
        depth = 0
        end = -1
        for i in range(start, len(t)):
            if t[i] == '{':
                depth += 1
            elif t[i] == '}':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end != -1:
            entries.append({
                "key": key, 
                "content": t[start:end]
            })
    return entries

entries = parse_bib_entries(text)

# We want the content of entry 'michelson_developing_2024'
entry = next(e for e in entries if e["key"] == "michelson_developing_2024")

def _normalize_string(s):
    if s is None:
        return ""
    s = unicodedata.normalize('NFC', str(s).strip().lower())
    s = re.sub(r'[^a-z0-9]', '', s)
    return s.strip()

content = entry["content"]
title_m = re.search(r'title\s*=\s*(?:\{|")([^}]+)(?:\}|")', content, re.IGNORECASE | re.DOTALL)
entry_title_norm = _normalize_string(title_m.group(1)) if title_m else ""
author_m = re.search(r'author\s*=\s*(?:\{|")([^}]+)(?:\}|")', content, re.IGNORECASE | re.DOTALL)
first_author_norm = _normalize_string(author_m.group(1).replace('\n', ' ').strip().split(' and ')[0].split(',')[0])
year_m = re.search(r'year\s*=\s*(?:\{|")?(\d{4})(?:\}|")?', content, re.IGNORECASE)
entry_year = _normalize_string(year_m.group(1)) if year_m else ""

# Read report data
REPORTS_DIR = "/Users/johan/Develop/research-projects/thoracic-review-app-deploy/reports"
DATA_DIR = "/Users/johan/Develop/research-projects/thoracic-review-app-deploy/data"
reports = [f for f in os.listdir(REPORTS_DIR) if f.endswith(".md") and not f.startswith(".")]
report_data = {}
for r in reports:
    prefix = int(r.split("_")[0])
    with open(os.path.join(REPORTS_DIR, r), 'r', encoding='utf-8') as f:
        title = ""
        for line in f:
            if line.startswith("Title:"):
                title = line.replace("Title:", "").strip()
                break
        report_data[prefix] = title

pdfs = [f for f in os.listdir(DATA_DIR) if f.endswith(".pdf") and not f.startswith(".")]

for pdf in sorted(pdfs):
    prefix_m = re.match(r'^(\d+)_', pdf)
    prefix = int(prefix_m.group(1)) if prefix_m else -1
    target_title_raw = report_data.get(prefix, "")
    filename_clean = pdf.replace(".pdf", "")
    filename_clean = re.sub(r'^\d+[_\s]', '', filename_clean).strip()
    parts = [p.strip() for p in filename_clean.split(" - ")]
    if len(parts) >= 3:
        target_author_raw = parts[0].replace(" et al.", "")
        target_year = parts[1]
    else:
        target_author_raw = ""
        target_year = ""
    if not target_title_raw and len(parts) >= 3:
        target_title_raw = " ".join(parts[2:])
        
    target_author_norm = _normalize_string(target_author_raw)
    target_title_norm = _normalize_string(target_title_raw)

    score = 0
    if target_year and target_year == entry_year:
        score += 2
    if target_author_norm and target_author_norm in first_author_norm:
        score += 5
    if target_title_norm:
        sim = SequenceMatcher(None, target_title_norm, entry_title_norm).ratio()
        if sim > 0.8:
            score += 20
        elif sim > 0.5:
            score += 10
        elif len(target_title_norm) > 15 and target_title_norm[:15] in entry_title_norm:
            score += 8
            
    if score > 0:
        print(f"PDF {pdf} scored {score} on michelson_developing_2024")
