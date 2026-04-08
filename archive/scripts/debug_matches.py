import os
import re
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

def _normalize_string(s):
    if s is None:
        return ""
    s = unicodedata.normalize('NFC', str(s).strip().lower())
    s = re.sub(r'[^a-z0-9]', '', s)
    return s.strip()

for entry in entries:
    content = entry["content"]
    title_m = re.search(r'title\s*=\s*(?:\{|")([^}]+)(?:\}|")', content, re.IGNORECASE | re.DOTALL)
    entry["norm_title"] = _normalize_string(title_m.group(1)) if title_m else ""

def similar(a, b):
    return SequenceMatcher(None, a, b).ratio()

pdf = "37_Michelson-2024-Developing machine learning mod.pdf"
target_title_norm = _normalize_string("Developing machine learning models to predict non-invasive 1-year mortality among lung transplant recipients")

results = []
for entry in entries:
    sim = similar(target_title_norm, entry["norm_title"])
    results.append((sim, entry["key"]))

results.sort(reverse=True)
print("Top 5 matches for Michelson:")
for r in results[:5]:
    print(r)
