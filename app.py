"""Streamlit UI for the ISC source onboarding interview."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

import streamlit as st

import excel_export
import interview

st.set_page_config(
    page_title="ISC Source Onboarding",
    page_icon=":material/hub:",
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
except Exception as exc:
    SECRET_ERROR = f"{type(exc).__name__}: {exc}"

st.html("""
<style>
  .block-container { padding-top: 2.2rem; max-width: 1080px; }
  h1, h2, h3 { letter-spacing: -0.01em; }
  div[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 10px; }
  div[data-testid="stSidebarUserContent"] { padding-top: 1.2rem; }
  .qnum {
    display:inline-block; font-size:0.72rem; font-weight:600; letter-spacing:0.06em;
    color:#8A8F98; text-transform:uppercase; margin-bottom:0.15rem;
  }
  .qtext { font-size:1.02rem; font-weight:600; line-height:1.45; margin:0 0 0.15rem 0; }
  .req { color:#C8102E; margin-left:0.25rem; }
  .sectionblurb { color:#5C6370; font-size:0.94rem; margin:-0.4rem 0 1.1rem 0; }
  .navrow { border-top:1px solid #E6E8EB; margin-top:1.4rem; padding-top:0.2rem; }
</style>
""")


@st.cache_resource(show_spinner=False)
def ensure_index() -> None:
    """Build the index on first retrieval; not at import, which would block first paint."""
    import rag

    if not rag._store().get(limit=1)["ids"]:
        rag.ingest()


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def existing_interviews() -> list[str]:
    if not interview.STATE_DIR.exists():
        return []
    return sorted(p.stem for p in interview.STATE_DIR.glob("*.json"))


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


def render_input(slot: dict[str, Any], state: dict[str, Any]) -> None:
    key = f"w_{slot['id']}"
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

        unknown_key = f"u_{slot['id']}"
        is_open = slot["id"] in state["open_questions"]

        if st.session_state.get(unknown_key, is_open):
            st.text_input(
                "Who will find this out?",
                value=state["open_questions"].get(slot["id"], {}).get("reason", ""),
                key=f"r_{slot['id']}",
                placeholder="Who will find this out?",
                label_visibility="collapsed",
            )
        else:
            render_input(slot, state)

        left, right = st.columns([3, 2])
        with left:
            st.checkbox("I don't know — flag for follow-up", key=unknown_key, value=is_open)
        with right:
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
        if st.session_state.get(f"u_{sid}"):
            state["open_questions"][sid] = {"reason": st.session_state.get(f"r_{sid}", "")}
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

        value = st.session_state.get(f"w_{sid}")
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


def goto(index: int) -> None:
    st.session_state["nav"] = index
    st.rerun()


# ---------------------------------------------------------------- sidebar

with st.sidebar:
    st.subheader("Source onboarding")

    if not os.getenv("GROQ_API_KEY"):
        detail = ""
        if SECRET_ERROR:
            detail = f"\n\nSecrets could not be read — {SECRET_ERROR}"
        elif SECRET_NAMES:
            detail = "\n\nSecrets loaded, but found: " + ", ".join(SECRET_NAMES)
        else:
            detail = "\n\nNo secrets file was found at all."
        st.warning(
            "No GROQ_API_KEY set — the docs explainer will show raw documentation "
            "excerpts instead of a written answer." + detail,
            icon=":material/key_off:",
        )

    options = ["+ New application"] + existing_interviews()
    if "active" not in st.session_state:
        st.session_state["active"] = st.query_params.get("app")
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
        new_name = st.text_input("Application name")
        if st.button("Start intake", type="primary", disabled=not new_name):
            slug = interview.slugify(new_name)
            interview.save_state(
                {
                    "name": new_name,
                    "slug": slug,
                    "created": now(),
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
                restored = json.load(upload)
                interview.save_state(restored)
                st.session_state["active"] = restored["slug"]
                st.session_state["nav"] = 0
                st.rerun()
        st.stop()

    state = interview.load_state(choice)
    audience = st.radio(
        "Completing as",
        list(SCHEMA["audiences"]),
        format_func=lambda a: SCHEMA["audiences"][a],
    )

    counts = {sid: section_status(state, audience, sid) for sid in SECTIONS}
    done = sum(c[0] for c in counts.values())
    total = sum(c[1] for c in counts.values())
    st.progress(done / total if total else 0.0)
    st.caption(f"{done} of {total} answered · {len(state['open_questions'])} flagged")

    live = [sid for sid in SECTIONS if counts[sid][1]]
    pages = live + [REVIEW]
    nav = min(st.session_state.get("nav", 0), len(pages) - 1)

    def label(sid: str) -> str:
        if sid == REVIEW:
            return "Review & export"
        resolved, count = counts[sid]
        tick = "✓ " if resolved == count else ""
        return f"{tick}{SECTIONS[sid]['name']}  ({resolved}/{count})"

    picked = st.radio("Section", pages, index=nav, format_func=label)
    if pages.index(picked) != nav:
        nav = pages.index(picked)
        st.session_state["nav"] = nav

    st.divider()
    st.download_button(
        "Back up this intake",
        json.dumps(state, indent=2, ensure_ascii=False),
        file_name=f"{state['slug']}.json",
        use_container_width=True,
        help="Server storage is temporary. Download to keep a copy you can restore later.",
    )

page = pages[nav]

# ---------------------------------------------------------------- main

st.title(state["name"])

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
    st.subheader(section["name"])
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
