import os
import re
import unicodedata
from difflib import SequenceMatcher

DATA_DIR = "/Users/johan/Develop/research-projects/thoracic-review-app-deploy/data"
BIB_FILE = os.path.join(DATA_DIR, "library.bib")

with open(BIB_FILE, 'r', encoding='utf-8') as f:
    text = f.read()

# Fix the escaping backslash bug if any
text = text.replace(r'\}', '}')

# Strip any existing file= lines so we can add them fresh
text = re.sub(r',\s*file\s*=\s*\{[^}]*\}', '', text)
text = re.sub(r'\s*file\s*=\s*\{[^}]*\}', '', text)

def _normalize_string(s):
    if s is None:
        return ""
    s = unicodedata.normalize('NFC', str(s).strip().lower())
    s = re.sub(r'[^a-z0-9]', '', s)
    return s.strip()

def parse_bib_entries(t):
    entries = []
    for match in re.finditer(r'@(\w+)\s*\{\s*([^,]+),', t):
        start = match.start()
        entry_type = match.group(1)
        key = match.group(2)
        depth = 0
        end = -1
        # find matching bracket
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

# We expect exactly 57 entries!
print(f"Parsed {len(entries)} entries from library.bib")

for entry in entries:
    content = entry["content"]
    
    # Very generous title matcher
    title_m = re.search(r'title\s*=\s*[\{"]?(.*?)[\}"]?,\n', content, re.IGNORECASE | re.DOTALL)
    if not title_m:
        title_m = re.search(r'title\s*=\s*(.+)', content, re.IGNORECASE)
    title_raw = title_m.group(1) if title_m else ""
    title_raw = title_raw.replace('{', '').replace('}', '')
    entry["norm_title"] = _normalize_string(title_raw)
    
    author_m = re.search(r'author\s*=\s*[\{"]?(.*?)[\}"]?,\n', content, re.IGNORECASE | re.DOTALL)
    if not author_m:
        author_m = re.search(r'author\s*=\s*(.+)', content, re.IGNORECASE)
    if author_m:
        author_raw = author_m.group(1).replace('\n', ' ').strip().replace('{', '').replace('}', '')
        entry["all_author_norm"] = _normalize_string(author_raw)
        
        # Grab strictly the first author
        first_author = author_raw.split(' and ')[0].split(',')[0]
        entry["first_author_norm"] = _normalize_string(first_author)
    else:
        entry["all_author_norm"] = ""
        entry["first_author_norm"] = ""
        
    year_m = re.search(r'year\s*=\s*[\{"]?(\d{4})[\}"]?', content, re.IGNORECASE)
    entry["year"] = _normalize_string(year_m.group(1)) if year_m else ""

# Load PDFs
pdfs = [f for f in os.listdir(DATA_DIR) if f.endswith(".pdf") and not f.startswith(".")]

# Parse PDF metadata according to user format:
# NN_FirstAuthor et al. - YYYY - Title.pdf
# 'et al' might be missing, spaces around - might be missing.
parsed_pdfs = []
for pdf in sorted(pdfs):
    filename_clean = pdf.replace(".pdf", "")
    
    # Try regex match: ^(\d+)_([^-]+?)(?:\s+et al\.?)?\s*-\s*(\d{4})\s*-\s*(.+)$
    m = re.match(r'^(\d+)_([^-]+?)(?:\s+et al\.?)?\s*-\s*(\d{4})\s*-\s*(.+)$', filename_clean, re.IGNORECASE)
    
    if m:
        prefix = int(m.group(1))
        author = m.group(2).strip()
        year = m.group(3).strip()
        title = m.group(4).strip()
    else:
        # Fallback manual split
        prefix_m = re.match(r'^(\d+)_', pdf)
        prefix = int(prefix_m.group(1)) if prefix_m else -1
        
        filename_without_prefix = re.sub(r'^\d+[_\s]', '', filename_clean).strip()
        parts = filename_without_prefix.split("-")
        parts = [p.strip() for p in parts if p.strip()]
        
        if len(parts) >= 3:
            author = parts[0].replace("et al.", "").replace("et al", "").strip()
            year = parts[1]
            title = "-".join(parts[2:])
        else:
            author = ""
            year = ""
            title = filename_without_prefix
            
    parsed_pdfs.append({
        "pdf": pdf,
        "author_norm": _normalize_string(author),
        "year": _normalize_string(year),
        "title_norm": _normalize_string(title)
    })

def similar(a, b):
    return SequenceMatcher(None, a, b).ratio()

# Calculate score matrix
matches = []
for p in parsed_pdfs:
    best_score = -1
    best_entry = None
    
    for entry in entries:
        score = 0
        if p["year"] and p["year"] == entry["year"]:
            score += 10
            
        if p["author_norm"] and (p["author_norm"] in entry["first_author_norm"] or entry["first_author_norm"] in p["author_norm"]):
            score += 50
        elif p["author_norm"] and p["author_norm"] in entry["all_author_norm"]:
            score += 20
            
        if p["title_norm"]:
            if entry["norm_title"].startswith(p["title_norm"]) or p["title_norm"].startswith(entry["norm_title"]):
                # Truncated title match
                score += 100
            elif p["title_norm"] in entry["norm_title"] or entry["norm_title"] in p["title_norm"]:
                score += 80
            else:
                sim = similar(p["title_norm"], entry["norm_title"])
                score += int(sim * 60) # Up to 60 points for fuzzy sim
                
        matches.append({
            "pdf_obj": p,
            "entry": entry,
            "score": score
        })

# Greedy assignment
matches.sort(key=lambda x: x["score"], reverse=True)
matched_pdfs = set()
matched_entries = set()
final_pairings = []

out_text = ""
matched_list = []

for m in matches:
    pdf = m["pdf_obj"]["pdf"]
    entry_key = m["entry"]["key"]
    
    if pdf not in matched_pdfs and entry_key not in matched_entries:
        matched_pdfs.add(pdf)
        matched_entries.add(entry_key)
        
        final_pairings.append(m)

final_pairings.sort(key=lambda x: x["pdf_obj"]["pdf"])

for m in final_pairings:
    pdf = m["pdf_obj"]["pdf"]
    entry = m["entry"]
    
    content = entry["content"]
    # insert file attribute
    new_content = content.replace('\n}', f',\n\tfile = {{{pdf}}}\n}}')
    out_text += new_content + "\n\n"
    matched_list.append(f"- **{pdf}** -> `{entry['key']}` (score: {m['score']})")

print(f"Matched {len(final_pairings)} of run length pdfs ({len(pdfs)}) and entries ({len(entries)}).")

with open(BIB_FILE, 'w', encoding='utf-8') as f:
    f.write(out_text)
    
with open(os.path.join(DATA_DIR, "match_report.md"), "w") as f:
    f.write("# Perfect PDF to BibTeX Mapping\n\n")
    f.write("\n".join(matched_list))

unmatched_pdfs = [p for p in pdfs if p not in matched_pdfs]
if unmatched_pdfs:
    print("UNMATCHED PDFs:")
    for u in unmatched_pdfs:
        print(f" - {u}")
else:
    print("All PDFs mapped successfully!")
