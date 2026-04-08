import os
import re
import unicodedata

DATA_DIR = "/Users/johan/Develop/research-projects/thoracic-review-app-deploy/data"
BIB_FILE = os.path.join(DATA_DIR, "library.bib")

def _normalize_string(s):
    if s is None:
        return ""
    return unicodedata.normalize('NFC', str(s).strip().lower())

def extract_metadata_from_filename(filename):
    filename_clean = filename.replace(".pdf", "")
    filename_clean = re.sub(r'^\d+[_\s]', '', filename_clean).strip()
    
    parts = [p.strip() for p in filename_clean.split(" - ")]
    if len(parts) < 3:
        parts_alt = [p.strip() for p in filename_clean.split("-")]
        if len(parts_alt) >= 3:
            parts = parts_alt
            
    match_title = _normalize_string(parts[2]) if len(parts) >= 3 else _normalize_string(filename_clean[:30])
    match_author = _normalize_string(parts[0].replace(" et al.", "")) if len(parts) >= 1 else ""
    match_year = _normalize_string(parts[1]) if len(parts) >= 2 else ""

    return match_author, match_year, match_title

def parse_bib_entries(text):
    entries = []
    for match in re.finditer(r'@\w+\s*\{\s*([^,]+),', text):
        start = match.start()
        key = match.group(1)
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
            entries.append({"key": key, "start": start, "end": end, "content": text[start:end]})
    return entries

with open(BIB_FILE, 'r', encoding='utf-8') as f:
    bib_text = f.read()

entries = parse_bib_entries(bib_text)
pdfs = [f for f in os.listdir(DATA_DIR) if f.endswith(".pdf")]

print(f"Loaded {len(entries)} entries and {len(pdfs)} PDFs.")

matches = []

for pdf in sorted(pdfs):
    author, year, title = extract_metadata_from_filename(pdf)
    best_match = None
    best_score = 0
    
    for entry in entries:
        content = entry["content"]
        
        title_m = re.search(r'title\s*=\s*(?:\{|")([^}]+)(?:\}|")', content, re.IGNORECASE | re.DOTALL)
        entry_title = _normalize_string(title_m.group(1).replace('\n', ' ')) if title_m else ""
        
        author_m = re.search(r'author\s*=\s*(?:\{|")([^}]+)(?:\}|")', content, re.IGNORECASE | re.DOTALL)
        entry_author = _normalize_string(author_m.group(1).replace('\n', ' ')) if author_m else ""
        
        year_m = re.search(r'year\s*=\s*(?:\{|")?(\d{4})(?:\}|")?', content, re.IGNORECASE)
        entry_year = _normalize_string(year_m.group(1)) if year_m else ""
        
        score = 0
        if author and author in entry_author:
            score += 1
        if year and year == entry_year:
            score += 1
        if title and (title in entry_title or entry_title in title or len(title) > 10 and (title[:15] in entry_title)):
            score += 2
            
        if score > best_score:
            best_score = score
            best_match = entry
            
    if best_match and best_score >= 2:
        matches.append((pdf, best_match))
    else:
        print(f"NO MATCH FOR: {pdf}")

unique_matches = []
seen = set()
for pdf, entry in matches:
    if pdf not in seen:
        seen.add(pdf)
        unique_matches.append((pdf, entry))

unique_matches.sort(key=lambda x: x[1]['start'], reverse=True)

out_text = bib_text
matched_list = []

for pdf, entry in unique_matches:
    content = entry["content"]
    start = entry["start"]
    end = entry["end"]
    
    # Use \g<1> instead of \1 to prevent group expansion bugs when pdf name starts with a number.
    if re.search(r'\bfile\s*=\s*\{[^}]*\}', content):
        new_content = re.sub(r'(\bfile\s*=\s*\{)[^}]*\}', rf'\g<1>{pdf}\}}', content)
    else:
        new_content = content.replace('\n}', f',\n\tfile = {{{pdf}}}\n}}')
        
    out_text = out_text[:start] + new_content + out_text[end:]
    matched_list.append(f"- **{pdf}** -> `{entry['key']}`")

with open(BIB_FILE, 'w', encoding='utf-8') as f:
    f.write(out_text)
    
print("Successfully matched and updated entries.")
if matched_list:
    matched_list.reverse()
    with open(os.path.join(DATA_DIR, "match_report.md"), "w") as f:
        f.write("# PDF to BibTeX Mapping\n\n")
        f.write("\n".join(matched_list))
