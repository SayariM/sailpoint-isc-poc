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

## Permanent storage

Accounts, saved progress and every application live in one database:

- **Default:** a local SQLite file, `state/app.db`. Good for running on your own machine.
  Data left over from older versions (`state/*.json`, `state/users.db`) is imported
  automatically the first time.
- **Hosted Postgres (recommended for Streamlit Cloud):** set `DATABASE_URL` and the same
  code stores everything there, so nothing is lost when the app restarts or redeploys.

Setting up a hosted database (Supabase or Neon, both have free tiers):

1. Create a project, then copy its **connection string** (Postgres URI), e.g.
   `postgresql://user:password@host:5432/dbname`. For Supabase use the *pooler* /
   "Transaction" string if the direct host does not resolve from Streamlit Cloud.
2. Add it to the Streamlit secrets (or `.env` to try it locally):
   ```toml
   DATABASE_URL = "postgresql://user:password@host:5432/dbname"
   ```
3. Tables are created automatically on first start. To copy your existing local data
   into it, run `python migrate_to_db.py` once with `DATABASE_URL` set. It is safe to
   repeat and never overwrites rows that already exist.

If `DATABASE_URL` is wrong or the database is down, the app says so instead of
silently falling back to temporary storage. The database holds client information, so
use a provider and region your organisation approves, and keep the connection string
in secrets only. **Back up this intake** still gives each user a personal copy.

## Accounts and access

Users sign in with a **User ID and password** (create one on the **Create account** tab).
Passwords are stored as salted scrypt hashes in the database, and five wrong
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
- Without `DATABASE_URL`, hosts with a temporary disk (such as Streamlit Community Cloud)
  lose accounts and intakes whenever the app restarts. See **Permanent storage** above.

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
- Set `DATABASE_URL` to keep data across restarts. Without it, data is stored in a local
  file. **Back up this intake** and **Restore from a saved file** give each user a
  personal copy either way.
