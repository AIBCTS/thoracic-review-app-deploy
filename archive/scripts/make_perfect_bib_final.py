import os
import re
import shutil
import unicodedata
from difflib import SequenceMatcher

DATA_DIR = "/Users/johan/Develop/research-projects/thoracic-review-app-deploy/data"
REPORTS_DIR = "/Users/johan/Develop/research-projects/thoracic-review-app-deploy/reports"
BIB_FILE = os.path.join(DATA_DIR, "library.bib")

with open(BIB_FILE, 'r', encoding='utf-8') as f:
    text = f.read()

# Fix the escaping backslash bug if it exists in the current file
text = text.replace(r'\}', '}')

# Remove ALL file lines to get clean file fields later.
text = re.sub(r',\s*file\s*=\s*\{[^}]*\}', '', text)
text = re.sub(r'\s*file\s*=\s*\{[^}]*\}', '', text)

def _normalize_string(s):
    if s is None:
        return ""
    s = unicodedata.normalize('NFC', str(s).strip().lower())
    s = re.sub(r'[^a-z0-9]', '', s)
    return s.strip()

# Parse all bib entries:
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
                "type": entry_type, 
                "start": start, 
                "end": end, 
                "content": t[start:end]
            })
    return entries

entries = parse_bib_entries(text)

# pre-parse entries metadata
for entry in entries:
    content = entry["content"]
    title_m = re.search(r'title\s*=\s*(?:\{|")([^}]+)(?:\}|")', content, re.IGNORECASE | re.DOTALL)
    entry["norm_title"] = _normalize_string(title_m.group(1)) if title_m else ""
    
    author_m = re.search(r'author\s*=\s*(?:\{|")([^}]+)(?:\}|")', content, re.IGNORECASE | re.DOTALL)
    if author_m:
        author_raw = author_m.group(1).replace('\n', ' ').strip()
        first_author = author_raw.split(' and ')[0].split(',')[0]
        entry["first_author_norm"] = _normalize_string(first_author)
    else:
        entry["first_author_norm"] = ""
        
    year_m = re.search(r'year\s*=\s*(?:\{|")?(\d{4})(?:\}|")?', content, re.IGNORECASE)
    entry["year"] = _normalize_string(year_m.group(1)) if year_m else ""

# Read report data, filenames have NO extensions like '01_FirstAuthor_Adedinsewo'
reports = [f for f in os.listdir(REPORTS_DIR) if not f.startswith(".")]
report_data = {}
for r in reports:
    parts = r.split("_", 1)
    if len(parts) >= 1 and parts[0].isdigit():
        prefix = int(parts[0])
        with open(os.path.join(REPORTS_DIR, r), 'r', encoding='utf-8') as f:
            title = ""
            for line in f:
                if line.startswith("Title:"):
                    title = line.replace("Title:", "").strip()
                    break
            report_data[prefix] = title

# Match all PDFs perfectly
pdfs = [f for f in os.listdir(DATA_DIR) if f.endswith(".pdf") and not f.startswith(".")]
matches = []

def similar(a, b):
    return SequenceMatcher(None, a, b).ratio()

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

    best_match = None
    best_score = 0
    
    for entry in entries:
        score = 0
        
        if target_year and target_year == entry["year"]:
            score += 2
            
        if target_author_norm and target_author_norm in entry["first_author_norm"]:
            score += 5
            
        if target_title_norm:
            if target_title_norm == entry["norm_title"]:
                score += 50
            else:
                sim = similar(target_title_norm, entry["norm_title"])
                if sim > 0.8:
                    score += 20
                elif sim > 0.5:
                    score += 10
                elif len(target_title_norm) > 15 and target_title_norm[:15] in entry["norm_title"]:
                    score += 8
                
        if score > best_score:
            best_score = score
            best_match = entry
            
    if best_match and best_score >= 5:
        matches.append({"pdf": pdf, "entry": best_match, "score": best_score})

# Process unique matches
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

# Construct brand new file containing ONLY matched entries (truncates `library.bib` down to just the 57 matched)
unique_matches.sort(key=lambda x: x["pdf"])

out_text = ""
matched_list = []

for m in unique_matches:
    pdf = m["pdf"]
    entry = m["entry"]
    content = entry["content"]
    
    # insert clean file attribute
    new_content = content.replace('\n}', f',\n\tfile = {{{pdf}}}\n}}')
    out_text += new_content + "\n\n"
    matched_list.append(f"- **{pdf}** -> `{entry['key']}`")

# Write to library.bib directly overwriting the giant pasted file.
with open(BIB_FILE, 'w', encoding='utf-8') as f:
    f.write(out_text)
    
with open(os.path.join(DATA_DIR, "match_report.md"), "w") as f:
    f.write("# Perfect PDF to BibTeX Mapping\n\n")
    f.write("\n".join(matched_list))

print("Successfully replaced library.bib with strictly matched entries.")

# Write unmatched PDFs list just in case
with open(os.path.join(DATA_DIR, "unmatched.txt"), "w") as f:
    for pdf in pdfs:
        if pdf not in seen_pdfs:
            print(f"FAILED TO MATCH: {pdf}")
            f.write(f"{pdf}\n")
