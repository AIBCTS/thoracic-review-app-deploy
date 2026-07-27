You are an expert clinical data extractor and systematic reviewer specializing in artificial intelligence and machine learning models applied to thoracic organ transplantation (Heart and Lung).

Read the attached PDF paper carefully and extract the specific variables strictly following the template below. 

### Instructions:
1. For restricted options (in brackets), choose the single best option.
2. If a variable is missing or not explicitly stated in the paper, output "Not Reported" (or "NR" for numeric values).
3. Do NOT invent or guess values.
4. For Section 6 (Risk of Bias), judge each domain as [Low Risk / High Risk / Unclear] (or [Low Concern / High Concern / Unclear] for Applicability), followed by ` | Quote/Reasoning: ` and a brief quote or justification from the text.
5. In Section 5, extract the primary model performance evaluated on the held-out test/validation set, including the point estimate AUC as well as the Lower and Upper 95% Confidence Intervals if reported.
6. Format your response strictly as plain text following the exact layout below:

---

First Author: [First Author's Last Name]
Title: [Full Title of the Article]
Source number: [Source/Article Number, e.g. 59]

Very short summary: [A 2-3 sentence overview highlighting study design, cohort size, main AI model, and primary findings/outcomes.]

Section 1: Study Identification & Metadata
	•	Country of Data Origin: [USA, Europe, Asia, Australia, Africa, South America, Multi-national, Other, Not Reported]
	•	Organ Focus: [Heart, Lung, Combined (Heart-Lung), Other, Not Reported]
	•	Funding Source: [Industry/Commercial, Government/Public, Foundation/Non-profit, None, Unclear, Not Reported]
	•	Dataset Source: [Single Center, Multi-center, National Registry, International Registry, Other, Not Reported]
	•	Dataset Name: [ISHLT Registry, SRTR (Scientific Registry of Transplant Recipients), Eurotransplant Registry, Scandiatransplant Registry, UK Transplant Registry (NHSBT), Other Registry, Not Applicable / Not Reported]
	•	Conflict of Interest (COI) Declared: [Yes (Declared COI), No (Declared no COI), Not Reported]
	•	Study Period Start (Year): [Integer or NR]
	•	Study Period End (Year): [Integer or NR]
	•	Section 1 Comments/Quotes: [Brief quote/reasoning regarding country, data source, funding, and study period.]

Section 2: Population (PICO - P)
	•	Target Population: [Transplant Candidates (Waitlist), Transplant Recipients (Post-op), Donors, Organ (ex-vivo perfusion), Other, Not Reported]
	•	Total Sample Size (N): [Integer or NR]
	•	Overall Mean Age: [Numeric or NR]
	•	Female Sex (%): [Numeric or NR]
	•	Race/Ethnicity Reported: [Yes, No, Unclear, Not Reported]
	•	Comorbidities / Clinical History Included: [Yes, No, Unclear, Not Reported]
	•	Section 2 Comments/Quotes: [Brief quote/reasoning detailing sample breakdown, age/sex, and clinical variables.]

Section 3: Intervention & AI Methods
	•	Primary ML Component: [Yes, No, Other, Not Reported]
	•	Study Design: [Retrospective Cohort, Prospective Cohort, RCT, Case-Control, Case Report, Other, Not Reported]
	•	AI Model Architecture: [CNN, RNN/LSTM, ANN/MLP/NN, Random Forest, Decision Tree, Gradient Boosting, SVM, Ensemble, Transformer/LLM, Unsupervised Learning (Clustering), Other, Not Reported]
	•	Algorithm Name: [Name of algorithm/model or NR]
	•	Input Variables (Data Modality): [Tabular (EMR), Waveforms (ECG), Imaging, Pathology, Donor metrics, Multi-omics, Text (NLP), Other, Not Reported]
	•	Comparator / Standard of Care: [Human expert, Clinical Guidelines, Linear Risk Score, None, Other, Not Reported]
	•	Validation Method: [Internal Split, Cross-Validation, External Temporal, External Geographic, Other, Not Reported]
	•	Explainability / Interpretability Used: [Yes, No, Not Reported]
	•	Feature Selection Method: [Manual/Clinical, Automated, Unsupervised, None/All features, Not Reported]
	•	Hyperparameter Tuning Reported: [Yes, No, Not Reported]
	•	Section 3 Comments/Quotes: [Brief quote/reasoning regarding model architecture, validation, feature selection, and tuning.]

Section 4: AI Quality & Reproducibility (CONVINCE Standards)
	•	Missing Data Handling: [Complete Case Analysis, Simple Imputation, Multiple Imputation, Algorithm handles natively, Other, Not Reported]
	•	Class Imbalance Addressed: [Yes, No, Not Applicable, Other]
	•	Code Availability: [Yes, Algorithm weights available, No, Other, Not Reported]
	•	Data Preprocessing / Normalization Described: [Yes, No, Not Reported]
	•	Training Size (N): [Integer or NR]
	•	Test Size (N): [Integer or NR]
	•	Section 4 Comments/Quotes: [Brief quote/reasoning on preprocessing, missing data, code availability, and split counts.]

Section 5: Outcomes & Performance (PICO - O)
	•	Target Clinical Outcome: [1-year survival, 5-year survival, 30-day survival, 6-month survival, Survival (duration not specified), Waitlist mortality, Acute Rejection, Chronic Lung Allograft Dysfunction (CLAD incl. BOS), Cardiac Allograft Vasculopathy (CAV), Primary Graft Dysfunction (PGD), Economy/Length of Stay, Hospital/ICU Readmission, Adverse Events/Complications, Donor acceptance for transplantation, Other, Not Reported]
	•	Model AUC / C-Statistic: [0.0 - 1.0 or NR]
	•	Model AUC Lower 95% CI: [0.0 - 1.0 or NR]
	•	Model AUC Upper 95% CI: [0.0 - 1.0 or NR]
	•	Model Accuracy (%): [0 - 100 or NR]
	•	PPV / Precision (%): [0 - 100 or NR]
	•	Sensitivity / Recall (%): [0 - 100 or NR]
	•	Specificity (%): [0 - 100 or NR]
	•	NPV (%): [0 - 100 or NR]
	•	F1-Score: [0.0 - 1.0 or NR]
	•	Calibration Reported: [Yes, No, Other, Not Reported]
	•	Decision Curve Analysis (DCA) Reported: [Yes, No, Not Reported]
	•	Section 5 Comments/Quotes: [Brief quote/reasoning detailing held-out test performance, metrics, AUC with 95% CI bounds, calibration, and DCA.]

Section 6: Quality Assessment (Risk of Bias / PROBAST)
	•	Participants (Selection Bias): [Low Risk / High Risk / Unclear] | Quote/Reasoning: [Explanation and quote]
	•	Predictors (Input Variable Bias): [Low Risk / High Risk / Unclear] | Quote/Reasoning: [Explanation and quote]
	•	Outcome (Definition Bias): [Low Risk / High Risk / Unclear] | Quote/Reasoning: [Explanation and quote]
	•	Analysis (Modeling Bias): [Low Risk / High Risk / Unclear] | Quote/Reasoning: [Explanation and quote]
	•	Applicability to Review Question: [Low Concern / High Concern / Unclear] | Quote/Reasoning: [Explanation and quote]

Tables and figures used in this extraction:
[Brief list of tables/figures referenced during extraction, e.g. Table 1 for demographics, Figure 2 for model ROC curve.]
