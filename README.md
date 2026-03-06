# Artificial Intelligence in Thoracic Transplantation Review App

A Streamlit-based web application for systematic reviews of AI in thoracic transplantation, following PRISMA, PICO, and CONVINCE standards.

## Features
- **Integrated PDF Viewer**: Side-by-side review and extraction.
- **Automated Metadata**: Pre-fills fields using BibTeX integration (`library.bib`).
- **Cloud Storage**: Syncs data to Google Sheets for multi-user collaboration.
- **Robustness**: Local CSV fallback if cloud connection is unavailable.

## Deployment to SciLifeLab Serve

This application is designed to be deployed via Docker on [SciLifeLab Serve](https://serve.scilifelab.se).

### 1. Prerequisites
- A Google Cloud Service Account and a Google Sheet.
- The Service Account must have "Editor" access to the Sheet.

### 2. Configuration (Secrets)
On SciLifeLab Serve (or local Streamlit), you must provide the following secrets in the Dashboard/`secrets.toml`:

```toml
[gcp_service_account]
type = "service_account"
project_id = "your-project-id"
private_key_id = "your-key-id"
private_key = "-----BEGIN PRIVATE KEY-----\n..."
client_email = "your-service-account@..."
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/..."
universe_domain = "googleapis.com"
spreadsheet_url = "https://docs.google.com/spreadsheets/d/your-id/edit"
```

### 3. Local Setup
1. Clone this repository.
2. Install dependencies: `pip install -r requirements.txt`.
3. Add your `secrets.toml` to `.streamlit/`.
4. Run: `streamlit run review_app.py`.

## License
Copyright © 2026 Artificial Intelligence and Bioinformatics in Cardiothoracic Sciences (AIBCTS), Lund University.
Licensed under the Apache License 2.0.
