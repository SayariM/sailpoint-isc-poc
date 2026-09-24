---
title: ISC Source Onboarding
colorFrom: red
colorTo: gray
sdk: streamlit
app_file: app.py
pinned: false
short_description: Structured intake for SailPoint ISC source onboarding
---

# ISC Source Onboarding

Interviews an application owner in plain language and produces a complete,
citation-backed onboarding specification for a SailPoint Identity Security Cloud
source.

The question set lives in `onboarding_schema.json`, so coverage is deterministic:
every applicable requirement is asked, and anything unanswered is reported as an
open question rather than silently missed. Questions branch on the answers — a
database-backed application gets the JDBC questions, an API-backed one gets the
Web Services questions.

## Running locally

```bash
pip install -r requirements.txt
cp .env.example .env        # add your Groq API key
streamlit run app.py
```

Drop reference documents into `docs/` (PDF, Markdown, JSON, XML). The index
builds automatically the first time the docs explainer is used.

## Notes

- Embeddings run locally; only retrieved excerpts are sent to the language model.
- Server storage is temporary. Use **Back up this intake** to keep a copy, and
  **Restore from a saved file** to resume.
