# Workflow & Database Optimization Summary

This document summarizes the structural, schema, and data workflow enhancements completed for the Thoracic AI Review Application dataset and app deployment.

---

## 1. Linear Model Comparator Addition (Section 5)

- Added **Linear Risk Score Comparator** evaluation fields in `app.py` Section 5 UI and CSV database:
  - `model_auc_se`: Model AUC Standard Error
  - `linear_model_auc`: Linear Model AUC / C-Statistic
  - `linear_model_auc_lower_ci`: Linear Model AUC Lower 95% CI
  - `linear_model_auc_upper_ci`: Linear Model AUC Upper 95% CI
  - `linear_model_auc_se`: Linear Model AUC Standard Error

---

## 2. Master Column Header Schema Alignment (73 Columns)

- Aligned all CSV databases, `app.py` form payloads, and batch extraction scripts to strictly follow the **65 Master Column Headers** from `AI_Thoracic_Review_Database - Sheet1.csv` plus **8 newly created variables** (total 73 columns):
  - Preserved original master column names: `female_sex_pct` and `race_ethnicity_reported`.
  - Appended new variables at columns 66–73: `review_duration_seconds`, `model_auc_lower_ci`, `model_auc_upper_ci`, `model_auc_se`, `linear_model_auc`, `linear_model_auc_lower_ci`, `linear_model_auc_upper_ci`, `linear_model_auc_se`.

---

## 3. Choice Option Normalization & Verification

- **Categorical Options**: Standardized option strings across all 77 report files in `reports/` and CSV rows to match `app.py` and `chatGPT_prompt_2026.md` protocol definitions (e.g. `SRTR (Scientific Registry of Transplant Recipients)`, `Convolutional Neural Network (CNN)`, `Donors`, `Organ (ex-vivo perfusion)`).
- **Section 6 (PROBAST)**: Standardized Quality Assessment dropdown options to short strings (`Low Risk`, `High Risk`, `Unclear`, `Low Concern`, `High Concern`) matching Streamlit UI selectboxes.

---

## 4. Multi-Reviewer Verification Results

- **Francesca Lunardi**: Verified **100% exact match** across all 57 studies between `AI_Thoracic_Review_Database - Sheet1.csv`, `manual_review_results.csv`, and `extraction_raw_all_reviewers.csv`.
- **Johan Nilsson**: Verified **100% exact match** across all 58 studies between `manual_review_results.csv` and `extraction_raw_all_reviewers.csv`.

---

## 5. File Reorganization & Git Archiving

- **Active Master Database**: Consolidated master database promoted to `results/AI_Thoracic_Review_Database - Sheet1.csv` (221 rows, 73 columns).
- **App & Batch Script Update**: `app.py` and `scripts/batch_extract_llm_reviewer.py` updated to read and write directly to `results/AI_Thoracic_Review_Database - Sheet1.csv`.
- **Archiving**: Historical database files moved to `archive/` and `_archive/`.
- **Git Ignore**: Updated `.gitignore` to exclude `archive/`, `_archive/`, `.venv/`, and temporary build artifacts.

---

## 6. Study #13 Naming & Character Accent Normalization

- Renamed PDF file `data/13_Dueñas-Jurado et al...pdf` $\rightarrow$ `data/13_Duenas-Jurado et al...pdf`.
- Renamed report file `reports/13_FirstAuthor_Dueñas-Jurado` $\rightarrow$ `reports/13_FirstAuthor_Duenas-Jurado`.
- Updated master CSV `study_id` and BibTeX entry `#13` file path to `13_Duenas-Jurado...` without special accents for 100% cross-platform compatibility.

---

## 7. Two-Digit Study 01-77 Standardization

- Standardized all single-digit PDF filenames in `data/` (`01_` through `09_`) to 2-digit leading zero format.
- Updated `file = {...}` references in `data/library.bib` for entries 1 to 9.
- Updated `study_id` in `results/AI_Thoracic_Review_Database - Sheet1.csv` and `results/AI_Thoracic_Review_Database_GoogleSheets_Ready.csv` to 2-digit format (`01_` through `77_`), ensuring clean numerical sorting in Excel/Google Sheets.

---

## 8. Google Sheets Pre-fill & String Normalization (`app.py`)

- Updated `load_pdf_list()` and `get_existing_review()` to use case- and whitespace-insensitive string normalization (`_normalize_string`) and prefix/suffix stripping (`_strip_prefix`).
- Re-established Google Sheets online connection as the primary live database when available, with automatic fallback to local master CSV files when offline.

---

## 9. CI/CD & Docker Build Optimization

- Added `.dockerignore` to exclude `.git/`, `.venv/`, `archive/`, and large binaries from Docker context.
- Updated `.github/workflows/deploy.yml` with dynamic repository name downcasing (`REPO_LC=${GITHUB_REPOSITORY,,}`), resolving GitHub Container Registry (GHCR) case-sensitivity requirements.

---

## 10. Google Sheets Compliant Export

- Generated `results/AI_Thoracic_Review_Database_GoogleSheets_Ready.csv`:
  - Fixed double-encoded UTF-8 / Mojibake artifacts (`‚Äú` $\rightarrow$ `“`, `‚Äù` $\rightarrow$ `”`, `â€“` $\rightarrow$ `–`).
  - Included full Row 1 headers (73 columns) and 221 complete rows ready for direct cell copy/paste into Google Sheets.
