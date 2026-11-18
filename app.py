"""Streamlit UI for the ISC source onboarding interview."""

from __future__ import annotations

import base64
import html
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import streamlit as st
from dotenv import load_dotenv

import assistant
import auth
import excel_export
import interview

LOGO = Path(__file__).parent / "assets" / "logo.png"
load_dotenv()

st.set_page_config(
    page_title="KPMG | ISC Source Onboarding",
    page_icon=str(LOGO) if LOGO.exists() else ":material/hub:",
    layout="wide",
    initial_sidebar_state="expanded",
)

SCHEMA = interview.load_schema()
SECTIONS = {s["id"]: s for s in SCHEMA["sections"]}
BY_ID = {s["id"]: s for s in SCHEMA["slots"]}
REVIEW = "__review__"

SECRET_NAMES: list[str] = []
SECRET_ERROR: str | None = None
try:  # hosted platforms supply the key as a secret rather than a .env file
    SECRET_NAMES = list(st.secrets.keys())
    if "GROQ_API_KEY" in st.secrets:
        os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]
    if "GROQ_CHAT_MODEL" in st.secrets:
        os.environ["GROQ_CHAT_MODEL"] = st.secrets["GROQ_CHAT_MODEL"]
    for name in ("GEMINI_API_KEY", "GEMINI_CHAT_MODEL", "ADMIN_USER_IDS"):
        if name in st.secrets:
            os.environ[name] = st.secrets[name]
except Exception as exc:
    SECRET_ERROR = f"{type(exc).__name__}: {exc}"

if LOGO.exists():
    BRAND_HTML = (
        '<img alt="KPMG" src="data:image/png;base64,'
        + base64.b64encode(LOGO.read_bytes()).decode()
        + '">'
    )
else:
    BRAND_HTML = '<span class="wordmark">KPMG</span>'

st.html("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
  :root {
    --kpmg-blue: #00338D; --kpmg-mid: #005EB8; --kpmg-light: #0091DA;
    --kpmg-tint: #EAF1FB; --kpmg-line: #D3E0F3; --kpmg-ink: #0B1F3A;
  }
  html, body, [class*="st-"]:not([data-testid="stIconMaterial"]), .stApp {
    font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
  }
  .stApp { background: linear-gradient(180deg, #F3F7FD 0%, #FFFFFF 380px); }
  .block-container { padding-top: 1.2rem; max-width: 1480px; }
  header[data-testid="stHeader"] { background: transparent; }
  div[data-testid="stColumn"]:has(.chat-anchor) {
    position: sticky; top: 3.5rem; align-self: flex-start;
  }
  h1, h2, h3 { letter-spacing: -0.01em; color: var(--kpmg-blue); }

  /* sidebar */
  div[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #E4EEFB 0%, #F3F7FD 100%);
    border-right: 1px solid var(--kpmg-line);
  }
  div[data-testid="stSidebarUserContent"] { padding-top: 1.2rem; }
  div[data-testid="stSidebar"] h3 {
    border-bottom: 3px solid var(--kpmg-light); padding-bottom: 0.35rem;
  }
  div[data-testid="stSidebar"] div[role="radiogroup"] label {
    padding: 0.32rem 0.6rem; border-radius: 8px; border-left: 3px solid transparent;
    transition: background 0.15s, border-color 0.15s;
  }
  div[data-testid="stSidebar"] div[role="radiogroup"] label:hover { background: rgba(0, 94, 184, 0.09); }
  div[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {
    background: #fff; border-left-color: var(--kpmg-mid); font-weight: 600;
    box-shadow: 0 1px 3px rgba(0, 51, 141, 0.12);
  }

  /* cards */
  div[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 14px; border-color: var(--kpmg-line); background: #fff;
    box-shadow: 0 1px 3px rgba(0, 51, 141, 0.06), 0 6px 18px rgba(0, 51, 141, 0.04);
    transition: box-shadow 0.2s, border-color 0.2s;
  }
  div[data-testid="stVerticalBlockBorderWrapper"]:hover {
    border-color: #9DBBE6; box-shadow: 0 2px 6px rgba(0, 51, 141, 0.08), 0 10px 26px rgba(0, 51, 141, 0.08);
  }

  /* inputs */
  div[data-baseweb="textarea"], div[data-baseweb="input"], div[data-baseweb="select"] > div {
    background: #fff !important; border-radius: 10px !important;
  }
  div[data-baseweb="textarea"], div[data-baseweb="input"] { border: 1px solid #B9CDEB !important; }
  div[data-baseweb="textarea"]:focus-within, div[data-baseweb="input"]:focus-within {
    border-color: var(--kpmg-mid) !important; box-shadow: 0 0 0 3px rgba(0, 94, 184, 0.15);
  }
  textarea { background: #fff !important; }

  /* hero */
  .hero {
    position: relative; overflow: hidden;
    background: linear-gradient(110deg, var(--kpmg-blue) 0%, var(--kpmg-mid) 62%, var(--kpmg-light) 100%);
    border-radius: 16px; padding: 1.2rem 1.7rem; margin-bottom: 1.4rem;
    display: flex; align-items: center; gap: 1.4rem;
    box-shadow: 0 6px 20px rgba(0, 51, 141, 0.25);
  }
  .hero::before, .hero::after {
    content: ""; position: absolute; border-radius: 50%; background: rgba(255, 255, 255, 0.07);
  }
  .hero::before { width: 260px; height: 260px; right: -60px; top: -120px; }
  .hero::after { width: 160px; height: 160px; right: 150px; bottom: -100px; background: rgba(255, 255, 255, 0.05); }
  .hero > * { position: relative; z-index: 1; }
  .hero .brand {
    display: flex; align-items: center; padding-right: 1.4rem;
    border-right: 1px solid rgba(255, 255, 255, 0.45);
  }
  .hero .brand img { height: 64px; width: 64px; border-radius: 14px; display: block; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25); }
  .hero .brand .wordmark {
    font-family: Georgia, "Times New Roman", serif; font-style: italic; font-weight: 700;
    font-size: 1.9rem; letter-spacing: 0.02em; color: #fff;
  }
  .hero .heading { color: #fff; font-size: 1.3rem; font-weight: 700; line-height: 1.2; }
  .hero .sub { color: rgba(255, 255, 255, 0.85); font-size: 0.88rem; margin-top: 0.2rem; }

  /* page header */
  .pagehead { display: flex; align-items: center; flex-wrap: wrap; gap: 0.6rem 0.9rem; margin: 0.2rem 0 0.4rem 0; }
  .pagehead h1 { margin: 0; padding: 0; font-size: 2.1rem; font-weight: 700; color: var(--kpmg-ink); }
  .chip {
    display: inline-flex; align-items: center; gap: 0.35rem; font-size: 0.78rem; font-weight: 600;
    padding: 0.22rem 0.75rem; border-radius: 999px; background: var(--kpmg-tint); color: var(--kpmg-mid);
    border: 1px solid var(--kpmg-line);
  }
  .chip.done { background: #E3F4EA; color: #17673A; border-color: #BFE3CD; }
  h3.sectiontitle {
    display: flex; align-items: center; gap: 0.6rem; margin: 0.8rem 0 0.2rem 0; font-size: 1.45rem;
  }
  h3.sectiontitle::before {
    content: ""; width: 5px; height: 1.5rem; border-radius: 3px;
    background: linear-gradient(180deg, var(--kpmg-light), var(--kpmg-blue));
  }

  /* questions */
  .qnum {
    display: inline-block; font-size: 0.72rem; font-weight: 700; letter-spacing: 0.06em;
    color: #fff; background: linear-gradient(135deg, var(--kpmg-blue), var(--kpmg-mid)); border-radius: 999px;
    padding: 0.15rem 0.7rem; text-transform: uppercase; margin-bottom: 0.35rem;
  }
  .qtext { font-size: 1.05rem; font-weight: 600; line-height: 1.45; margin: 0 0 0.15rem 0; color: var(--kpmg-ink); }
  .req { color: var(--kpmg-light); margin-left: 0.25rem; }
  .sectionblurb { color: #4A5F7D; font-size: 0.95rem; margin: 0 0 1.2rem 0; }
  .navrow { border-top: 1px solid var(--kpmg-line); margin-top: 1.4rem; padding-top: 0.2rem; }

  /* buttons and widgets */
  div[data-testid="stButton"] button, div[data-testid="stDownloadButton"] button {
    border-radius: 10px; font-weight: 600; transition: transform 0.12s, box-shadow 0.12s, border-color 0.12s;
  }
  div[data-testid="stButton"] button p { white-space: normal; line-height: 1.25; }
  div[data-testid="stButton"] button:hover, div[data-testid="stDownloadButton"] button:hover {
    transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0, 51, 141, 0.18); border-color: var(--kpmg-mid);
  }
  div[data-testid="stButton"] button[kind="primary"],
  div[data-testid="stDownloadButton"] button[kind="primary"] {
    background: linear-gradient(135deg, var(--kpmg-blue), var(--kpmg-mid)); border: none; color: #fff;
  }
  div[data-testid="stMetric"] {
    background: #fff; border-radius: 12px; padding: 0.8rem 1rem;
    border: 1px solid var(--kpmg-line); border-left: 5px solid var(--kpmg-mid);
    box-shadow: 0 1px 3px rgba(0, 51, 141, 0.06);
  }
  div[data-testid="stChatMessage"] { border-radius: 14px; background: var(--kpmg-tint); }
  div[data-testid="stProgress"] div[role="progressbar"] { background: var(--kpmg-line); border-radius: 999px; }
  div[data-testid="stProgress"] div[role="progressbar"] > div {
    background: linear-gradient(90deg, var(--kpmg-mid), var(--kpmg-light)); border-radius: 999px;
  }
  div[data-testid="stExpander"] { border-radius: 12px; border-color: var(--kpmg-line); background: #fff; }
  div[data-testid="stChatInput"] { border-radius: 14px; }
</style>
<div class="hero">
  <div class="brand">__BRAND__</div>
  <div>
    <div class="heading">SailPoint ISC Source Onboarding</div>
    <div class="sub">Identity Security Cloud intake, guided by the ISC Ask Agent</div>
  </div>
</div>
""".replace("__BRAND__", BRAND_HTML))


@st.cache_resource(show_spinner=False)
def ensure_index() -> None:
    """Build the index on first retrieval; not at import, which would block first paint."""
    import rag

    if not rag._store().get(limit=1)["ids"]:
        rag.ingest()


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def existing_interviews(user: dict[str, Any]) -> list[str]:
    """Slugs of the applications this user may open."""
    if not interview.STATE_DIR.exists():
        return []
    slugs = []
    for path in sorted(interview.STATE_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and auth.can_access(user, data):
            slugs.append(path.stem)
    return slugs


def unique_slug(name: str) -> str:
    base = interview.slugify(name)
    slug, n = base, 2
    while interview.state_path(slug).exists():
        slug, n = f"{base}-{n}", n + 1
    return slug


def login_page() -> None:
    st.html(
        '<style>div[data-testid="stSidebar"], div[data-testid="stSidebarCollapsedControl"],'
        'div[data-testid="stExpandSidebarButton"] { display: none; }</style>'
    )
    _, mid, _ = st.columns([1, 1.3, 1])
    with mid:
        with st.container(border=True):
            st.html('<h3 class="sectiontitle">Welcome</h3>')
            st.caption("Sign in to continue your application, or create an account to start one.")
            sign_in, sign_up = st.tabs(["Sign in", "Create account"])

            with sign_in:
                with st.form("login_form"):
                    uid = st.text_input("User ID", autocomplete="username")
                    pw = st.text_input("Password", type="password", autocomplete="current-password")
                    go = st.form_submit_button("Sign in", type="primary", use_container_width=True)
                if go:
                    try:
                        user = auth.login(uid, pw)
                    except auth.AuthError as exc:
                        st.error(str(exc))
                    else:
                        st.session_state["user_id"] = user["user_id"]
                        st.rerun()

            with sign_up:
                with st.form("register_form"):
                    new_uid = st.text_input("User ID", help="3-64 characters: letters, numbers and . _ @ + -")
                    name = st.text_input("Full name")
                    role = st.radio(
                        "I am an",
                        list(auth.SELF_SERVICE_ROLES),
                        format_func=lambda r: auth.ROLES[r],
                        horizontal=True,
                    )
                    pw1 = st.text_input("Password", type="password", help="At least 8 characters")
                    pw2 = st.text_input("Confirm password", type="password")
                    create = st.form_submit_button("Create account", type="primary", use_container_width=True)
                if create:
                    if pw1 != pw2:
                        st.error("The passwords do not match.")
                    else:
                        try:
                            user = auth.register(new_uid, name, pw1, role)
                        except auth.AuthError as exc:
                            st.error(str(exc))
                        else:
                            st.session_state["user_id"] = user["user_id"]
                            st.rerun()


def account_panel(user: dict[str, Any]) -> None:
    st.caption(f"Signed in as **{user['name']}** · {auth.ROLES[user['role']]}")
    if st.button("Sign out", key="signout", use_container_width=True):
        # Handled once the current section is known, so unsaved answers are saved first.
        st.session_state["signing_out"] = True

    with st.expander("Account"):
        with st.form("pw_form", clear_on_submit=True):
            old = st.text_input("Current password", type="password")
            new = st.text_input("New password", type="password")
            if st.form_submit_button("Change password", use_container_width=True):
                try:
                    auth.change_password(user["user_id"], old, new)
                    st.success("Password changed.")
                except auth.AuthError as exc:
                    st.error(str(exc))

    if user["role"] != "admin":
        return
    with st.expander("Manage users"):
        for person in auth.list_users():
            st.markdown(f"**{person['name']}** · `{person['user_id']}`")
            role_col, reset_col = st.columns([3, 2])
            new_role = role_col.selectbox(
                "Role",
                list(auth.ROLES),
                index=list(auth.ROLES).index(person["role"]),
                format_func=lambda r: auth.ROLES[r],
                key=f"role_{person['user_id']}",
                label_visibility="collapsed",
            )
            if new_role != person["role"]:
                try:
                    auth.set_role(person["user_id"], new_role)
                    st.rerun()
                except auth.AuthError as exc:
                    st.error(str(exc))
            if reset_col.button("Reset password", key=f"reset_{person['user_id']}"):
                st.session_state["temp_pw"] = (person["user_id"], auth.reset_password(person["user_id"]))
        if st.session_state.get("temp_pw"):
            who, temp = st.session_state["temp_pw"]
            st.info(f"Temporary password for `{who}`: `{temp}`. Share it once; they can change it after signing in.")


def access_panel(user: dict[str, Any], state: dict[str, Any]) -> None:
    people = [u for u in auth.list_users() if u["user_id"] != state.get("owner_id")]
    owner = state.get("owner_id")
    with st.expander("Owner & sharing"):
        st.caption(f"Owner: `{owner}`" if owner else "Owner: not assigned")
        if not auth.can_manage(user, state):
            shared = ", ".join(state.get("shared_with", [])) or "no one else"
            st.caption(f"Shared with: {shared}")
            return
        ids = [p["user_id"] for p in people]
        shared = st.multiselect(
            "Share with",
            ids,
            default=[s for s in state.get("shared_with", []) if s in ids],
            format_func=lambda i: next(p["name"] for p in people if p["user_id"] == i) + f" ({i})",
        )
        new_owner = owner
        if user["role"] == "admin":
            everyone = [u["user_id"] for u in auth.list_users()]
            new_owner = st.selectbox(
                "Owner",
                everyone,
                index=everyone.index(owner) if owner in everyone else 0,
            )
        if st.button("Save access", key="save_access", use_container_width=True):
            state["shared_with"] = [s for s in shared if s != new_owner]
            state["owner_id"] = new_owner
            interview.save_state(state)
            st.toast("Access updated.")
            st.rerun()


def slots_for(state: dict[str, Any], audience: str, section_id: str) -> list[dict]:
    return [
        s
        for s in SCHEMA["slots"]
        if s["audience"] == audience
        and s["section"] == section_id
        and interview.applicable(s, state["answers"])
    ]


def section_status(state: dict[str, Any], audience: str, sid: str) -> tuple[int, int]:
    slots = slots_for(state, audience, sid)
    resolved = sum(
        1
        for s in slots
        if s["id"] in state["answers"] or s["id"] in state["open_questions"]
    )
    return resolved, len(slots)


def table_rows(slot: dict[str, Any], current: Any) -> list[dict[str, Any]]:
    label = slot.get("row_label")
    columns = slot["columns"]
    if isinstance(current, list) and current:
        return current
    if slot.get("rows"):
        return [{label: name, **{c: "" for c in columns}} for name in slot["rows"]]
    blank = {c: "" for c in columns}
    return [dict(blank) for _ in range(3)]


def wk(prefix: str, sid: str) -> str:
    """Widget key that changes when the agent applies an answer, forcing a fresh widget."""
    return f"{prefix}{sid}_v{st.session_state.get(f'ver_{sid}', 0)}"


def render_input(slot: dict[str, Any], state: dict[str, Any]) -> None:
    key = wk("w_", slot["id"])
    current = state["answers"].get(slot["id"], {}).get("value")
    options = slot.get("options", [])
    label = slot["question"]

    if slot["type"] == "table":
        rows = table_rows(slot, current)
        config = {}
        if slot.get("row_label"):
            config[slot["row_label"]] = st.column_config.TextColumn(disabled=True, width="medium")
        edited = st.data_editor(
            rows,
            key=key,
            use_container_width=True,
            hide_index=True,
            num_rows="dynamic" if slot.get("dynamic") else "fixed",
            column_config=config,
        )
        # data_editor returns the data; session_state[key] holds only the diff.
        st.session_state[f"tbl_{slot['id']}"] = edited
    elif slot["type"] == "bool":
        default = None if current is None else ("Yes" if current else "No")
        st.segmented_control(
            label, ["Yes", "No"], default=default, key=key, label_visibility="collapsed"
        )
    elif slot["type"] == "choice":
        default = current if current in options else None
        if options and max(len(o) for o in options) <= 30:
            st.pills(label, options, default=default, key=key, label_visibility="collapsed")
        else:
            st.radio(
                label,
                options,
                index=options.index(default) if default else None,
                key=key,
                label_visibility="collapsed",
            )
    elif slot["type"] == "multi":
        default = [c for c in (current or []) if c in options]
        st.pills(
            label,
            options,
            default=default,
            selection_mode="multi",
            key=key,
            label_visibility="collapsed",
        )
    else:
        st.text_area(
            label,
            value=current or "",
            key=key,
            height=90,
            label_visibility="collapsed",
            placeholder=slot.get("hint", ""),
        )


def question_block(slot: dict[str, Any], state: dict[str, Any], number: int) -> None:
    with st.container(border=True):
        req = '<span class="req">*</span>' if slot.get("required") else ""
        st.html(
            f'<div class="qnum">Question {number}</div>'
            f'<p class="qtext">{slot["question"]}{req}</p>'
        )
        if slot.get("hint"):
            st.caption(f"For example: {slot['hint']}")

        unknown_key = wk("u_", slot["id"])
        is_open = slot["id"] in state["open_questions"]

        if st.session_state.get(unknown_key, is_open):
            st.text_input(
                "Who will find this out?",
                value=state["open_questions"].get(slot["id"], {}).get("reason", ""),
                key=wk("r_", slot["id"]),
                placeholder="Who will find this out?",
                label_visibility="collapsed",
            )
        else:
            render_input(slot, state)

        st.checkbox("I don't know — flag for follow-up", key=unknown_key, value=is_open)
        agent_col, docs_col = st.columns(2)
        with agent_col:
            if st.button(
                ":material/smart_toy: Take help from Agent to know more",
                key=f"ag_{slot['id']}",
                use_container_width=True,
                help="The ISC agent explains this question and can draft an answer for you to review.",
            ):
                st.session_state["agent_prompt"] = (
                    f"Explain question {number} in plain language, using the ISC docs, "
                    "and tell me what a good answer looks like. Then offer to draft it for me."
                )
        with docs_col:
            # Deliberately not inside a popover: the click reruns the script and would
            # close it before the answer could render.
            if st.button(
                "Explain from the ISC docs",
                key=f"e_{slot['id']}",
                use_container_width=True,
            ):
                with st.spinner("Checking reference documents…"):
                    ensure_index()
                    st.session_state[f"exp_{slot['id']}"] = interview.explain_text(slot)

        if slot.get("why"):
            st.caption(f"Why we ask: {slot['why']}")

        explained = st.session_state.get(f"exp_{slot['id']}")
        if explained:
            text, sources = explained
            st.info(text)
            if sources:
                st.caption("Sources: " + ", ".join(sources))
            if st.button("Hide", key=f"x_{slot['id']}"):
                del st.session_state[f"exp_{slot['id']}"]
                st.rerun()

        review = state["answers"].get(slot["id"], {}).get("review")
        if review:
            st.warning(review, icon=":material/flag:")


def save_section(state: dict[str, Any], slots: list[dict]) -> None:
    for slot in slots:
        sid = slot["id"]
        if st.session_state.get(wk("u_", sid)):
            state["open_questions"][sid] = {"reason": st.session_state.get(wk("r_", sid), "")}
            state["answers"].pop(sid, None)
            continue

        state["open_questions"].pop(sid, None)
        if slot["type"] == "table":
            rows = st.session_state.get(f"tbl_{sid}")
            if rows is None:
                continue
            rows = [r for r in rows if any(str(v).strip() for k, v in r.items() if k != slot.get("row_label"))]
            if rows:
                state["answers"][sid] = {"value": rows, "answered_at": now()}
            else:
                state["answers"].pop(sid, None)
            continue

        value = st.session_state.get(wk("w_", sid))
        if slot["type"] == "bool":
            value = None if value is None else value == "Yes"
        if value in (None, "", []):
            state["answers"].pop(sid, None)
            continue

        previous = state["answers"].get(sid, {})
        entry = {"value": value, "answered_at": now()}
        if previous.get("value") == value and "review" in previous:
            entry["review"] = previous["review"]
        state["answers"][sid] = entry

    interview.save_state(state)


def check_section(state: dict[str, Any], slots: list[dict]) -> int:
    checked = 0
    for slot in slots:
        entry = state["answers"].get(slot["id"])
        if not entry or not slot.get("validate"):
            continue
        verdict = interview.validate(slot, entry["value"])
        checked += 1
        if verdict and not verdict.startswith("PASS"):
            entry["review"] = verdict
        else:
            entry.pop("review", None)
    interview.save_state(state)
    return checked


def finish_sign_out(state: dict[str, Any] | None = None, slots: list[dict] | None = None) -> None:
    if not st.session_state.get("signing_out"):
        return
    if state is not None and slots:
        save_section(state, slots)
    st.session_state.clear()
    st.rerun()


def saved_label(state: dict[str, Any]) -> str:
    stamp = state.get("updated")
    if not stamp:
        return "Not saved yet"
    return "Last saved " + stamp.replace("T", " ")[:16] + " UTC"


def goto(index: int) -> None:
    st.session_state["nav"] = index
    st.rerun()


def apply_proposal(slug: str, prop: dict[str, Any]) -> None:
    state = interview.load_state(slug)
    sid = prop["id"]
    if prop["kind"] == "unknown":
        state["open_questions"][sid] = {"reason": prop.get("reason", "")}
        state["answers"].pop(sid, None)
    else:
        state["open_questions"].pop(sid, None)
        state["answers"][sid] = {"value": prop["value"], "answered_at": now()}
    interview.save_state(state)
    # A new widget key makes the form build a fresh widget from the saved value, even when
    # the browser still holds the old one.
    st.session_state[f"ver_{sid}"] = st.session_state.get(f"ver_{sid}", 0) + 1
    prop["status"] = "applied"


def dismiss_proposal(prop: dict[str, Any]) -> None:
    prop["status"] = "dismissed"


def proposal_card(slug: str, i: int, j: int, prop: dict[str, Any]) -> None:
    slot = BY_ID.get(prop["id"])
    if slot is None or prop["status"] == "dismissed":
        return
    with st.container(border=True):
        st.caption(slot["question"])
        if prop["kind"] == "unknown":
            st.text("Flag as unknown" + (f": {prop['reason']}" if prop["reason"] else ""))
        else:
            st.text("Suggested answer: " + interview.render(prop["value"]))
        if prop.get("reason") and prop["kind"] == "answer":
            st.caption("Based on: " + prop["reason"])
        if prop["status"] == "applied":
            st.caption(":material/check: Applied to the form. Review and edit it there.")
            return
        apply_col, dismiss_col = st.columns(2)
        apply_col.button(
            "Apply",
            key=f"ap_{slug}_{i}_{j}",
            on_click=apply_proposal,
            args=(slug, prop),
            type="primary",
            use_container_width=True,
        )
        dismiss_col.button(
            "Dismiss",
            key=f"dm_{slug}_{i}_{j}",
            on_click=dismiss_proposal,
            args=(prop,),
            use_container_width=True,
        )


def chat_panel(state: dict[str, Any], audience: str, page: str) -> None:
    slug = state["slug"]
    history: list[dict[str, Any]] = st.session_state.setdefault(f"chat_{slug}", [])
    on_review = page == REVIEW
    slots = [] if on_review else slots_for(state, audience, page)

    title, clear = st.columns([3, 1])
    title.html('<h3 class="sectiontitle" style="margin-top:0.2rem;white-space:nowrap">Ask Agent</h3>')
    if clear.button("Clear", key=f"clr_{slug}", disabled=not history):
        history.clear()
        st.rerun()
    st.caption(
        "Your SailPoint ISC specialist. Ask about any question, or say “fill question 3” "
        "and I'll draft the answer for you to review, edit and submit."
    )

    box = st.container(height=520, border=True)
    prompt = st.chat_input("Ask the ISC agent…", key=f"ci_{slug}") or st.session_state.pop(
        "agent_prompt", None
    )

    if prompt:
        prior = [{"role": m["role"], "content": m["content"]} for m in history]
        history.append({"role": "user", "content": prompt})
        outstanding = (
            [
                s["question"]
                for s in interview.pending(SCHEMA, state, audience)
                if s.get("required")
            ][:15]
            if on_review
            else []
        )
        context = assistant.build_context(
            SCHEMA["audiences"][audience],
            "Review & export" if on_review else SECTIONS[page]["name"],
            slots,
            state,
            outstanding,
        )
        with st.spinner("Thinking…"):
            try:
                ensure_index()
            except Exception:
                pass  # chat still works; the search tool reports the failure itself
            reply = assistant.respond(prompt, prior, context, slots, state)
        history.append(
            {
                "role": "assistant",
                "content": reply.text,
                "sources": reply.sources,
                "proposals": reply.proposals,
            }
        )

    with box:
        if not history:
            st.caption(
                "For example: “Read question 2 and fill it in”, “What does the primary key "
                "question mean?” or “The app is an HR portal backed by Oracle.”"
            )
        for i, msg in enumerate(history):
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                if msg.get("sources"):
                    st.caption("Sources: " + ", ".join(msg["sources"]))
                for j, prop in enumerate(msg.get("proposals", [])):
                    proposal_card(slug, i, j, prop)


# ---------------------------------------------------------------- sidebar

user = auth.get_user(st.session_state.get("user_id", ""))
if user is None:
    st.session_state.pop("user_id", None)
    login_page()
    st.stop()

with st.sidebar:
    st.subheader("Source onboarding")
    account_panel(user)

    if not (os.getenv("GEMINI_API_KEY") or os.getenv("GROQ_API_KEY")):
        detail = ""
        if SECRET_ERROR:
            detail = f"\n\nSecrets could not be read — {SECRET_ERROR}"
        elif SECRET_NAMES:
            detail = "\n\nSecrets loaded, but found: " + ", ".join(SECRET_NAMES)
        else:
            detail = "\n\nNo secrets file was found at all."
        st.warning(
            "No GEMINI_API_KEY or GROQ_API_KEY set — the docs explainer will show raw documentation "
            "excerpts instead of a written answer." + detail,
            icon=":material/key_off:",
        )

    options = ["+ New application"] + existing_interviews(user)
    if "active" not in st.session_state:
        # Reopen the application the user was last working on after signing back in.
        st.session_state["active"] = st.query_params.get("app") or auth.last_app(
            user["user_id"], options
        )
    active = st.session_state.get("active")
    choice = st.selectbox(
        "Application", options, index=options.index(active) if active in options else 0
    )
    if choice != active:
        st.session_state["active"] = choice
        st.session_state["nav"] = 0
    if choice != "+ New application":
        st.query_params["app"] = choice

    if choice == "+ New application":
        finish_sign_out()
        new_name = st.text_input("Application name")
        if st.button("Start intake", type="primary", disabled=not new_name):
            slug = unique_slug(new_name)
            interview.save_state(
                {
                    "name": new_name,
                    "slug": slug,
                    "created": now(),
                    "owner_id": user["user_id"],
                    "shared_with": [],
                    "answers": {},
                    "open_questions": {},
                }
            )
            st.session_state["active"] = slug
            st.session_state["nav"] = 0
            st.rerun()

        with st.expander("Restore from a saved file"):
            upload = st.file_uploader("Intake JSON", type="json", label_visibility="collapsed")
            if upload is not None:
                try:
                    restored = json.load(upload)
                    if not isinstance(restored, dict) or not {"name", "answers", "open_questions"} <= restored.keys():
                        raise ValueError
                except ValueError:
                    st.error("That file is not a valid intake backup.")
                else:
                    # Never trust the file's slug or owner: it would let an upload overwrite
                    # another user's application or write outside the state folder.
                    slug = unique_slug(str(restored["name"]))
                    restored.update(slug=slug, owner_id=user["user_id"], shared_with=[])
                    interview.save_state(restored)
                    st.session_state["active"] = slug
                    st.session_state["nav"] = 0
                    st.rerun()
        st.stop()

    state = interview.load_state(choice)
    access_panel(user, state)
    audiences = list(SCHEMA["audiences"]) if user["role"] == "admin" else [user["role"]]
    if len(audiences) > 1:
        audience = st.radio(
            "Completing as",
            audiences,
            format_func=lambda a: SCHEMA["audiences"][a],
        )
    else:
        audience = audiences[0]
        st.caption(f"Completing as: {SCHEMA['audiences'][audience]}")

    counts = {sid: section_status(state, audience, sid) for sid in SECTIONS}
    done = sum(c[0] for c in counts.values())
    total = sum(c[1] for c in counts.values())
    st.progress(done / total if total else 0.0)
    st.caption(f"{done} of {total} answered · {len(state['open_questions'])} flagged")

    live = [sid for sid in SECTIONS if counts[sid][1]]
    pages = live + [REVIEW]

    if st.session_state.get("resumed_for") != choice:
        st.session_state["resumed_for"] = choice
        saved_page = auth.get_resume(user["user_id"], choice)
        if saved_page in pages and saved_page != pages[0]:
            st.session_state["nav"] = pages.index(saved_page)
            name = "Review & export" if saved_page == REVIEW else SECTIONS[saved_page]["name"]
            st.toast(f"Welcome back — resuming at “{name}”.")
    nav = min(st.session_state.get("nav", 0), len(pages) - 1)

    def label(sid: str) -> str:
        if sid == REVIEW:
            return "Review & export"
        resolved, count = counts[sid]
        tick = "✓ " if resolved == count else ""
        return f"{tick}{SECTIONS[sid]['name']}  ({resolved}/{count})"

    picked = st.radio("Section", pages, index=nav, format_func=label)
    if pages.index(picked) != nav:
        # Leaving a section from the sidebar must not lose what was typed in it.
        if pages[nav] != REVIEW:
            save_section(state, slots_for(state, audience, pages[nav]))
        st.session_state["nav"] = pages.index(picked)
        st.rerun()

    current_slots = [] if pages[nav] == REVIEW else slots_for(state, audience, pages[nav])
    finish_sign_out(state, current_slots)
    if st.button("Save progress", icon=":material/save:", use_container_width=True):
        if current_slots:
            save_section(state, current_slots)
        st.toast("Progress saved — sign in later and you'll resume right here.")
    st.caption(saved_label(state))

    st.divider()
    st.download_button(
        "Back up this intake",
        json.dumps(state, indent=2, ensure_ascii=False),
        file_name=f"{state['slug']}.json",
        use_container_width=True,
        help="Server storage is temporary. Download to keep a copy you can restore later.",
    )

page = pages[nav]
if st.session_state.get("resume_mark") != (choice, page):
    auth.set_resume(user["user_id"], choice, page)
    st.session_state["resume_mark"] = (choice, page)

# ---------------------------------------------------------------- main

main_col, chat_col = st.columns([2.3, 1], gap="large")

with chat_col:
    st.html('<div class="chat-anchor"></div>')

with main_col:
    if page == REVIEW:
        step_chip = f'<span class="chip">Final step · {len(pages)} of {len(pages)}</span>'
    else:
        resolved, count = counts[page]
        step_chip = (
            f'<span class="chip">Section {nav + 1} of {len(pages) - 1}</span>'
            f'<span class="chip{" done" if resolved == count else ""}">'
            f"{'✓ ' if resolved == count else ''}{resolved}/{count} answered</span>"
        )
    st.html(
        f'<div class="pagehead"><h1>{html.escape(state["name"])}</h1>{step_chip}'
        f'<span class="chip">{done} of {total} overall</span></div>'
    )
    if page == REVIEW:
        st.caption("Everything captured so far, and what is still outstanding.")
        markdown = interview.report(state["slug"])

        cols = st.columns(len(SCHEMA["audiences"]) + 1)
        for col, (aud, aud_label) in zip(cols, SCHEMA["audiences"].items()):
            answered = sum(1 for sid in state["answers"] if BY_ID[sid]["audience"] == aud)
            col.metric(
                aud_label,
                answered,
                f"{len(interview.pending(SCHEMA, state, aud))} outstanding",
                delta_color="off",
            )
        cols[-1].metric("Flagged for follow-up", len(state["open_questions"]))

        if state["open_questions"]:
            st.subheader("Open questions")
            for sid, item in state["open_questions"].items():
                st.markdown(
                    f"- **{BY_ID[sid]['question']}** — {item['reason'] or '_unassigned_'}"
                )

        left, right = st.columns(2)
        left.download_button(
            "Download requirements (Markdown)",
            markdown,
            file_name=f"{state['slug']}-requirements.md",
            use_container_width=True,
        )
        right.download_button(
            "Download requirements (JSON)",
            json.dumps(state, indent=2, ensure_ascii=False),
            file_name=f"{state['slug']}-requirements.json",
            use_container_width=True,
        )

        with st.expander("Preview document"):
            st.markdown(markdown)

        st.divider()
        st.subheader("Final submission")

        outstanding = [s for s in interview.pending(SCHEMA, state, audience) if s.get("required")]
        submitted = state.get("submitted_at")

        if submitted:
            st.success(f"Submitted {submitted}. Re-submit to refresh after any changes.")

        if outstanding:
            st.warning(
                f"{len(outstanding)} required question(s) still unanswered. "
                "They will be listed in the workbook as gaps.",
                icon=":material/error:",
            )
            with st.expander(f"Show the {len(outstanding)} outstanding question(s)"):
                for slot in outstanding:
                    st.markdown(f"- {SECTIONS[slot['section']]['name']} — {slot['question']}")
            allow = st.checkbox("Submit anyway, with the gaps recorded")
        else:
            allow = True

        if st.button("Submit and generate Excel", type="primary", disabled=not allow):
            state["submitted_at"] = now()
            interview.save_state(state)
            st.session_state["xlsx"] = excel_export.build(SCHEMA, state)
            st.rerun()

        if st.session_state.get("xlsx"):
            st.download_button(
                "Download Excel workbook",
                st.session_state["xlsx"],
                file_name=f"{state['slug']}-onboarding.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
            )

        if st.button("← Back to questions"):
            goto(nav - 1)
    else:
        section = SECTIONS[page]
        st.html(f'<h3 class="sectiontitle">{html.escape(section["name"])}</h3>')
        if section.get("blurb"):
            st.html(f'<p class="sectionblurb">{section["blurb"]}</p>')

        section_slots = slots_for(state, audience, page)
        for number, slot in enumerate(section_slots, start=1):
            question_block(slot, state, number)

        st.html('<div class="navrow"></div>')
        back, check, save, nxt = st.columns([1, 1.4, 1, 1.2])

        if back.button("← Back", use_container_width=True, disabled=nav == 0):
            save_section(state, section_slots)
            goto(nav - 1)

        if check.button("Check against docs", use_container_width=True):
            save_section(state, section_slots)
            with st.spinner("Reviewing your answers…"):
                ensure_index()
                n = check_section(state, section_slots)
            st.toast(f"Checked {n} answer(s) against the ISC documentation.")
            st.rerun()

        if save.button("Save", use_container_width=True):
            save_section(state, section_slots)
            st.toast("Saved — you can close this and come back later.")

        next_label = "Review →" if nav == len(pages) - 2 else "Next section →"
        if nxt.button(next_label, type="primary", use_container_width=True):
            save_section(state, section_slots)
            goto(nav + 1)

with chat_col:
    chat_panel(state, audience, page)
