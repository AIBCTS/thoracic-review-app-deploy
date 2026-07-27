import os
import sys
import csv
import re
from pathlib import Path
from datetime import datetime
import bibtexparser

# Add workspace directory to path
BASE_DIR = Path(__file__).parent.parent.resolve() if Path(__file__).parent.name == "scripts" else Path(__file__).parent.resolve()
sys.path.insert(0, str(BASE_DIR))

import app

REPORTS_DIR = BASE_DIR / "reports"
DATA_DIR = BASE_DIR / "data"
BIB_FILE = DATA_DIR / "library.bib"
CSV_FILE = BASE_DIR / "results" / "AI_Thoracic_Review_Database - Sheet1.csv"

def load_bib():
    if not BIB_FILE.exists():
        return None
    with open(BIB_FILE, "r", encoding="utf-8") as f:
        return bibtexparser.load(f)

def build_prefix_to_pdf_stem_map():
    """Build a mapping from numeric prefix (e.g. 10) to PDF filename stem."""
    pdf_map = {}
    if DATA_DIR.exists():
        for p in DATA_DIR.glob("*.pdf"):
            m = re.match(r'^(\d+)', p.name)
            if m:
                pdf_map[int(m.group(1))] = p.stem
    return pdf_map

def get_bib_metadata_improved(report_filename, bib_database):
    """Matches a report file to its entry in library.bib via prefix number or file attribute."""
    if not bib_database:
        return report_filename
        
    m = re.match(r'^(\d+)', report_filename)
    prefix_num = int(m.group(1)) if m else None

    # 1. Match by prefix number in file attribute or entry ID
    if prefix_num is not None:
        for entry in bib_database.entries:
            file_attr = entry.get('file', '')
            file_num = re.match(r'^(\d+)', file_attr)
            if file_num and int(file_num.group(1)) == prefix_num:
                title = entry.get('title', 'Unknown Title').replace('{', '').replace('}', '')
                authors = entry.get('author', 'Unknown Authors').replace('\n', ' ')
                author_list = authors.split(' and ')
                if len(author_list) > 3:
                    authors = f"{author_list[0]} et al."
                journal = entry.get('journal', 'Unknown Journal')
                year = entry.get('year', 'Unknown Year')
                return f"{title}\n{authors}\n{journal} / {year}"

    # 2. Fallback to app.get_bibtex_metadata
    return app.get_bibtex_metadata(report_filename, bib_database)

def build_review_row(report_file, bib_db, pdf_stem_map):
    report_path = REPORTS_DIR / report_file
    
    # 1. Parse report using app.py parsing logic
    parsed_fields = app.report_to_review_dict(report_path)
    
    # 2. Get study_id (matching PDF stem for Streamlit app compatibility)
    m = re.match(r'^(\d+)', report_file)
    prefix_num = int(m.group(1)) if m else None
    study_id = pdf_stem_map.get(prefix_num, report_file.replace(".pdf", ""))
    
    # 3. Get study_metadata
    study_metadata = get_bib_metadata_improved(report_file, bib_db)
    
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    row = {
        "date_reviewed": now_str,
        "reviewer": "llm-reviewer",
        "study_id": study_id,
        "study_metadata": study_metadata,
        "country_origin": parsed_fields.get("country_origin", "Not Reported"),
        "organ_focus": parsed_fields.get("organ_focus", "Not Reported"),
        "dataset_source": parsed_fields.get("dataset_source", "Not Reported"),
        "study_start_year": parsed_fields.get("study_start_year", "NR"),
        "study_end_year": parsed_fields.get("study_end_year", "NR"),
        "target_population": parsed_fields.get("target_population", "Not Reported"),
        "total_sample_size": parsed_fields.get("total_sample_size", "NR"),
        "mean_age": parsed_fields.get("mean_age", "NR"),
        "female_sex_pct": parsed_fields.get("female_sex_pct", "NR"),
        "primary_ml_component": parsed_fields.get("primary_ml_component", "Not Reported"),
        "study_design": parsed_fields.get("study_design", "Not Reported"),
        "ai_architecture": parsed_fields.get("ai_architecture", "Not Reported"),
        "algorithm_name": parsed_fields.get("algorithm_name", "NR"),
        "input_modalities": parsed_fields.get("input_modalities", "NR"),
        "comparator": parsed_fields.get("comparator", "Not Reported"),
        "validation_method": parsed_fields.get("validation_method", "Not Reported"),
        "missing_data_handling": parsed_fields.get("missing_data_handling", "Not Reported"),
        "code_availability": parsed_fields.get("code_availability", "Not Reported"),
        "training_size": parsed_fields.get("training_size", "NR"),
        "test_size": parsed_fields.get("test_size", "NR"),
        "target_outcome": parsed_fields.get("target_outcome", "Not Reported"),
        "model_auc": parsed_fields.get("model_auc", "NR"),
        "model_accuracy": parsed_fields.get("model_accuracy", "NR"),
        "model_sensitivity": parsed_fields.get("model_sensitivity", "NR"),
        "model_specificity": parsed_fields.get("model_specificity", "NR"),
        "calibration_reported": parsed_fields.get("calibration_reported", "Not Reported"),
        "DatasetName": parsed_fields.get("DatasetName", "Not Applicable / Not Reported"),
        "DatasetOther": parsed_fields.get("DatasetOther", ""),
        "section1_comments": parsed_fields.get("section1_comments", ""),
        "section2_comments": parsed_fields.get("section2_comments", ""),
        "section3_comments": parsed_fields.get("section3_comments", ""),
        "section4_comments": parsed_fields.get("section4_comments", ""),
        "section5_comments": parsed_fields.get("section5_comments", ""),
        "qa_participants_bias": parsed_fields.get("qa_participants_bias", "Not Reported"),
        "qa_participants_quotes": parsed_fields.get("qa_participants_quotes", ""),
        "qa_participants_comments": parsed_fields.get("qa_participants_comments", ""),
        "qa_predictors_bias": parsed_fields.get("qa_predictors_bias", "Not Reported"),
        "qa_predictors_quotes": parsed_fields.get("qa_predictors_quotes", ""),
        "qa_predictors_comments": parsed_fields.get("qa_predictors_comments", ""),
        "qa_outcome_bias": parsed_fields.get("qa_outcome_bias", "Not Reported"),
        "qa_outcome_quotes": parsed_fields.get("qa_outcome_quotes", ""),
        "qa_outcome_comments": parsed_fields.get("qa_outcome_comments", ""),
        "qa_analysis_bias": parsed_fields.get("qa_analysis_bias", "Not Reported"),
        "qa_analysis_quotes": parsed_fields.get("qa_analysis_quotes", ""),
        "qa_analysis_comments": parsed_fields.get("qa_analysis_comments", ""),
        "qa_applicability": parsed_fields.get("qa_applicability", "Not Reported"),
        "qa_applicability_quotes": parsed_fields.get("qa_applicability_quotes", ""),
        "qa_applicability_comments": parsed_fields.get("qa_applicability_comments", ""),
        "funding_source": parsed_fields.get("funding_source", "Not Reported"),
        "coi_declared": parsed_fields.get("coi_declared", "Not Reported"),
        "race_ethnicity_reported": parsed_fields.get("race_ethnicity_reported", "Not Reported"),
        "comorbidities_included": parsed_fields.get("comorbidities_included", "Not Reported"),
        "explainability_used": parsed_fields.get("explainability_used", "Not Reported"),
        "feature_selection": parsed_fields.get("feature_selection", "Not Reported"),
        "hyperparameter_tuning": parsed_fields.get("hyperparameter_tuning", "Not Reported"),
        "class_imbalance": parsed_fields.get("class_imbalance", "Not Reported"),
        "preprocessing_described": parsed_fields.get("preprocessing_described", "Not Reported"),
        "model_ppv": parsed_fields.get("model_ppv", "NR"),
        "model_npv": parsed_fields.get("model_npv", "NR"),
        "model_f1": parsed_fields.get("model_f1", "NR"),
        "dca_reported": parsed_fields.get("dca_reported", "Not Reported"),
        "review_duration_seconds": 60,
        "model_auc_lower_ci": parsed_fields.get("model_auc_lower_ci", "NR"),
        "model_auc_upper_ci": parsed_fields.get("model_auc_upper_ci", "NR"),
        "model_auc_se": parsed_fields.get("model_auc_se", "NR"),
        "linear_model_auc": parsed_fields.get("linear_model_auc", "NR"),
        "linear_model_auc_lower_ci": parsed_fields.get("linear_model_auc_lower_ci", "NR"),
        "linear_model_auc_upper_ci": parsed_fields.get("linear_model_auc_upper_ci", "NR"),
        "linear_model_auc_se": parsed_fields.get("linear_model_auc_se", "NR")
    }

    # Standardize coi_declared specifically
    if row["coi_declared"] == "Yes":
        row["coi_declared"] = "Yes (Declared COI)"
    elif row["coi_declared"] == "No":
        row["coi_declared"] = "No (Declared no COI)"
    elif row["coi_declared"] in ["NR", "Not reported", "not reported"]:
        row["coi_declared"] = "Not Reported"

    # Fill any remaining Nones with NR or empty string
    for k, v in row.items():
        if v is None:
            if "comments" in k or "quotes" in k or k == "DatasetOther":
                row[k] = ""
            else:
                row[k] = "NR"

    return row

def main(dry_run=True):
    bib_db = load_bib()
    pdf_stem_map = build_prefix_to_pdf_stem_map()
    report_files = sorted([f for f in os.listdir(REPORTS_DIR) if not f.startswith('.')])
    
    extracted_rows = []
    for rfile in report_files:
        row = build_review_row(rfile, bib_db, pdf_stem_map)
        extracted_rows.append(row)
        
    print(f"Successfully processed {len(extracted_rows)} report files.")
    
    if dry_run:
        print("\n=== DRY RUN MODE: SAMPLE EXTRACTED ROWS ===")
        for i, row in enumerate(extracted_rows[:2]):
            print(f"\n--- Row #{i+1}: {row['study_id']} ---")
            for k, v in row.items():
                if v:
                    print(f"  {k}: {repr(v)}")
        print("\nNo files were updated in Dry Run mode.")
        return extracted_rows
    else:
        headers = list(extracted_rows[0].keys())
        existing_rows = []
        if CSV_FILE.exists():
            with open(CSV_FILE, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames if reader.fieldnames else headers
                for r in reader:
                    if r.get("reviewer") != "llm-reviewer":
                        existing_rows.append(r)

        all_rows = existing_rows + extracted_rows
        
        with open(CSV_FILE, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(all_rows)

        print(f"\nSuccessfully wrote {len(all_rows)} total rows (including {len(extracted_rows)} for reviewer 'llm-reviewer') to {CSV_FILE}.")
        return extracted_rows

if __name__ == "__main__":
    dry_run_arg = "--write" not in sys.argv
    main(dry_run=dry_run_arg)
