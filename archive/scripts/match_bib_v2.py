import os
import re
import unicodedata

DATA_DIR = "/Users/johan/Develop/research-projects/thoracic-review-app-deploy/data"
BIB_FILE = os.path.join(DATA_DIR, "library.bib")

def _normalize_string(s):
    if s is None:
        return ""
    # Strip non-alphanumeric except spaces for robust matching
    s = unicodedata.normalize('NFC', str(s).strip().lower())
    s = re.sub(r'[^a-z0-9 ]', '', s)
    return s.strip()

def extract_metadata_from_filename(filename):
    filename_clean = filename.replace(".pdf", "")
    filename_clean = re.sub(r'^\d+[_\s]', '', filename_clean).strip()
    
    parts = [p.strip() for p in filename_clean.split(" - ")]
    if len(parts) >= 3:
        author = parts[0].replace(" et al.", "")
        year = parts[1]
        title = " ".join(parts[2:])
        return _normalize_string(author), _normalize_string(year), _normalize_string(title)
        
    parts_alt = [p.strip() for p in filename_clean.split("-")]
    if len(parts_alt) >= 3:
        author = parts_alt[0]
        year = parts_alt[1]
        title = " ".join(parts_alt[2:])
        return _normalize_string(author), _normalize_string(year), _normalize_string(title)
        
    return "", "", ""

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

# Parse Bib entries metadata once
for entry in entries:
    content = entry["content"]
    
    title_m = re.search(r'title\s*=\s*(?:\{|")([^}]+)(?:\}|")', content, re.IGNORECASE | re.DOTALL)
    entry["title"] = _normalize_string(title_m.group(1)) if title_m else ""
    
    author_m = re.search(r'author\s*=\s*(?:\{|")([^}]+)(?:\}|")', content, re.IGNORECASE | re.DOTALL)
    entry["author"] = _normalize_string(author_m.group(1)) if author_m else ""
    
    year_m = re.search(r'year\s*=\s*(?:\{|")?(\d{4})(?:\}|")?', content, re.IGNORECASE)
    entry["year"] = _normalize_string(year_m.group(1)) if year_m else ""

matches = []

for pdf in sorted(pdfs):
    author, year, title = extract_metadata_from_filename(pdf)
    best_match = None
    best_score = 0
    
    for entry in entries:
        score = 0
        is_year_match = (year == entry["year"])
        
        # Author matching
        is_author_match = False
        if author and author in entry["author"]:
            is_author_match = True
            
        # Title matching
        is_title_match = False
        if title:
            # check if 15 chars of title match
            short_title = title[:15]
            if short_title and short_title in entry["title"]:
                is_title_match = True
        
        if is_year_match and is_author_match and is_title_match:
            score = 10
        elif is_year_match and is_author_match:
            score = 5
        elif is_year_match and is_title_match:
            score = 5
        elif is_author_match and is_title_match:
            score = 3
            
        if score > best_score:
            best_score = score
            best_match = entry
            
    if best_match and best_score >= 5:
        matches.append((pdf, best_match))
    else:
        print(f"NO GOOD MATCH FOR: {pdf} (Author: {author}, Year: {year}, Title: {title[:15]})")

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
    
    if re.search(r'\bfile\s*=\s*\{[^}]*\}', content):
        new_content = re.sub(r'(\bfile\s*=\s*\{)[^}]*\}', rf'\g<1>{pdf}\}}', content)
    else:
        new_content = content.replace('\n}', f',\n\tfile = {{{pdf}}}\n}}')
        
    out_text = out_text[:start] + new_content + out_text[end:]
    matched_list.append(f"- **{pdf}** -> `{entry['key']}`")

# Also run `git checkout` to restore the bib file first since we mutated it earlier poorly.
import subprocess
subprocess.run(["git", "checkout", "data/library.bib"])

with open(BIB_FILE, 'w', encoding='utf-8') as f:
    f.write(out_text)
    
print("Successfully matched and updated entries.")
if matched_list:
    matched_list.reverse()
    with open(os.path.join(DATA_DIR, "match_report.md"), "w") as f:
        f.write("# PDF to BibTeX Mapping\n\n")
        f.write("\n".join(matched_list))
