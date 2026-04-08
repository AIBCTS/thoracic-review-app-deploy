import os
import re
import shutil
import unicodedata
from difflib import SequenceMatcher

DATA_DIR = "/Users/johan/Develop/research-projects/thoracic-review-app-deploy/data"
REPORTS_DIR = "/Users/johan/Develop/research-projects/thoracic-review-app-deploy/reports"
BIB_FILE = os.path.join(DATA_DIR, "library.bib")
BACKUP_FILE = os.path.join(DATA_DIR, "library.bib.backup")

# 1. Provide a backup
if not os.path.exists(BACKUP_FILE):
    shutil.copy(BIB_FILE, BACKUP_FILE)

# Read from backup to make sure we always start fresh
with open(BACKUP_FILE, 'r', encoding='utf-8') as f:
    bib_text = f.read()

def _normalize_string(s):
    if s is None:
        return ""
    # Strip spaces and special chars, lowercase
    s = unicodedata.normalize('NFC', str(s).strip().lower())
    s = re.sub(r'[^a-z0-9]', '', s)
    return s.strip()

def similar(a, b):
    # calculate string similarity ratio
    return SequenceMatcher(None, a, b).ratio()

# Parse the Bib file
def parse_bib_entries(text):
    entries = []
    for match in re.finditer(r'@(\w+)\s*\{\s*([^,]+),', text):
        start = match.start()
        entry_type = match.group(1)
        key = match.group(2)
        depth = 0
        end = -1
        for i in range(start, len(text)):
            if text[i] == '{':
                depth += 1
            elif text[i] == '}':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end != -1:
            entries.append({"key": key, "type": entry_type, "start": start, "end": end, "content": text[start:end]})
    return entries

entries = parse_bib_entries(bib_text)
for entry in entries:
    content = entry["content"]
    title_m = re.search(r'title\s*=\s*(?:\{|")([^}]+)(?:\}|")', content, re.IGNORECASE | re.DOTALL)
    entry["raw_title"] = title_m.group(1).replace('\n', ' ').strip() if title_m else ""
    entry["norm_title"] = _normalize_string(entry["raw_title"])
    
    author_m = re.search(r'author\s*=\s*(?:\{|")([^}]+)(?:\}|")', content, re.IGNORECASE | re.DOTALL)
    entry["raw_author"] = author_m.group(1).replace('\n', ' ').strip() if author_m else ""
    # parse first author
    first_author = entry["raw_author"].split(' and ')[0]
    entry["first_author_norm"] = _normalize_string(first_author.split(',')[0]) # usually Lastname, Firstname

reports = [f for f in os.listdir(REPORTS_DIR) if f.endswith(".md") and not f.startswith(".")]
report_data = {}
for r in reports:
    prefix_m = re.match(r'^(\d+)_', r)
    if prefix_m:
        prefix = int(prefix_m.group(1))
        with open(os.path.join(REPORTS_DIR, r), 'r', encoding='utf-8') as f:
            lines = f.readlines()
            title = ""
            for line in lines:
                if line.startswith("Title:"):
                    title = line.replace("Title:", "").strip()
                    break
            report_data[prefix] = title

pdfs = [f for f in os.listdir(DATA_DIR) if f.endswith(".pdf") and not f.startswith(".")]
matches = []

for pdf_filename in sorted(pdfs):
    prefix_m = re.match(r'^(\d+)_', pdf_filename)
    prefix = int(prefix_m.group(1)) if prefix_m else -1
    
    target_title_raw = report_data.get(prefix, "")
    
    filename_clean = pdf_filename.replace(".pdf", "")
    filename_clean = re.sub(r'^\d+[_\s]', '', filename_clean).strip()
    parts = [p.strip() for p in filename_clean.split(" - ")]
    
    if len(parts) >= 3:
        target_author_raw = parts[0].replace(" et al.", "")
    else:
        target_author_raw = ""

    if not target_title_raw and len(parts) >= 3:
        target_title_raw = " ".join(parts[2:])
        
    target_author_norm = _normalize_string(target_author_raw)
    target_title_norm = _normalize_string(target_title_raw)

    best_match = None
    best_score = 0
    
    for entry in entries:
        score = 0
        
        if target_author_norm and target_author_norm in entry["first_author_norm"]:
            score += 3
            
        if target_title_norm:
            sim = similar(target_title_norm, entry["norm_title"])
            if sim > 0.8:
                score += 10
            elif sim > 0.5:
                score += 5
            if len(target_title_norm) > 15 and target_title_norm[:15] in entry["norm_title"]:
                score += 4
                
        if score > best_score:
            best_score = score
            best_match = entry
            
    if best_match and best_score >= 3:
        matches.append({"pdf": pdf_filename, "entry": best_match, "score": best_score})

# Sort matches by score so we favor the best mapping
matches.sort(key=lambda x: x["score"], reverse=True)

unique_matches = []
seen_pdfs = set()
seen_entries = set()

for m in matches:
     pdf = m["pdf"]
     entry = m["entry"]
     if pdf not in seen_pdfs and entry["key"] not in seen_entries:
         seen_pdfs.add(pdf)
         seen_entries.add(entry["key"])
         unique_matches.append(m)

print(f"Matched {len(unique_matches)} of {len(pdfs)} PDFs.")

# If we missed any pdfs, print them
for pdf in sorted(pdfs):
    if pdf not in seen_pdfs:
        print(f"FAILED TO MATCH: {pdf}")

out_text = ""
matched_list = []

# Sort alphabetically by PDF for the output
unique_matches.sort(key=lambda x: x["pdf"])

for m in unique_matches:
    pdf = m["pdf"]
    entry = m["entry"]
    content = entry["content"]
    
    # Remove any existing file = {...} to cleanly set the new one
    content = re.sub(r',\s*file\s*=\s*\{[^}]*\}', '', content)
    content = re.sub(r'\bfile\s*=\s*\{[^}]*\}', '', content)
    
    # Add new file field
    new_content = content.replace('\n}', f',\n\tfile = {{{pdf}}}\n}}')
    out_text += new_content + "\n\n"
    
    matched_list.append(f"- **{pdf}** -> `{entry['key']}`")

# Write out the brand new streamlined file
with open(BIB_FILE, 'w', encoding='utf-8') as f:
    f.write(out_text)

matched_list.sort()
with open(os.path.join(DATA_DIR, "match_report.md"), "w") as f:
    f.write("# Perfect PDF to BibTeX Mapping\n\n")
    f.write("\n".join(matched_list))
    
print("Successfully generated new bib file.")
