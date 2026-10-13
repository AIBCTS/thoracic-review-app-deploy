# Data-extraction application: machine learning in heart and lung transplantation

A local web application for structured full-text data extraction, used in the systematic review and meta-analysis *Machine learning and the donor–recipient dual-risk problem in heart and lung transplantation* (PROSPERO CRD420251174511). The reviewer reads the article next to the extraction form, can pre-fill the form from a structured study summary, and saves one row per study and reviewer.

The analysis code and the locked extraction database are in a separate repository: https://github.com/AIBCTS/ml-thoracic-transplant-metaanalysis

## Run

Requires [uv](https://docs.astral.sh/uv/) (Python 3.11 or later).

```bash
uv run streamlit run app.py
```

The app opens in the browser at http://localhost:8501. Enter a reviewer name, choose an article, and save. Nothing is sent over the network.

## Contents

| Folder / file | Content |
|---|---|
| `app.py` | The application |
| `data/` | The 46 included studies that are open access under a Creative Commons licence (PDF), their BibTeX records (`library.bib`), and the licence of each file (`PDF_LICENCES.csv`). Articles under publisher copyright are not included; they can be added to `data/` with a matching `library.bib` entry |
| `reports/` | Structured study summaries used to pre-fill the form, one per included PDF |
| `results/review_results.csv` | Saved reviews. Empty at start (column headers only) |

## Licence

Copyright © 2026 Artificial Intelligence and Bioinformatics in Cardiothoracic Sciences (AIBCTS), Lund University. All rights reserved; see `LICENSE`. You may view the code and run it unmodified to inspect the workflow; any other use requires written permission. The article PDFs remain under their own Creative Commons licences (`data/PDF_LICENCES.csv`).

## Contact

Questions and permission requests: open an issue at https://github.com/AIBCTS/thoracic-review-app-deploy/issues
