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

## Accounts and access

Users sign in with a **User ID and password** (create one on the **Create account** tab).
Passwords are stored as salted scrypt hashes in `state/users.db`, and five wrong
attempts lock a User ID for five minutes.

| Role | Sees | Can |
|------|------|-----|
| Application owner | Owner questions | Create applications, share them, fill them in |
| ISC developer | Design-decision questions | Fill in applications shared with them |
| Admin | Everything | Assign owners, change roles, reset passwords |

- Each application has an owner. Users only see their own applications and those shared
  with them (**Owner & sharing** in the sidebar). Applications created before accounts
  existed have no owner and are visible to admins only, who can assign one.
- The first account created becomes the admin, unless you configure one. To set a default
  admin, put `ADMIN_USER_ID` and `ADMIN_PASSWORD` in `.env` or the platform secrets. That
  account is created or corrected on every start, so its password is changed by editing
  `ADMIN_PASSWORD` (not inside the app). `ADMIN_USER_IDS` (comma-separated) instead lets
  those User IDs become admins when they register themselves. If the admin sign-in is
  refused on a hosted app, check the app logs for a line starting `[auth]`.
- On Streamlit Community Cloud the disk is temporary, so accounts and intakes are lost
  when the app restarts. Use **Back up this intake** regularly, and move to a hosted
  database before real use.

## Saving and resuming

You can stop at any point and pick up later:

- Answers are saved when you click **Save**, **Next/Back**, **Save progress** (sidebar),
  switch sections from the sidebar, or sign out. Applying an Ask Agent suggestion saves it
  immediately. The sidebar shows when the application was last saved.
- When you sign back in, the app reopens the application you were last working on, at the
  section you left, and the form shows your saved answers.
- Closing the browser tab does not save what you typed since the last save, so click
  **Save progress** before you leave.

## Ask Agent

The panel beside the form is an ISC-specific agent. Ask it about any question, or
say "fill question 3" (or click **Take help from Agent to know more** on a question). It reads the
question, drafts an answer from what you told it, the other answers on the form and
the ISC docs, and shows it as a suggestion. **Apply** puts it on the form, where you
can edit it, then **Save** and submit from **Review & export**.

## Notes

- Embeddings run locally; only retrieved excerpts are sent to the language model.
- Server storage is temporary. Use **Back up this intake** to keep a copy, and
  **Restore from a saved file** to resume.
