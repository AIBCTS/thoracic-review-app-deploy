import streamlit as st
import pandas as pd
import os
import base64
from pathlib import Path
import bibtexparser
import gspread
from google.oauth2.service_account import Credentials
import unicodedata

# --- Configuration ---
st.set_page_config(layout="wide", page_title="Artificial Intelligence in Thoracic Transplantation: Current State and Future Directions")

# Define paths
BASE_DIR = Path(__file__).parent.resolve()
DATA_DIR = BASE_DIR / "data"
BIB_FILE = DATA_DIR / "library.bib"
REPORTS_DIR = BASE_DIR / "reports"
# Exported Google Sheet CSV (read-only fallback when GSheets is unavailable)
SHEET_CSV_FILE = BASE_DIR / "AI_Thoracic_Review_Database - Sheet1.csv"

# Define a writable results directory
def get_writable_csv_path():
    """Finds a writable path for the fallback CSV file."""
    potential_paths = [
        BASE_DIR / "results" / "manual_review_results.csv",
        Path("/home/results/manual_review_results.csv"),
        Path("/srv/results/manual_review_results.csv"),
        Path("/tmp/manual_review_results.csv")
    ]
    for p in potential_paths:
        try:
            # Check if directory is writable
            p.parent.mkdir(parents=True, exist_ok=True)
            test_file = p.parent / ".write_test"
            test_file.touch()
            test_file.unlink()
            return p
        except Exception:
            continue
    return BASE_DIR / "manual_review_results.csv" # Absolute fallback

CSV_FILE = get_writable_csv_path()

def read_csv_safe(file_path):
    """Reads a CSV file into a DataFrame, handling EmptyDataError."""
    if not file_path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(file_path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()

# Debug prints for Docker logs
print(f"App starting...")
print(f"BASE_DIR: {BASE_DIR}")
print(f"DATA_DIR: {DATA_DIR} (exists: {DATA_DIR.exists()})")
print(f"CSV_FILE Path: {CSV_FILE}")

# --- Helper Functions ---
import re

def _normalize_string(s):
    """Normalize string to NFC format, lowercased and stripped."""
    if s is None:
        return ""
    # NFC normalization is standard for web/data comparisons
    return unicodedata.normalize('NFC', str(s).strip().lower())

def get_numeric_prefix(filename):
    """Extracts and returns the leading integer prefix from a filename like '07_...' or '7_...'"""
    m = re.match(r'^(\d+)[_\s]', filename)
    if m:
        return int(m.group(1))
    return None

@st.cache_data
def load_bibtex():
    """Loads and parses the bibtex file once."""
    if not BIB_FILE.exists():
        return None
    with open(BIB_FILE, 'r', encoding='utf-8') as bibtex_file:
        bib_database = bibtexparser.load(bibtex_file)
    return bib_database

def get_bibtex_metadata(pdf_filename, bib_database):
    """Attempts to match a PDF filename to a BibTeX entry and return formatted metadata."""
    if not bib_database:
        return pdf_filename
        
    # 1. Exact match on the 'file' field
    for entry in bib_database.entries:
        if pdf_filename in entry.get('file', ''):
            title = entry.get('title', 'Unknown Title').replace('{', '').replace('}', '')
            authors = entry.get('author', 'Unknown Authors').replace('\n', ' ')
            author_list = authors.split(' and ')
            if len(author_list) > 3:
                authors = f"{author_list[0]} et al."
            journal = entry.get('journal', 'Unknown Journal')
            year = entry.get('year', 'Unknown Year')
            return f"{title}\n{authors}\n{journal} / {year}"

    # 2. Fallback Heuristic: try to match the title or author from the filename
    filename_clean = pdf_filename.replace(".pdf", "")
    # Strip leading numeric prefix (e.g. "07_" or "7_") before matching
    filename_clean = re.sub(r'^\d+[_\s]', '', filename_clean).strip()
    parts = [p.strip() for p in filename_clean.split(" - ")]
    if len(parts) < 3:
        parts_alt = [p.strip() for p in filename_clean.split("-")]
        if len(parts_alt) >= 3:
            parts = parts_alt
            
    match_title = _normalize_string(parts[2]) if len(parts) >= 3 else _normalize_string(filename_clean[:30])
    match_author = _normalize_string(parts[0].replace(" et al.", "")) if len(parts) >= 1 else ""
    
    for entry in bib_database.entries:
        entry_title = _normalize_string(entry.get('title', '').replace('{', '').replace('}', ''))
        entry_author = _normalize_string(entry.get('author', ''))
        
        # Match if title is very similar or author is found
        title_match = (len(match_title) > 10 and (match_title in entry_title or entry_title in match_title))
        author_match = (match_author and match_author in entry_author)
        
        if title_match or author_match:
            title = entry.get('title', 'Unknown Title').replace('{', '').replace('}', '')
            authors = entry.get('author', 'Unknown Authors').replace('\n', ' ')
            author_list = authors.split(' and ')
            if len(author_list) > 3:
                authors = f"{author_list[0]} et al."
            journal = entry.get('journal', 'Unknown Journal')
            year = entry.get('year', 'Unknown Year')
            return f"{title}\n{authors}\n{journal} / {year}"
            
    return pdf_filename

def load_report_files():
    """Loads all report files indexed by their numeric prefix."""
    report_map = {}  # int prefix -> Path
    if not REPORTS_DIR.exists():
        return report_map
    for f in REPORTS_DIR.iterdir():
        if f.is_file() and not f.name.startswith('.'):
            prefix = get_numeric_prefix(f.name)
            if prefix is not None:
                report_map[prefix] = f
    return report_map

def find_matching_report(pdf_filename):
    """Returns the Path of the report file matching a given PDF filename, or None."""
    prefix = get_numeric_prefix(pdf_filename)
    if prefix is None:
        return None
    report_map = load_report_files()
    return report_map.get(prefix)

def parse_report(report_path):
    """Parses a structured report text file into a dict of field->value."""
    field_map = {}
    if report_path is None or not report_path.exists():
        return field_map

    # Regex to capture bullet-point fields: "\t• Key: Value"
    bullet_re = re.compile(r'^\s*[•\-]\s*(.+?):\s*(.+)$')
    # Regex for quoted/reasoning fields in Section 6: "Risk: Low Risk | Quote/Reasoning: ..."
    bias_field_re = re.compile(
        r'^\s*[•\-]\s*(.+?):\s*(Low Risk|High Risk|Unclear|Not Reported|Low Concern|High Concern)'
        r'(?:\s*\|\s*(?:Quote/Reasoning|Reasoning|Quote)?:?\s*(.*))?$',
        re.IGNORECASE
    )

    with open(report_path, 'r', encoding='utf-8', errors='replace') as fh:
        lines = fh.readlines()

    for line in lines:
        # Try bias/applicability lines first (Section 6 format)
        m = bias_field_re.match(line)
        if m:
            key_raw = m.group(1).strip()
            risk_val = m.group(2).strip()
            quote_val = (m.group(3) or "").strip()
            # Sanitize unicode symbols from quotes
            quote_val = quote_val.replace('\ufffc', '').strip()
            field_map[key_raw] = risk_val
            if quote_val:
                field_map[key_raw + "__quote"] = quote_val
            continue

        # Try normal bullet fields
        m2 = bullet_re.match(line)
        if m2:
            key_raw = m2.group(1).strip()
            val = m2.group(2).strip()
            # Sanitize unicode symbols (e.g. object-replacement chars from PDF copy-paste)
            val = val.replace('\ufffc', '').strip()
            field_map[key_raw] = val

    return field_map

# Mapping from report field keys -> app form field keys
_FIELD_ALIASES = {
    # Section 1
    "Country of Data Origin":       "country_origin",
    "Organ Focus":                   "organ_focus",
    "Funding Source":                "funding_source",
    "Dataset Source":                "dataset_source",
    "Dataset Name":                  "DatasetName",
    "Conflict of Interest (COI) Declared": "coi_declared",
    "Study Period Start (Year)":     "study_start_year",
    "Study Period End (Year)":       "study_end_year",
    "Section 1 Comments/Quotes":     "section1_comments",
    # Section 2
    "Target Population":             "target_population",
    "Total Sample Size (N)":         "total_sample_size",
    "Overall Mean Age":              "mean_age",
    "Female Sex (%)": "female_sex_pct",
    "Race/Ethnicity Reported":       "race_ethnicity_reported",
    "Comorbidities / Clinical History Included": "comorbidities_included",
    "Section 2 Comments/Quotes":     "section2_comments",
    # Section 3
    "Primary ML Component":          "primary_ml_component",
    "Study Design":                  "study_design",
    "AI Model Architecture":         "ai_architecture",
    "Algorithm Name":                "algorithm_name",
    "Input Variables (Data Modality)": "input_modalities",
    "Comparator / Standard of Care": "comparator",
    "Validation Method":             "validation_method",
    "Explainability / Interpretability Used": "explainability_used",
    "Feature Selection Method":      "feature_selection",
    "Hyperparameter Tuning Reported": "hyperparameter_tuning",
    "Section 3 Comments/Quotes":     "section3_comments",
    # Section 4
    "Missing Data Handling":         "missing_data_handling",
    "Class Imbalance Addressed":     "class_imbalance",
    "Code Availability":             "code_availability",
    "Data Preprocessing / Normalization Described": "preprocessing_described",
    "Training Size (N)":             "training_size",
    "Test Size (N)":                 "test_size",
    "Section 4 Comments/Quotes":     "section4_comments",
    # Section 5
    "Target Clinical Outcome":       "target_outcome",
    "Model AUC / C-Statistic":       "model_auc",
    "Model Accuracy (%)": "model_accuracy",
    "PPV / Precision (%)":           "model_ppv",
    "Sensitivity / Recall (%)": "model_sensitivity",
    "Specificity (%)":               "model_specificity",
    "NPV (%)":                       "model_npv",
    "F1-Score":                      "model_f1",
    "Calibration Reported":          "calibration_reported",
    "Decision Curve Analysis (DCA) Reported": "dca_reported",
    "Section 5 Comments/Quotes":     "section5_comments",
    # Section 6 bias fields
    "Participants (Selection Bias)": "qa_participants_bias",
    "Participants (Selection Bias)__quote": "qa_participants_quotes",
    "Predictors (Input Variable Bias)": "qa_predictors_bias",
    "Predictors (Input Variable Bias)__quote": "qa_predictors_quotes",
    "Outcome (Definition Bias)":     "qa_outcome_bias",
    "Outcome (Definition Bias)__quote": "qa_outcome_quotes",
    "Analysis (Modeling Bias)":      "qa_analysis_bias",
    "Analysis (Modeling Bias)__quote": "qa_analysis_quotes",
    "Applicability to Review Question": "qa_applicability",
    "Applicability to Review Question__quote": "qa_applicability_quotes",
}

# Mapping from report values -> app option labels (for partial/abbreviated strings)
_VALUE_NORMALISE = {
    # AI Architecture
    "CNN": "Convolutional Neural Network (CNN)",
    "RNN": "Recurrent Neural Network (RNN/LSTM)",
    "LSTM": "Recurrent Neural Network (RNN/LSTM)",
    "ANN": "Artificial Neural Networks (ANN, MLP, NN)",
    "MLP": "Artificial Neural Networks (ANN, MLP, NN)",
    "Random Forest": "Random Forest",
    "Gradient Boosting": "Gradient Boosting (XGBoost/LightGBM)",
    "XGBoost": "Gradient Boosting (XGBoost/LightGBM)",
    "SVM": "Support Vector Machine (SVM)",
    "Unsupervised Learning (Clustering)": "Unsupervised Learning (Clustering)",
    "Unsupervised": "Unsupervised Learning (Clustering)",
    "Transformer": "Transformer/LLM",
    # Input modalities
    "Waveforms (ECG)": "Waveforms/Signals (ECG)",
    "Imaging": "Imaging (CT/CXR/Echo)",
    "Tabular": "Tabular (EMR/Clinical data)",
    "Tabular (EMR/Clinical data)": "Tabular (EMR/Clinical data)",
    "Text": "Text / Clinical Notes (NLP)",
    "NLP": "Text / Clinical Notes (NLP)",
    # Comparator
    "None": "None",
    "Other": "Other",
    # Validation
    "Internal Split": "Internal Split (Train/Test)",
    "Cross-Validation": "Cross-Validation (k-fold)",
    "External Validation (Temporal)": "External Validation (Temporal)",
    "External Validation (Geographic/Different Hospital)": "External Validation (Geographic/Different Hospital)",
    # Missing data
    "Complete Case Analysis": "Complete Case Analysis (Excluded)",
    "Simple Imputation": "Simple Imputation (Mean/Median)",
    "Multiple Imputation": "Multiple Imputation",
    # Class imbalance
    "Not Applicable": "Not Applicable / Not Reported",
    "Not Applicable/Not Reported": "Not Applicable / Not Reported",
    # Outcomes
    "Acute Rejection": "Acute Rejection",
    "Donor acceptance": "Donor acceptance for transplantation",
    "Donor acceptance for transplantation": "Donor acceptance for transplantation",
}

def normalise_report_value(val):
    """Map abbreviated report values to full app option strings."""
    if not val or val in ("NR", "Not Reported"):
        return val
    # Direct lookup
    if val in _VALUE_NORMALISE:
        return _VALUE_NORMALISE[val]
    # Partial prefix match
    for k, v in _VALUE_NORMALISE.items():
        if val.lower().startswith(k.lower()):
            return v
    return val

def report_to_review_dict(report_path):
    """Parse a report file and return a review data dict compatible with get_val/get_index."""
    raw = parse_report(report_path)
    result = {}
    for report_key, app_key in _FIELD_ALIASES.items():
        if report_key in raw:
            result[app_key] = normalise_report_value(raw[report_key])
    return result

def display_pdf(file_path):
    """Displays a PDF within a Streamlit app using an iframe."""
    try:
        with open(file_path, "rb") as f:
            base64_pdf = base64.b64encode(f.read()).decode('utf-8')
        
        # Displaying the PDF via HTML iframe
        pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="1200" type="application/pdf"></iframe>'
        st.markdown(pdf_display, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Error displaying PDF: {e}")

# --- Helper Functions ---
def get_secret_val(key, subkey=None):
    """Helper to get a secret from st.secrets, os.environ, or a mounted file."""
    # 1. Try Streamlit Secrets
    try:
        if subkey:
            if key in st.secrets and subkey in st.secrets[key]:
                return st.secrets[key][subkey]
        elif key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass

    # 2. Try Environment Variables
    env_key = f"{key.upper()}_{subkey.upper()}" if subkey else key.upper()
    if env_key in os.environ:
        return os.environ[env_key]
    
    # 3. Try Mounted File — local project secrets first, then SciLifeLab Serve paths
    mount_paths = [
        BASE_DIR / ".secrets" / "secrets.toml",  # Local dev alternative
        BASE_DIR / "secrets" / "secrets.toml",   # Local dev: project/secrets/secrets.toml
        Path("/app/secrets/secrets.toml"),
        Path("/srv/secrets/secrets.toml"),
        Path("/home/secrets/secrets.toml"),
    ]
    for mount_path in mount_paths:
        if mount_path.exists():
            try:
                import tomllib # Python 3.11+
                with open(mount_path, "rb") as f:
                    mounted_secrets = tomllib.load(f)
                    if subkey:
                        if key in mounted_secrets and subkey in mounted_secrets[key]:
                            return mounted_secrets[key][subkey]
                    elif key in mounted_secrets:
                        return mounted_secrets[key]
            except Exception as e:
                print(f"Error reading mounted secrets at {mount_path}: {e}")

    return None

@st.cache_resource
def get_gspread_client():
    """Initializes and returns the gspread client if credentials exist."""
    try:
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        
        # Get the service account info (JSON string or dict)
        sa_info = get_secret_val("gcp_service_account")
        
        if sa_info:
            if isinstance(sa_info, str):
                import json
                sa_info = json.loads(sa_info)
            
            # Ensure it's a dict for from_service_account_info
            creds = Credentials.from_service_account_info(dict(sa_info), scopes=scopes)
            return gspread.authorize(creds)
            
    except Exception as e:
        print(f"GSpread Client Init Error: {e}")
    return None

def get_worksheet():
    """Gets the active worksheet if the client is available."""
    client = get_gspread_client()
    if not client:
        return None
        
    try:
        sheet_url = get_secret_val("gcp_service_account", "spreadsheet_url")
        if not sheet_url:
            sheet_url = get_secret_val("GCP_SPREADSHEET_URL") # Try alternative env var name

        if sheet_url:
            sheet = client.open_by_url(sheet_url)
            return sheet.sheet1
    except Exception as e:
        print(f"Get Worksheet Error: {e}")
    return None

def _strip_prefix(name):
    """Strip leading numeric prefix (e.g. '01_' or '7_') from a study_id or filename."""
    name_str = _normalize_string(name)
    m = re.match(r'^\d+[_\s](.*)', name_str)
    return m.group(1).strip() if m else name_str

def _study_ids_match(id_a, id_b):
    """Compare two study_ids ignoring numeric prefix differences and encoding."""
    return _strip_prefix(id_a) == _strip_prefix(id_b)

def _find_in_df(df, study_id, reviewer):
    """Find a review row in a DataFrame using prefix-aware study_id matching."""
    if df.empty or 'study_id' not in df.columns or 'reviewer' not in df.columns:
        return None
    study_norm = _strip_prefix(study_id)
    reviewer_norm = _normalize_string(reviewer)
    for _, row in df.iterrows():
        if _normalize_string(row['reviewer']) == reviewer_norm and \
           _strip_prefix(row['study_id']) == study_norm:
            return row.where(pd.notna(row), None).to_dict()
    return None

def _reviewed_ids_from_df(df, reviewer_name):
    """Return a set of strip-prefix-normalised study_ids reviewed by reviewer_name."""
    if df.empty or 'reviewer' not in df.columns or 'study_id' not in df.columns:
        return set()
    reviewer_norm = _normalize_string(reviewer_name)
    df_reviewed = df[df['reviewer'].apply(lambda x: _normalize_string(x) == reviewer_norm)]
    return set(_strip_prefix(str(sid)) for sid in df_reviewed['study_id'].tolist())

def load_pdf_list(reviewer_name=None):
    """Returns a list of PDF files, marking those already reviewed by the user."""
    if not DATA_DIR.exists():
        st.warning(f"Data directory not found: {DATA_DIR}")
        return []
        
    pdfs = [f.name for f in DATA_DIR.glob("*.pdf")]
    
    # Build set of normalised study_ids already reviewed
    reviewed_norm_set = set()
    if reviewer_name:
        worksheet = get_worksheet()
        if worksheet:
            try:
                records = worksheet.get_all_records()
                for req in records:
                    if str(req.get('reviewer', '')) == str(reviewer_name):
                        reviewed_norm_set.add(_strip_prefix(str(req.get('study_id', ''))))
            except Exception:
                pass
        else:
            # Try writable CSV first, then the exported Sheet CSV
            for csv_path in [CSV_FILE, SHEET_CSV_FILE]:
                df = read_csv_safe(csv_path)
                norm_ids = _reviewed_ids_from_df(df, reviewer_name)
                reviewed_norm_set.update(norm_ids)
            
    # Return a list of tuples (actual_filename, display_name)
    display_list = []
    for pdf in sorted(pdfs):
        study_id = pdf.replace(".pdf", "")
        if _strip_prefix(study_id) in reviewed_norm_set:
            display_list.append((pdf, f"✅ {pdf}"))
        else:
            display_list.append((pdf, pdf))
            
    return display_list

def get_existing_review(study_id, reviewer):
    """Returns a dictionary of existing review data if it exists.
    
    Matches by stripping numeric prefixes so '1_Adedinsewo...' matches
    'Adedinsewo...' already saved in the Google Sheet or CSV.
    """
    worksheet = get_worksheet()
    if worksheet:
        try:
            records = worksheet.get_all_records()
            study_norm = _strip_prefix(study_id)
            reviewer_norm = _normalize_string(reviewer)
            for record in records:
                if _strip_prefix(record.get('study_id', '')) == study_norm and \
                   _normalize_string(record.get('reviewer', '')) == reviewer_norm:
                    return {k: (v if v != "" else None) for k, v in record.items()}
        except Exception:
            pass

    # Try writable CSV first, then the exported Sheet CSV
    for csv_path in [CSV_FILE, SHEET_CSV_FILE]:
        df = read_csv_safe(csv_path)
        record = _find_in_df(df, study_id, reviewer)
        if record is not None:
            return record
            
    return None

def save_data(data_dict):
    """Saves the review data to Google Sheets or a CSV file as fallback."""
    worksheet = get_worksheet()
    if worksheet:
        try:
            records = worksheet.get_all_records()
            # Find if it exists
            row_index = None
            study_norm = _strip_prefix(data_dict['study_id'])
            reviewer_norm = _normalize_string(data_dict['reviewer'])
            for i, record in enumerate(records):
                if _strip_prefix(record.get('study_id', '')) == study_norm and \
                   _normalize_string(record.get('reviewer', '')) == reviewer_norm:
                    # get_all_records is 0-indexed, but Google Sheets rows are 1-indexed, and row 1 is the header.
                    # So record index 0 is row 2.
                    row_index = i + 2
                    break
            
            headers = worksheet.row_values(1)
            # Create a list of values strictly ordered by the headers
            # If a header doesn't exist in data_dict, default to empty string
            row_values = [str(data_dict.get(h, "")) for h in headers]
            
            if row_index:
                from gspread.utils import rowcol_to_a1
                start_cell = rowcol_to_a1(row_index, 1)
                end_cell = rowcol_to_a1(row_index, len(headers))
                worksheet.update(range_name=f"{start_cell}:{end_cell}", values=[row_values])
                return "Updated existing entry (Google Sheets)."
            else:
                worksheet.append_row(row_values)
                return "Saved new entry (Google Sheets)."
                
        except Exception as e:
            return f"Failed saving to Google Sheets: {e}"
            
    # CSV Fallback
    df_new = pd.DataFrame([data_dict])
    if CSV_FILE.exists():
        df_existing = read_csv_safe(CSV_FILE)
        if not df_existing.empty and 'study_id' in df_existing.columns and 'reviewer' in df_existing.columns:
            study_norm = _strip_prefix(data_dict['study_id'])
            reviewer_norm = _normalize_string(data_dict['reviewer'])
            mask = ((df_existing['study_id'].apply(lambda x: _strip_prefix(str(x)))) == study_norm) & \
                   ((df_existing['reviewer'].apply(lambda x: _normalize_string(str(x)))) == reviewer_norm)
            if mask.any():
                index = df_existing[mask].index[0]
                for key, value in data_dict.items():
                    df_existing.loc[index, key] = value
                df_existing.to_csv(CSV_FILE, index=False)
                return "Updated existing entry (Local CSV Fallback)."
            else:
                df_combined = pd.concat([df_existing, df_new], ignore_index=True)
                df_combined.to_csv(CSV_FILE, index=False)
                return "Saved new entry (Local CSV Fallback)."
        else:
            # File exists but is empty or missing columns
            df_new.to_csv(CSV_FILE, index=False)
            return "Created/Overwrote file and saved entry (Local CSV Fallback)."
    else:
        df_new.to_csv(CSV_FILE, index=False)
        return "Created new file and saved entry (Local CSV Fallback)."

def delete_data(study_id, reviewer):
    """Deletes a review entry from Google Sheets or CSV."""
    worksheet = get_worksheet()
    if worksheet:
        try:
            records = worksheet.get_all_records()
            for i, record in enumerate(records):
                study_norm = _strip_prefix(str(study_id))
                reviewer_norm = _normalize_string(str(reviewer))
                if _strip_prefix(str(record.get('study_id', ''))) == study_norm and \
                   _normalize_string(str(record.get('reviewer', ''))) == reviewer_norm:
                    row_index = i + 2
                    worksheet.delete_rows(row_index)
                    return True
        except Exception:
            return False
            
    # CSV Fallback
    if CSV_FILE.exists():
        df = read_csv_safe(CSV_FILE)
        if not df.empty and 'study_id' in df.columns and 'reviewer' in df.columns:
            study_norm = _strip_prefix(str(study_id))
            reviewer_norm = _normalize_string(str(reviewer))
            mask = ((df['study_id'].apply(lambda x: _strip_prefix(str(x)))) == study_norm) & \
                   ((df['reviewer'].apply(lambda x: _normalize_string(str(x)))) == reviewer_norm)
            if mask.any():
                df = df[~mask]
                df.to_csv(CSV_FILE, index=False)
                return True
    return False

# --- Main App Execution ---
st.title("📄 Artificial Intelligence in Thoracic Transplantation: Current State and Future Directions")

# Load BibTeX database
bib_db = load_bibtex()

# 1. User & File Selection (Top Bar)
col_top1, col_top2 = st.columns([1, 1])

with col_top1:
    reviewer_name = st.text_input("Reviewer Name (Required)", placeholder="e.g. Johan")
    
    # --- Diagnostics ---
    with st.sidebar.expander("🛠️ Deployment Diagnostics"):
        st.write(f"**CSV Fallback Path:** `{CSV_FILE}`")
        
        # Check for secrets
        found_path = None
        mount_paths = [
            Path("/app/secrets/secrets.toml"), 
            Path("/srv/secrets/secrets.toml"),
            Path("/home/secrets/secrets.toml")
        ]
        for p in mount_paths:
            if p.exists():
                found_path = p
                break
        
        if found_path:
            st.success(f"✅ Found secrets at: `{found_path}`")
        else:
            st.error("❌ No `secrets.toml` found in standard mount paths.")
            st.info("Ensure Mount Path is `/home` and file is in `project-vol/secrets/secrets.toml`")
            
        # Check GS Client
        if get_gspread_client():
            st.success("✅ Google Sheets Client initialized.")
        else:
            st.error("❌ Google Sheets Client failed (check JSON format).")

with col_top2:
    pdf_files_info = load_pdf_list(reviewer_name)
    if pdf_files_info:
        # Pass the tuple list, format_func uses the second element for display
        selected_pdf_tuple = st.selectbox(
            "Select Article to Review", 
            options=pdf_files_info, 
            format_func=lambda x: x[1]
        )
        selected_pdf = selected_pdf_tuple[0]
    else:
        st.warning("No PDF files found in the data directory.")
        selected_pdf = None

st.divider()

# Only show the main UI if a reviewer name is entered and a PDF is selected
if reviewer_name and selected_pdf:
    
    if 'current_pdf' not in st.session_state or st.session_state.current_pdf != selected_pdf:
        st.session_state.current_pdf = selected_pdf
        st.session_state.start_time = pd.Timestamp.now()
        
    study_id = selected_pdf.replace(".pdf", "")
    existing_data = get_existing_review(study_id, reviewer_name)

    # Report prefill: only load report data if a button is clicked (Johan Nilsson only)
    report_prefill_key = f"use_report_{study_id}"
    report_path = find_matching_report(selected_pdf)
    # Use report data only when button was pressed and no existing saved data
    report_data = st.session_state.get(report_prefill_key, {})
    if existing_data:
        report_data = {}  # Never use report data when saved review exists

    # Merge: saved review takes priority, then report (if button was clicked), then empty
    effective_data = existing_data or report_data or None
    
    # Helper functions to get safe defaults
    def get_val(key, default):
        if effective_data and key in effective_data and effective_data[key] is not None:
            if effective_data[key] == "NR":
                if isinstance(default, (int, float)):
                    return default # Keep default number if NR was saved
            return effective_data[key]
        return default
        
    def get_index(key, options):
        val = get_val(key, None)
        if val in options:
            return options.index(val)
        return None
        
    def get_multiselect(key, options):
        val = get_val(key, "")
        if not val or val == "NR":
            return []
            
        # Migrate old labels or commas that break the split logic
        val = val.replace("Chronic Rejection/CLAD", "Chronic Lung Allograft Dysfunction (CLAD incl. BOS)")
        val = val.replace("Chronic Lung Allograft Dysfunction (CLAD, incl. BOS)", "Chronic Lung Allograft Dysfunction (CLAD incl. BOS)")
        
        saved_list = [v.strip() for v in val.split(', ')]
        return [opt for opt in options if opt in saved_list]

    def get_index_with_migration(key, options):
        val = get_val(key, None)
        if not val:
            return None
            
        # Migrate old multi-select values to single-select options (take first one if string)
        if isinstance(val, str):
            val = val.replace("Chronic Rejection/CLAD", "Chronic Lung Allograft Dysfunction (CLAD incl. BOS)")
            val = val.replace("Chronic Lung Allograft Dysfunction (CLAD, incl. BOS)", "Chronic Lung Allograft Dysfunction (CLAD incl. BOS)")
            val = val.split(',')[0].strip() # If multiple were saved, just grab the primary one

        if val in options:
            return options.index(val)
        return 0

    def get_num_val(key, val_type=int):
        val = get_val(key, None)
        if val == "NR" or val == "":
            return None
        if val is not None:
            try:
                return val_type(val)
            except Exception:
                return None
        return None

    # Split screen layout
    col_pdf, col_form = st.columns([6, 4]) # 60% PDF, 40% Form
    
    # Left column: PDF Viewer
    with col_pdf:
        st.subheader("Article Viewer")
        pdf_path = DATA_DIR / selected_pdf
        display_pdf(pdf_path)

    # Right column: Data Entry Form
    with col_form:
        st.subheader("Extraction Form")
        st.write(f"**Current Article:** `{selected_pdf}`")
        bibtex_meta = get_bibtex_metadata(selected_pdf, bib_db)

        if existing_data:
            st.info("ℹ️ You have previously reviewed this article. Form is pre-filled with your saved data.")
            # Check for metadata mismatch
            saved_meta = existing_data.get('study_metadata', '')
            if bibtex_meta and saved_meta and _normalize_string(saved_meta) != _normalize_string(bibtex_meta):
                st.warning("⚠️ The saved Title/Author/Journal/Year metadata differs from the library.bib file.")
                if st.button("Update metadata with correct values from BibTeX", key=f"update_meta_{study_id}"):
                    st.session_state[f"force_meta_{study_id}"] = bibtex_meta
                    st.rerun()

        elif report_data:
            st.success(f"📄 Pre-filled from report: `{report_path.name if report_path else 'report'}`")
        elif report_path and reviewer_name.strip().lower() == "johan nilsson":
            # Show prefill button only for Johan Nilsson when form is empty
            if st.button("📄 Pre-fill form from report file", key=f"btn_prefill_{study_id}"):
                parsed = report_to_review_dict(report_path)
                if parsed:
                    parsed['study_metadata'] = bibtex_meta
                    st.session_state[report_prefill_key] = parsed
                    st.rerun()
                else:
                    st.warning("Could not parse report file.")
        
        with st.container(height=1200, border=False):
            with st.form(key=f"extraction_form_{study_id}"):
                st.markdown("Please fill out the following sections based on the PRISMA, PICO, and CONVINCE guidelines.")

                # --- Section 1: Study Identification & Metadata ---
                with st.expander("Section 1: Study Identification & Metadata", expanded=False):

                    if f"force_meta_{study_id}" in st.session_state:
                        meta_default = st.session_state[f"force_meta_{study_id}"]
                    elif existing_data and existing_data.get('study_metadata'):
                        meta_default = existing_data.get('study_metadata')
                        # Convert old ' / ' format to newlines if it's on one line
                        if '\n' not in meta_default and ' / ' in meta_default:
                            parts = meta_default.split(' / ')
                            if len(parts) >= 3:
                                meta_default = f"{parts[0]}\n{parts[1]}\n{' / '.join(parts[2:])}"
                    elif report_data and report_data.get('study_metadata'):
                        meta_default = report_data.get('study_metadata')
                    else:
                        meta_default = bibtex_meta

                    study_meta = st.text_area("Study Title / Authors / Journal / Year", 
                                  value=meta_default, 
                                  help="Bibliographic data. Defaults to library.bib if found, else filename.",
                                  height=100)

                    col1_1, col1_2 = st.columns(2)
                    with col1_1:
                        country_opts = ["USA", "Europe", "Asia", "Australia", "Africa", "South America", "Multi-national", "Other", "Not Reported"]
                        country_origin = st.selectbox("Country of Data Origin", country_opts, index=get_index('country_origin', country_opts), help="TRIPOD: State the geographic region or setting where the study data were collected.")

                        organ_opts = ["Heart", "Lung", "Combined (Heart-Lung)", "Other", "Not Reported"]
                        organ_focus = st.selectbox("Organ Focus", organ_opts, index=get_index('organ_focus', organ_opts), help="TRIPOD: Clearly define the clinical setting and organ system the prediction model is intended for.")

                        fund_opts = ["Industry/Commercial", "Government/Public", "Foundation/Non-profit", "None", "Unclear", "Not Reported"]
                        funding_source = st.selectbox("Funding Source", fund_opts, index=get_index('funding_source', fund_opts), help="PRISMA: Describe sources of funding for the systematic review and for the included studies.")
                    with col1_2:
                        dataset_opts = ["Single Center", "Multi-center", "National Registry", "International Registry", "Other", "Not Reported"]
                        dataset_source = st.selectbox("Dataset Source", dataset_opts, index=get_index('dataset_source', dataset_opts), help="TRIPOD: Describe the study design or source of data (e.g., randomized trial, cohort, or registry data).")

                        dataset_name_opts = ["ISHLT Registry", "SRTR (Scientific Registry of Transplant Recipients)", "Eurotransplant Registry", "Scandiatransplant Registry", "UK Transplant Registry (NHSBT)", "Other Registry", "Not Applicable / Not Reported"]
                        dataset_name = st.selectbox("Dataset Name", dataset_name_opts, index=get_index('DatasetName', dataset_name_opts), help="TRIPOD: Specify the dataset or registry name to allow assessment of data source.")

                        dataset_other = ""
                        if dataset_name == "Other Registry":
                            dataset_other = st.text_input("Other Dataset/Registry Name", value=get_val('DatasetOther', ""), placeholder="Enter specific registry name...")

                        coi_opts = ["Yes (Declared COI)", "No (Declared no COI)", "Not Reported"]
                        coi_declared = st.selectbox("Conflict of Interest (COI) Declared", coi_opts, index=get_index('coi_declared', coi_opts), help="PRISMA: Declare any conflicts of interest of the study authors.")

                    col1_3, col1_4 = st.columns(2)
                    with col1_3:
                        study_start = st.number_input("Study Period Start (Year)", min_value=1950, max_value=2050, value=get_num_val('study_start_year', int), step=1, help="TRIPOD: Specify key study dates, including start of accrual.")
                    with col1_4:
                        study_end = st.number_input("Study Period End (Year)", min_value=1950, max_value=2050, value=get_num_val('study_end_year', int), step=1, help="TRIPOD: Specify key study dates, including end of accrual.")

                    section1_comments = st.text_area("Section 1 Comments", value=get_val('section1_comments', ""), help="Add any comments or quotes related to Study Identification & Metadata.")

                # --- Section 2: Population (PICO - P) ---
                with st.expander("Section 2: Population (PICO - P)", expanded=False):
                    target_opts = ["Transplant Candidates (Waitlist)", "Transplant Recipients (Post-op)", "Donors", "Organ (ex-vivo perfusion)", "Other", "Not Reported"]
                    target_pop = st.selectbox("Target Population", target_opts, index=get_index('target_population', target_opts), help="TRIPOD: Specify key elements of the study setting and population (e.g., clinical stage, disease status).")

                    col2_1, col2_2, col2_3 = st.columns(3)
                    with col2_1:
                        sample_size = st.number_input("Total Sample Size (N)", min_value=0, value=get_num_val('total_sample_size', int), step=1, help="TRIPOD: Report the number of participants and, where relevant, the number of events.")
                    with col2_2:
                        mean_age = st.number_input("Overall Mean Age", min_value=0.0, value=get_num_val('mean_age', float), step=0.1, help="TRIPOD: Give characteristics of the study participants, including basic demographics (Age).")
                    with col2_3:
                        female_sex_pct = st.number_input("Female Sex (%)", min_value=0.0, max_value=100.0, value=get_num_val('female_sex_pct', float), step=0.1, help="TRIPOD: Give characteristics of the study participants, including basic demographics (Sex).")

                    col_pop1, col_pop2 = st.columns(2)
                    with col_pop1:
                        yn_opts = ["Yes", "No", "Unclear", "Not Reported"]
                        race_ethnicity_reported = st.radio("Race/Ethnicity Reported", yn_opts, index=get_index('race_ethnicity_reported', yn_opts), horizontal=True, help="TRIPOD: Report demographic characteristics required to assess generalizability (e.g., race/ethnicity).")
                    with col_pop2:
                        comorbidities_included = st.radio("Comorbidities / Clinical History Included", yn_opts, index=get_index('comorbidities_included', yn_opts), horizontal=True, help="TRIPOD: Report the distribution of predictors (e.g., comorbidities, relevant clinical history).")

                    section2_comments = st.text_area("Section 2 Comments", value=get_val('section2_comments', ""), help="Add any comments or quotes related to Population.")

                # --- Section 3: Intervention & AI Methods (PICO - I & C / CONVINCE) ---
                with st.expander("Section 3: Intervention & AI Methods", expanded=False):
                    ml_opts = ["Yes", "No", "Other", "Not Reported"]
                    primary_ml = st.radio("Primary ML Component", ml_opts, index=get_index('primary_ml_component', ml_opts), horizontal=True, help="PRISMA-AI: State if AI/ML methodologies are the primary intervention being evaluated.")

                    design_opts = ["Retrospective Cohort", "Prospective Cohort", "Randomized Controlled Trial (RCT)", "Case-Control", "Case Report", "Other", "Not Reported"]
                    study_design = st.selectbox("Study Design", design_opts, index=get_index('study_design', design_opts), help="TRIPOD: Describe the study design (e.g., nested case-control, retrospective cohort).")

                    arch_opts = ["Convolutional Neural Network (CNN)", "Recurrent Neural Network (RNN/LSTM)", "Artificial Neural Networks (ANN, MLP, NN)", "Random Forest", "Decision Tree", "Gradient Boosting (XGBoost/LightGBM)", "Support Vector Machine (SVM)", "Ensemble", "Transformer/LLM", "Unsupervised Learning (Clustering)", "Other", "Not Reported"]
                    ai_architecture = st.selectbox("AI Model Architecture (Intervention 1)", arch_opts, index=get_index('ai_architecture', arch_opts), help="TRIPOD: Specify type of model and describe all statistical methods (e.g., CNN, Random Forest).")

                    algo_name = st.text_input("Algorithm Name", value=get_val('algorithm_name', ""), placeholder="e.g., DeepSurv", help="PROBAST: List the explicit name of the algorithm or model developed.")
                    if algo_name == "NR": algo_name = ""

                    modality_opts = ["Tabular (EMR/Clinical data)", "Waveforms/Signals (ECG)", "Imaging (CT/CXR/Echo)", "Pathology slides", "Donor metrics", "Multi-omics/Genetics", "Text / Clinical Notes (NLP)", "Other", "Not Reported"]
                    input_modalities = st.multiselect("Input Variables (Data Modality)", modality_opts, default=get_multiselect('input_modalities', modality_opts), help="TRIPOD: Clearly define all predictors (input modalities) and how they were measured.")

                    comp_opts = ["Human expert/Clinician", "Standard Clinical Guidelines", "Linear Risk Score (e.g., LAS, EuroSCORE)", "None", "Other", "Not Reported"]
                    comparator = st.selectbox("Comparator / Standard of Care (Intervention 2)", comp_opts, index=get_index('comparator', comp_opts), help="TRIPOD/PRISMA: State the reference standard or comparator (e.g., clinical guidelines, existing score).")

                    val_opts = ["Internal Split (Train/Test)", "Cross-Validation (k-fold)", "External Validation (Temporal)", "External Validation (Geographic/Different Hospital)", "Other", "Not Reported"]
                    validation_method = st.selectbox("Validation Method", val_opts, index=get_index('validation_method', val_opts), help="TRIPOD: Describe any validation, including internal (e.g., bootstrapping) or external methods.")

                    col3_1, col3_2 = st.columns(2)
                    with col3_1:
                        exp_opts = ["Yes (e.g., SHAP, LIME)", "No", "Not Reported"]
                        explainability_used = st.selectbox("Explainability / Interpretability Used", exp_opts, index=get_index('explainability_used', exp_opts), help="CONVINCE: Describe any explainability or interpretability methods used to justify prediction model outputs.")

                        fs_opts = ["Manual/Clinical expertise", "Automated (e.g., LASSO, Stepwise)", "Unsupervised (e.g., PCA)", "None/All features", "Not Reported"]
                        feature_selection = st.selectbox("Feature Selection Method", fs_opts, index=get_index('feature_selection', fs_opts), help="TRIPOD: Specify the predictor selection procedures (e.g., pre-selection, stepwise).")
                    with col3_2:
                        yn_opts = ["Yes", "No", "Not Reported"]
                        hyperparameter_tuning = st.radio("Hyperparameter Tuning Reported", yn_opts, index=get_index('hyperparameter_tuning', yn_opts), horizontal=True, help="CONVINCE: Report whether hyperparameters were optimized and how this was performed.")

                    section3_comments = st.text_area("Section 3 Comments", value=get_val('section3_comments', ""), help="Add any comments or quotes related to Intervention & AI Methods.")

                # --- Section 4: AI Quality & Reproducibility (CONVINCE Standards) ---
                with st.expander("Section 4: AI Quality & Reproducibility", expanded=False):
                    missing_opts = ["Complete Case Analysis (Excluded)", "Simple Imputation (Mean/Median)", "Multiple Imputation", "Algorithm handles natively", "Other", "Not Reported"]
                    missing_data = st.selectbox("Missing Data Handling", missing_opts, index=get_index('missing_data_handling', missing_opts), help="TRIPOD: Describe how missing data were handled (e.g., complete-case analysis, multiple imputation).")

                    imb_opts = ["Yes (e.g., SMOTE, weighted loss)", "No", "Not Applicable/Not Reported", "Other"]
                    class_imbalance = st.selectbox("Class Imbalance Addressed", imb_opts, index=get_index('class_imbalance', imb_opts), help="CONVINCE: Specify if techniques to handle class imbalance (e.g., SMOTE, weighting) were utilized.")

                    col4_a, col4_b = st.columns(2)
                    with col4_a:
                        code_opts = ["Yes", "Algorithm/Model weights available", "No", "Other", "Not Reported"]
                        code_avail = st.radio("Code Availability", code_opts, index=get_index('code_availability', code_opts), horizontal=True, help="PRISMA/PROBAST: Provide transparency on whether data and model code are available for reproducibility.")
                    with col4_b:
                        yn_opts = ["Yes", "No", "Not Reported"]
                        preprocessing_described = st.radio("Data Preprocessing / Normalization Described", yn_opts, index=get_index('preprocessing_described', yn_opts), horizontal=True, help="TRIPOD/CONVINCE: Detail data preprocessing (e.g., normalization, standardization) prior to modeling.")

                    col4_1, col4_2 = st.columns(2)
                    with col4_1:
                        train_size = st.number_input("Training Size (N)", min_value=0, value=get_num_val('training_size', int), step=1, help="TRIPOD: Provide the number of participants in the derivation/training set.")
                    with col4_2:
                        test_size = st.number_input("Test Size (N)", min_value=0, value=get_num_val('test_size', int), step=1, help="TRIPOD: Provide the number of participants in the validation/test set.")

                    section4_comments = st.text_area("Section 4 Comments", value=get_val('section4_comments', ""), help="Add any comments or quotes related to AI Quality & Reproducibility.")

                # --- Section 5: Outcomes & Performance (PICO - O) ---
                with st.expander("Section 5: Outcomes & Performance", expanded=False):
                    outcome_opts = ["1-year survival", "5-year survival", "30-day survival", "6-month survival", "Survival (duration not specified)", "Waitlist mortality", "Acute Rejection", "Chronic Lung Allograft Dysfunction (CLAD incl. BOS)", "Cardiac Allograft Vasculopathy (CAV)", "Primary Graft Dysfunction (PGD)", "Economy/Length of Stay", "Hospital/ICU Readmission", "Adverse Events/Complications", "Donor acceptance for transplantation", "Other", "Not Reported"]
                    target_outcome = st.selectbox("Target Clinical Outcome", outcome_opts, index=get_index_with_migration('target_outcome', outcome_opts), help="TRIPOD: Clearly define the primary outcome that is predicted by the model.")

                    col5_1, col5_2 = st.columns(2)
                    with col5_1:
                        model_auc = st.number_input("Model AUC / C-Statistic", min_value=0.0, max_value=1.0, value=get_num_val('model_auc', float), step=0.01, format="%.2f", help="TRIPOD: Report performance measures for discrimination (e.g., AUC/c-statistic).")
                        model_acc = st.number_input("Model Accuracy (%)", min_value=0.0, max_value=100.0, value=get_num_val('model_accuracy', float), step=0.1, format="%.1f", help="TRIPOD: Report accuracy as an overall performance measure, where applicable.")
                        model_ppv = st.number_input("PPV / Precision (%)", min_value=0.0, max_value=100.0, value=get_num_val('model_ppv', float), step=0.1, format="%.1f", help="TRIPOD: Report performance measures for clinical utility and predictive values (PPV/Precision).")
                    with col5_2:
                        model_sens = st.number_input("Sensitivity / Recall (%)", min_value=0.0, max_value=100.0, value=get_num_val('model_sensitivity', float), step=0.1, format="%.1f", help="TRIPOD: Report model sensitivity or recall to characterize true positive identification.")
                        model_spec = st.number_input("Specificity (%)", min_value=0.0, max_value=100.0, value=get_num_val('model_specificity', float), step=0.1, format="%.1f", help="TRIPOD: Report model specificity to characterize true negative identification.")
                        model_npv = st.number_input("NPV (%)", min_value=0.0, max_value=100.0, value=get_num_val('model_npv', float), step=0.1, format="%.1f", help="TRIPOD: Report Negative Predictive Value (NPV).")

                    model_f1 = st.number_input("F1-Score", min_value=0.0, max_value=1.0, value=get_num_val('model_f1', float), step=0.01, format="%.2f", help="TRIPOD/CONVINCE: Report combined metrics (e.g., F1-score) for imbalanced classification evaluation.")

                    col5_calib1, col5_calib2 = st.columns(2)
                    with col5_calib1:
                        calib_opts = ["Yes", "No", "Other", "Not Reported"]
                        calib_reported = st.radio("Calibration Reported", calib_opts, index=get_index('calibration_reported', calib_opts), horizontal=True, help="TRIPOD: Report performance measures for calibration (e.g., calibration plots, Hosmer-Lemeshow).")
                    with col5_calib2:
                        dca_opts = ["Yes", "No", "Not Reported"]
                        dca_reported = st.radio("Decision Curve Analysis (DCA) Reported", dca_opts, index=get_index('dca_reported', dca_opts), horizontal=True, help="TRIPOD: Report clinical utility evaluations such as Decision Curve Analysis (DCA).")

                    section5_comments = st.text_area("Section 5 Comments", value=get_val('section5_comments', ""), help="Add any comments or quotes related to Outcomes & Performance.")

                # --- Section 6: Quality Assessment (Risk of Bias) ---
                with st.expander("Section 6: Quality Assessment (Risk of Bias)", expanded=False):
                    bias_opts = ["Low Risk", "High Risk", "Unclear", "Not Reported"]

                    st.markdown("#### 1. Participants (Selection Bias)")
                    qa_participants_bias = st.selectbox("Participants Risk of Bias", bias_opts, index=get_index('qa_participants_bias', bias_opts))
                    qa_participants_quotes = st.text_area("Participants Quotes", value=get_val('qa_participants_quotes', ""))
                    qa_participants_comments = st.text_area("Participants Comments", value=get_val('qa_participants_comments', ""))

                    st.markdown("#### 2. Predictors (Input Variable Bias)")
                    qa_predictors_bias = st.selectbox("Predictors Risk of Bias", bias_opts, index=get_index('qa_predictors_bias', bias_opts))
                    qa_predictors_quotes = st.text_area("Predictors Quotes", value=get_val('qa_predictors_quotes', ""))
                    qa_predictors_comments = st.text_area("Predictors Comments", value=get_val('qa_predictors_comments', ""))

                    st.markdown("#### 3. Outcome (Definition Bias)")
                    qa_outcome_bias = st.selectbox("Outcome Risk of Bias", bias_opts, index=get_index('qa_outcome_bias', bias_opts))
                    qa_outcome_quotes = st.text_area("Outcome Quotes", value=get_val('qa_outcome_quotes', ""))
                    qa_outcome_comments = st.text_area("Outcome Comments", value=get_val('qa_outcome_comments', ""))

                    st.markdown("#### 4. Analysis (Modeling Bias)")
                    qa_analysis_bias = st.selectbox("Analysis Risk of Bias", bias_opts, index=get_index('qa_analysis_bias', bias_opts))
                    qa_analysis_quotes = st.text_area("Analysis Quotes", value=get_val('qa_analysis_quotes', ""))
                    qa_analysis_comments = st.text_area("Analysis Comments", value=get_val('qa_analysis_comments', ""))

                    st.markdown("#### 5. Applicability to Review Question")
                    applicability_opts = ["High Concern", "Low Concern", "Unclear", "Not Reported"]
                    qa_applicability = st.selectbox("Applicability", applicability_opts, index=get_index('qa_applicability', applicability_opts))
                    qa_applicability_quotes = st.text_area("Applicability Quotes", value=get_val('qa_applicability_quotes', ""))
                    qa_applicability_comments = st.text_area("Applicability Comments", value=get_val('qa_applicability_comments', ""))

                # Form submission
                col_submit, col_time = st.columns([5, 5])
                with col_submit:
                    submit_button = st.form_submit_button(label="Save PRISMA/CONVINCE Review Data")

                if submit_button:
                    end_time = pd.Timestamp.now()
                    duration_seconds = int((end_time - st.session_state.start_time).total_seconds())
                    minutes, seconds = divmod(duration_seconds, 60)
                    
                    with col_time:
                        st.markdown(f"<p style='margin-top: 10px; font-size: 16px;'>⏱️ <b>Review Duration:</b> {minutes} min {seconds} sec</p>", unsafe_allow_html=True)

                    review_data = {
                        "date_reviewed": end_time.strftime("%Y-%m-%d %H:%M:%S"),
                        "review_duration_seconds": duration_seconds,
                        "reviewer": reviewer_name,
                        "study_id": study_id,
                        "study_metadata": study_meta,
                        "country_origin": country_origin,
                        "organ_focus": organ_focus,
                        "funding_source": funding_source,
                        "dataset_source": dataset_source,
                        "DatasetName": dataset_name,
                        "DatasetOther": dataset_other if dataset_name == "Other Registry" else "",
                        "coi_declared": coi_declared,
                        "study_start_year": study_start if study_start is not None else "NR",
                        "study_end_year": study_end if study_end is not None else "NR",
                        "target_population": target_pop,
                        "total_sample_size": sample_size if sample_size is not None else "NR",
                        "mean_age": mean_age if mean_age is not None else "NR",
                        "female_sex_pct": female_sex_pct if female_sex_pct is not None else "NR",
                        "race_ethnicity_reported": race_ethnicity_reported,
                        "comorbidities_included": comorbidities_included,
                        "primary_ml_component": primary_ml,
                        "study_design": study_design,
                        "ai_architecture": ai_architecture,
                        "algorithm_name": algo_name if algo_name else "NR",
                        "input_modalities": ", ".join(input_modalities) if input_modalities else "NR",
                        "comparator": comparator,
                        "validation_method": validation_method,
                        "explainability_used": explainability_used,
                        "feature_selection": feature_selection,
                        "hyperparameter_tuning": hyperparameter_tuning,
                        "missing_data_handling": missing_data,
                        "class_imbalance": class_imbalance,
                        "code_availability": code_avail,
                        "preprocessing_described": preprocessing_described,
                        "training_size": train_size if train_size is not None else "NR",
                        "test_size": test_size if test_size is not None else "NR",
                        "target_outcome": target_outcome,
                        "model_auc": model_auc if model_auc is not None else "NR",
                        "model_accuracy": model_acc if model_acc is not None else "NR",
                        "model_ppv": model_ppv if model_ppv is not None else "NR",
                        "model_sensitivity": model_sens if model_sens is not None else "NR",
                        "model_specificity": model_spec if model_spec is not None else "NR",
                        "model_npv": model_npv if model_npv is not None else "NR",
                        "model_f1": model_f1 if model_f1 is not None else "NR",
                        "calibration_reported": calib_reported,
                        "dca_reported": dca_reported,
                        "section1_comments": section1_comments,
                        "section2_comments": section2_comments,
                        "section3_comments": section3_comments,
                        "section4_comments": section4_comments,
                        "section5_comments": section5_comments,
                        "qa_participants_bias": qa_participants_bias,
                        "qa_participants_quotes": qa_participants_quotes,
                        "qa_participants_comments": qa_participants_comments,
                        "qa_predictors_bias": qa_predictors_bias,
                        "qa_predictors_quotes": qa_predictors_quotes,
                        "qa_predictors_comments": qa_predictors_comments,
                        "qa_outcome_bias": qa_outcome_bias,
                        "qa_outcome_quotes": qa_outcome_quotes,
                        "qa_outcome_comments": qa_outcome_comments,
                        "qa_analysis_bias": qa_analysis_bias,
                        "qa_analysis_quotes": qa_analysis_quotes,
                        "qa_analysis_comments": qa_analysis_comments,
                        "qa_applicability": qa_applicability,
                        "qa_applicability_quotes": qa_applicability_quotes,
                        "qa_applicability_comments": qa_applicability_comments
                    }

                    # Cleanup: ensure any remaining `None` inputs are converted securely to "NR" or ""
                    for k, v in review_data.items():
                        if v is None:
                            if 'comments' in k or 'quotes' in k or k == 'DatasetOther':
                                review_data[k] = ""
                            else:
                                review_data[k] = "NR"
                                
                    status_message = save_data(review_data)
                    st.success(f"✅ Data saved successfully! ({status_message})")
                    st.balloons()

            # Delete flow
            if existing_data:
                st.markdown("---")
                with st.expander("🗑️ Danger Zone: Delete Existing Review"):
                    st.warning("Deleting this review will permanently remove the data for this article by this reviewer.")
                    confirm_delete = st.checkbox("I confirm that I want to delete this review.")
                    if st.button("Delete Review", disabled=not confirm_delete):
                        if delete_data(study_id, reviewer_name):
                            st.success("Review deleted successfully.")
                            st.rerun()
                        else:
                            st.error("Failed to delete review.")

else:
    if not reviewer_name:
        st.info("👈 Please enter your name to start reviewing.")

# --- Footer ---
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: grey; font-size: 0.8em;'>
        Copyright © 2026 Artificial Intelligence and Bioinformatics in Cardiothoracic Sciences (AIBCTS), Lund University, Faculty of Medicine, Department of Translational Medicine<br>
        This project is licensed under the Apache License 2.0. See the LICENSE file for details.<br>
        <i>Patent Protection: The Apache 2.0 license includes explicit patent grants and a patent retaliation clause, providing protection for patentability while allowing open-source distribution.</i>
    </div>
    """,
    unsafe_allow_html=True
)
