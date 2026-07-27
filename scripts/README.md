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
