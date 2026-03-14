import streamlit as st
import pandas as pd
import os
import base64
from pathlib import Path
import bibtexparser
import gspread
from google.oauth2.service_account import Credentials

# --- Configuration ---
st.set_page_config(layout="wide", page_title="Artificial Intelligence in Thoracic Transplantation: Current State and Future Directions")

# Define paths
BASE_DIR = Path(__file__).parent.resolve()
DATA_DIR = BASE_DIR / "data"
BIB_FILE = DATA_DIR / "library.bib"

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
        
    filename_clean = pdf_filename.replace(".pdf", "")
    parts = filename_clean.split(" - ")
    
    # Simple heuristic: try to match the title or author from the filename
    match_title = parts[2].strip().lower() if len(parts) >= 3 else filename_clean.lower()
    match_author = parts[0].replace(" et al.", "").strip().lower() if len(parts) >= 1 else ""
    
    for entry in bib_database.entries:
        entry_title = entry.get('title', '').replace('{', '').replace('}', '').lower()
        entry_author = entry.get('author', '').lower()
        
        # If the filename title is in the bibtex title, or vice versa, or author matches roughly
        if (len(match_title) > 10 and (match_title in entry_title or entry_title[:20] in match_title)) or \
           (match_author and match_author in entry_author):
               
            title = entry.get('title', 'Unknown Title').replace('{', '').replace('}', '')
            authors = entry.get('author', 'Unknown Authors').replace('\n', ' ')
            # Shorten authors if too long
            author_list = authors.split(' and ')
            if len(author_list) > 3:
                authors = f"{author_list[0]} et al."
            journal = entry.get('journal', 'Unknown Journal')
            year = entry.get('year', 'Unknown Year')
            return f"{title}\n{authors}\n{journal} / {year}"
            
    return pdf_filename

def display_pdf(file_path):
    """Displays a PDF within a Streamlit app using an iframe."""
    try:
        with open(file_path, "rb") as f:
            base64_pdf = base64.b64encode(f.read()).decode('utf-8')
        
        # Displaying the PDF via HTML iframe
        pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="800" type="application/pdf"></iframe>'
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
    
    # 3. Try Mounted File (e.g. at /app/secrets/secrets.toml or /home/secrets/secrets.toml)
    # This is for SciLifeLab Serve persistent storage
    mount_paths = [
        Path("/app/secrets/secrets.toml"), 
        Path("/srv/secrets/secrets.toml"),
        Path("/home/secrets/secrets.toml")
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

def load_pdf_list(reviewer_name=None):
    """Returns a list of PDF files, marking those already reviewed by the user."""
    if not DATA_DIR.exists():
        st.warning(f"Data directory not found: {DATA_DIR}")
        return []
        
    pdfs = [f.name for f in DATA_DIR.glob("*.pdf")]
    
    # Check which ones are already reviewed
    reviewed_set = set()
    if reviewer_name:
        worksheet = get_worksheet()
        if worksheet:
            # GS fallback
            try:
                # Get all records to check existing
                records = worksheet.get_all_records()
                for req in records:
                    if str(req.get('reviewer', '')) == str(reviewer_name):
                        reviewed_set.add(str(req.get('study_id', '')))
            except Exception:
                pass
        elif CSV_FILE.exists():
            df = read_csv_safe(CSV_FILE)
            if not df.empty and 'reviewer' in df.columns and 'study_id' in df.columns:
                reviewed_df = df[df['reviewer'] == reviewer_name]
                reviewed_set = set(reviewed_df['study_id'].tolist())
            
    # Return a list of tuples (actual_filename, display_name)
    display_list = []
    for pdf in sorted(pdfs):
        study_id = pdf.replace(".pdf", "")
        if study_id in reviewed_set:
            display_list.append((pdf, f"✅ {pdf}"))
        else:
            display_list.append((pdf, pdf))
            
    return display_list

def get_existing_review(study_id, reviewer):
    """Returns a dictionary of existing review data if it exists."""
    worksheet = get_worksheet()
    if worksheet:
        try:
            records = worksheet.get_all_records()
            for record in records:
                if str(record.get('study_id', '')) == str(study_id) and str(record.get('reviewer', '')) == str(reviewer):
                    # Convert empty strings to None to match Pandas behavior
                    return {k: (v if v != "" else None) for k, v in record.items()}
        except Exception:
            pass
            
    # CSV Fallback
    if CSV_FILE.exists():
        df = read_csv_safe(CSV_FILE)
        if not df.empty and 'study_id' in df.columns and 'reviewer' in df.columns:
            mask = (df['study_id'] == study_id) & (df['reviewer'] == reviewer)
            if mask.any():
                # Convert the matched row to a dictionary, replacing NaN with None
                row = df[mask].iloc[0]
                record = row.where(pd.notna(row), None).to_dict()
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
            for i, record in enumerate(records):
                if str(record.get('study_id', '')) == str(data_dict['study_id']) and str(record.get('reviewer', '')) == str(data_dict['reviewer']):
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
            mask = (df_existing['study_id'] == data_dict['study_id']) & (df_existing['reviewer'] == data_dict['reviewer'])
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
                if str(record.get('study_id', '')) == str(study_id) and str(record.get('reviewer', '')) == str(reviewer):
                    row_index = i + 2
                    worksheet.delete_rows(row_index)
                    return True
        except Exception:
            return False
            
    # CSV Fallback
    if CSV_FILE.exists():
        df = read_csv_safe(CSV_FILE)
        if not df.empty and 'study_id' in df.columns and 'reviewer' in df.columns:
            mask = (df['study_id'] == study_id) & (df['reviewer'] == reviewer)
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
    
    study_id = selected_pdf.replace(".pdf", "")
    existing_data = get_existing_review(study_id, reviewer_name)
    
    # Helper functions to get safe defaults
    def get_val(key, default):
        if existing_data and key in existing_data and existing_data[key] is not None:
            if existing_data[key] == "NR":
                if isinstance(default, (int, float)):
                    return default # Keep default number if NR was saved
            return existing_data[key]
        return default
        
    def get_index(key, options):
        val = get_val(key, None)
        if val in options:
            return options.index(val)
        return 0
        
    def get_multiselect(key, options):
        val = get_val(key, "")
        if not val or val == "NR":
            return []
        saved_list = [v.strip() for v in val.split(', ')]
        return [opt for opt in options if opt in saved_list]

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
        if existing_data:
            st.info("ℹ️ You have previously reviewed this article. Form is pre-filled with your saved data.")
        
        with st.form(key=f"extraction_form_{study_id}"):
            st.markdown("Please fill out the following sections based on the PRISMA, PICO, and CONVINCE guidelines.")
            
            # --- Section 1: Study Identification & Metadata ---
            with st.expander("Section 1: Study Identification & Metadata", expanded=True):
                # Bibtex fallback
                bibtex_meta = get_bibtex_metadata(selected_pdf, bib_db)
                
                if existing_data and existing_data.get('study_metadata'):
                    meta_default = existing_data.get('study_metadata')
                    # Convert old ' / ' format to newlines if it's on one line
                    if '\n' not in meta_default and ' / ' in meta_default:
                        parts = meta_default.split(' / ')
                        if len(parts) >= 3:
                            meta_default = f"{parts[0]}\n{parts[1]}\n{' / '.join(parts[2:])}"
                else:
                    meta_default = bibtex_meta
                
                study_meta = st.text_area("Study Title / Authors / Journal / Year", 
                              value=meta_default, 
                              help="Bibliographic data. Defaults to library.bib if found, else filename.",
                              height=100)
                
                col1_1, col1_2 = st.columns(2)
                with col1_1:
                    country_opts = ["USA", "Europe", "Asia", "Australia", "Africa", "South America", "Multi-national", "Other"]
                    country_origin = st.selectbox("Country of Data Origin", country_opts, index=get_index('country_origin', country_opts), help="Geographic origin of the training data.")
                    
                    organ_opts = ["Heart", "Lung", "Combined (Heart-Lung)"]
                    organ_focus = st.selectbox("Organ Focus", organ_opts, index=get_index('organ_focus', organ_opts), help="The primary organ system the AI classifier targets.")
                with col1_2:
                    dataset_opts = ["Single Center", "Multi-center", "National Registry", "International Registry"]
                    dataset_source = st.selectbox("Dataset Source", dataset_opts, index=get_index('dataset_source', dataset_opts), help="The nature of the data registry (e.g., national, international, specific hospital).")
                    
                    dataset_name_opts = ["ISHLT Registry", "SRTR (Scientific Registry of Transplant Recipients)", "Eurotransplant Registry", "Scandiatransplant Registry", "UK Transplant Registry (NHSBT)", "Other Registry", "Not Applicable / Not Reported"]
                    dataset_name = st.selectbox("Dataset Name", dataset_name_opts, index=get_index('DatasetName', dataset_name_opts), help="The specific name of the registry or database used.")
                    
                    dataset_other = ""
                    if dataset_name == "Other Registry":
                        dataset_other = st.text_input("Other Dataset/Registry Name", value=get_val('DatasetOther', ""), placeholder="Enter specific registry name...")
                        
                col1_3, col1_4 = st.columns(2)
                with col1_3:
                    study_start = st.number_input("Study Period Start (Year)", min_value=1950, max_value=2050, value=int(get_val('study_start_year', 2010)), step=1, help="The year during which patient data collection began.")
                with col1_4:
                    study_end = st.number_input("Study Period End (Year)", min_value=1950, max_value=2050, value=int(get_val('study_end_year', 2024)), step=1, help="The year during which patient data collection ended.")

            # --- Section 2: Population (PICO - P) ---
            with st.expander("Section 2: Population (PICO - P)", expanded=False):
                target_opts = ["Transplant Candidates (Waitlist)", "Transplant Recipients (Post-op)", "Donors", "Organ (ex-vivo perfusion)"]
                target_pop = st.selectbox("Target Population", target_opts, index=get_index('target_population', target_opts), help="The clinical stage of the patients included.")
                
                col2_1, col2_2, col2_3 = st.columns(3)
                with col2_1:
                    sample_size = st.number_input("Total Sample Size (N)", min_value=0, value=int(get_val('total_sample_size', 0)), step=1, help="Total number of subjects analyzed in the study.")
                with col2_2:
                    mean_age = st.number_input("Overall Mean Age", min_value=0.0, value=float(get_val('mean_age', 0.0)), step=0.1, help="The mean or median age of the total cohort.")
                with col2_3:
                    female_sex_pct = st.number_input("Female Sex (%)", min_value=0.0, max_value=100.0, value=float(get_val('female_sex_pct', 0.0)), step=0.1, help="Percentage of female subjects in the total cohort.")

            # --- Section 3: Intervention & AI Methods (PICO - I & C / CONVINCE) ---
            with st.expander("Section 3: Intervention & AI Methods", expanded=False):
                ml_opts = ["Yes", "No"]
                primary_ml = st.radio("Primary ML Component", ml_opts, index=get_index('primary_ml_component', ml_opts), horizontal=True, help="Is Machine Learning/AI the primary analysis component of the paper?")
                
                design_opts = ["Retrospective Cohort", "Prospective Cohort", "Randomized Controlled Trial (RCT)", "Other"]
                study_design = st.selectbox("Study Design", design_opts, index=get_index('study_design', design_opts), help="The methodological design of the study.")
                
                arch_opts = ["Convolutional Neural Network (CNN)", "Recurrent Neural Network (RNN/LSTM)", "Artificial Neural Networks (ANN, MLP, NN)", "Random Forest", "Decision Tree", "Gradient Boosting (XGBoost/LightGBM)", "Support Vector Machine (SVM)", "Ensemble", "Transformer/LLM", "Other"]
                ai_architecture = st.selectbox("AI Model Architecture (Intervention 1)", arch_opts, index=get_index('ai_architecture', arch_opts), help="The specific non-linear algorithm used.")
                
                algo_name = st.text_input("Algorithm Name", value=get_val('algorithm_name', ""), placeholder="e.g., DeepSurv", help="The specific name of the algorithm if provided.")
                if algo_name == "NR": algo_name = ""
                
                modality_opts = ["Tabular (EMR/Clinical data)", "Waveforms/Signals (ECG)", "Imaging (CT/CXR/Echo)", "Pathology slides", "Donor metrics", "Multi-omics/Genetics"]
                input_modalities = st.multiselect("Input Variables (Data Modality)", modality_opts, default=get_multiselect('input_modalities', modality_opts), help="The types of data fed into the AI model.")
                
                comp_opts = ["Human expert/Clinician", "Standard Clinical Guidelines", "Linear Risk Score (e.g., LAS, EuroSCORE)", "None", "Other"]
                comparator = st.selectbox("Comparator / Standard of Care (Intervention 2)", comp_opts, index=get_index('comparator', comp_opts), help="What the AI is being compared against.")
                
                val_opts = ["Internal Split (Train/Test)", "Cross-Validation (k-fold)", "External Validation (Temporal)", "External Validation (Geographic/Different Hospital)", "Other"]
                validation_method = st.selectbox("Validation Method", val_opts, index=get_index('validation_method', val_opts), help="How the model's performance was evaluated to prevent overfitting.")

            # --- Section 4: AI Quality & Reproducibility (CONVINCE Standards) ---
            with st.expander("Section 4: AI Quality & Reproducibility", expanded=False):
                missing_opts = ["Complete Case Analysis (Excluded)", "Simple Imputation (Mean/Median)", "Multiple Imputation", "Algorithm handles natively", "Not Reported", "Other"]
                missing_data = st.selectbox("Missing Data Handling", missing_opts, index=get_index('missing_data_handling', missing_opts), help="How the study dealt with missing variables.")
                
                code_opts = ["Yes", "No", "Not Reported"]
                code_avail = st.radio("Code Availability", code_opts, index=get_index('code_availability', code_opts), horizontal=True, help="Is the AI training code open source or available upon request?")
                
                col4_1, col4_2 = st.columns(2)
                with col4_1:
                    train_size = st.number_input("Training Size (N)", min_value=0, value=int(get_val('training_size', 0)), step=1, help="Number of patients/samples used strictly for training.")
                with col4_2:
                    test_size = st.number_input("Test Size (N)", min_value=0, value=int(get_val('test_size', 0)), step=1, help="Number of patients/samples in the completely held-out test set.")

            # --- Section 5: Outcomes & Performance (PICO - O) ---
            with st.expander("Section 5: Outcomes & Performance", expanded=False):
                outcome_opts = ["1-year survival", "5-year survival", "Survival (duration not specified)", "Waitlist mortality", "Acute Rejection", "Chronic Lung Allograft Dysfunction (CLAD, incl. BOS)", "Cardiac Allograft Vasculopathy (CAV)", "Primary Graft Dysfunction (PGD)", "Economy/Length of Stay"]
                target_outcome = st.multiselect("Target Clinical Outcome", outcome_opts, default=get_multiselect('target_outcome', outcome_opts), help="What the AI is predicting or classifying.")
                
                col5_1, col5_2 = st.columns(2)
                with col5_1:
                    model_auc = st.number_input("Model AUC / C-Statistic", min_value=0.0, max_value=1.0, value=float(get_val('model_auc', 0.0)), step=0.01, format="%.2f", help="Area Under the Curve on the TEST set. The gold standard for discrimination.")
                    model_acc = st.number_input("Model Accuracy (%)", min_value=0.0, max_value=100.0, value=float(get_val('model_accuracy', 0.0)), step=0.1, format="%.1f", help="Overall percentage of correct predictions on the TEST set.")
                with col5_2:
                    model_sens = st.number_input("Sensitivity / Recall (%)", min_value=0.0, max_value=100.0, value=float(get_val('model_sensitivity', 0.0)), step=0.1, format="%.1f", help="True positive rate on the TEST set.")
                    model_spec = st.number_input("Specificity (%)", min_value=0.0, max_value=100.0, value=float(get_val('model_specificity', 0.0)), step=0.1, format="%.1f", help="True negative rate on the TEST set.")
                
                calib_opts = ["Yes", "No"]
                calib_reported = st.radio("Calibration Reported", calib_opts, index=get_index('calibration_reported', calib_opts), horizontal=True, help="Did the study report calibration plots or use the Hosmer-Lemeshow test?")

            # Form submission
            submit_button = st.form_submit_button(label="Save PRISMA/CONVINCE Review Data")
            
            if submit_button:
                review_data = {
                    "date_reviewed": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "reviewer": reviewer_name,
                    "study_id": study_id,
                    "study_metadata": study_meta,
                    "country_origin": country_origin,
                    "organ_focus": organ_focus,
                    "dataset_source": dataset_source,
                    "DatasetName": dataset_name,
                    "DatasetOther": dataset_other if dataset_name == "Other Registry" else "",
                    "study_start_year": study_start,
                    "study_end_year": study_end,
                    "target_population": target_pop,
                    "total_sample_size": sample_size if sample_size > 0 else "NR",
                    "mean_age": mean_age if mean_age > 0 else "NR",
                    "female_sex_pct": female_sex_pct if female_sex_pct > 0 else "NR",
                    "primary_ml_component": primary_ml,
                    "study_design": study_design,
                    "ai_architecture": ai_architecture,
                    "algorithm_name": algo_name if algo_name else "NR",
                    "input_modalities": ", ".join(input_modalities) if input_modalities else "NR",
                    "comparator": comparator,
                    "validation_method": validation_method,
                    "missing_data_handling": missing_data,
                    "code_availability": code_avail,
                    "training_size": train_size if train_size > 0 else "NR",
                    "test_size": test_size if test_size > 0 else "NR",
                    "target_outcome": ", ".join(target_outcome) if target_outcome else "NR",
                    "model_auc": model_auc if model_auc > 0 else "NR",
                    "model_accuracy": model_acc if model_acc > 0 else "NR",
                    "model_sensitivity": model_sens if model_sens > 0 else "NR",
                    "model_specificity": model_spec if model_spec > 0 else "NR",
                    "calibration_reported": calib_reported
                }
                
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
