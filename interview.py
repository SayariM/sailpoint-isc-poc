"""Schema-driven interview that gathers ISC source onboarding requirements, grounded in the RAG corpus."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate

# rag.py also loads this, but it is imported lazily, so callers would see no .env.
load_dotenv()

ROOT = Path(__file__).parent
SCHEMA_PATH = ROOT / "onboarding_schema.json"
STATE_DIR = ROOT / "state"
OUT_DIR = ROOT / "out"

EXPLAIN_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You help an engineer answer one question in a SailPoint ISC source "
            "onboarding spec. Use only the provided context. Say what the question is "
            "asking for, list valid options if the context states them, and name the "
            "main pitfall. If the context does not cover it, say so plainly instead of "
            "guessing. Under 120 words. Cite sources as [file].",
        ),
        ("human", "Question: {question}\nWhy it matters: {why}\n\nContext:\n{context}"),
    ]
)

VALIDATE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Review one answer in a SailPoint ISC onboarding spec against reference "
            "documentation. First line must be exactly PASS, CONCERN, or UNKNOWN. Then "
            "at most two sentences. Use only the context; if it does not cover the rule, "
            "answer UNKNOWN. Never invent a requirement.",
        ),
        (
            "human",
            "Question: {question}\nAnswer: {answer}\nRule: {rule}\n\nContext:\n{context}",
        ),
    ]
)


def load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "source"


def state_path(slug: str) -> Path:
    return STATE_DIR / f"{slug}.json"


def load_state(slug: str) -> dict[str, Any]:
    path = state_path(slug)
    if not path.exists():
        sys.exit(f"No interview found for '{slug}'. Start one with: interview.py start \"Name\"")
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(state: dict[str, Any]) -> None:
    STATE_DIR.mkdir(exist_ok=True)
    state["updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    state_path(state["slug"]).write_text(
        json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _matches(entry: dict[str, Any] | None, allowed: list[Any]) -> bool:
    if entry is None:
        return False
    value = entry["value"]
    given = value if isinstance(value, list) else [value]
    return any(v in allowed for v in given)


def applicable(slot: dict[str, Any], answers: dict[str, Any]) -> bool:
    for dep_id, allowed in slot.get("applies_to", {}).items():
        if not _matches(answers.get(dep_id), allowed):
            return False

    any_of = slot.get("applies_to_any", {})
    if any_of and not any(
        _matches(answers.get(dep_id), allowed) for dep_id, allowed in any_of.items()
    ):
        return False
    return True


def pending(
    schema: dict[str, Any], state: dict[str, Any], audience: str = "all"
) -> list[dict[str, Any]]:
    done = set(state["answers"]) | set(state["open_questions"])
    return [
        s
        for s in schema["slots"]
        if s["id"] not in done
        and (audience == "all" or s["audience"] == audience)
        and applicable(s, state["answers"])
    ]


def grounding_docs(slot: dict[str, Any]) -> list:
    import rag  # deferred: pulls in torch, which is slow and trips Streamlit's file watcher

    return rag.retrieve(slot.get("grounding") or slot["question"], k=4)


def explain_text(
    slot: dict[str, Any], api_key: str | None = None
) -> tuple[str, list[str]]:
    import rag

    docs = grounding_docs(slot)
    if not docs:
        return "No reference documents are indexed yet (run: python rag.py ingest).", []
    try:
        chain = EXPLAIN_PROMPT | rag.chat(api_key=api_key)
        answer = chain.invoke(
            {
                "question": slot["question"],
                "why": slot.get("why", "not stated"),
                "context": rag.format_context(docs),
            }
        )
    except Exception as exc:
        excerpts = "\n\n".join(f"**{rag.cite(d)}**\n\n{d.page_content[:700]}" for d in docs[:2])
        return f"_{exc}_\n\nShowing the matching documentation instead:\n\n{excerpts}", [
            rag.cite(d) for d in docs
        ]
    return answer.content, [rag.cite(d) for d in docs]


def explain(slot: dict[str, Any]) -> None:
    text, sources = explain_text(slot)
    print(f"\n  {text}\n")
    if sources:
        print("  sources: " + ", ".join(sources) + "\n")


def validate(
    slot: dict[str, Any], value: Any, api_key: str | None = None
) -> str | None:
    import rag

    rule = slot.get("validate")
    if not rule:
        return None
    docs = grounding_docs(slot)
    if not docs:
        return None
    try:
        chain = VALIDATE_PROMPT | rag.chat(api_key=api_key)
        return chain.invoke(
            {
                "question": slot["question"],
                "answer": value,
                "rule": rule,
                "context": rag.format_context(docs),
            }
        ).content.strip()
    except Exception as exc:
        return f"UNKNOWN\nCould not run the check: {exc}"


def prompt_value(slot: dict[str, Any]) -> Any | None:
    """Returns the answer, or None if the user chose to skip or quit."""
    options = slot.get("options", [])
    while True:
        print(f"\n[{slot['id']}] {slot['question']}")
        if slot.get("hint"):
            print(f"  e.g. {slot['hint']}")
        if slot.get("why"):
            print(f"  why we ask: {slot['why']}")
        if slot["type"] == "bool":
            print("  1) yes   2) no")
        for i, option in enumerate(options, start=1):
            print(f"  {i}) {option}")
        if slot["type"] == "multi":
            print("  (comma-separated numbers)")
        print("  commands: ? = explain from docs, skip = defer, quit = save and exit")

        raw = input("> ").strip()
        if not raw:
            continue
        if raw == "?":
            explain(slot)
            continue
        if raw in {"skip", "quit"}:
            return raw

        if slot["type"] == "bool":
            if raw in {"1", "yes", "y"}:
                return True
            if raw in {"2", "no", "n"}:
                return False
            print("  Enter 1 or 2.")
            continue
        if slot["type"] == "choice":
            if raw.isdigit() and 1 <= int(raw) <= len(options):
                return options[int(raw) - 1]
            print(f"  Enter a number 1-{len(options)}.")
            continue
        if slot["type"] == "multi":
            picks = [p.strip() for p in raw.split(",") if p.strip()]
            if all(p.isdigit() and 1 <= int(p) <= len(options) for p in picks) and picks:
                return [options[int(p) - 1] for p in picks]
            print(f"  Enter numbers 1-{len(options)}, comma-separated.")
            continue
        return raw


def run(slug: str, check: bool, audience: str) -> None:
    schema = load_schema()
    state = load_state(slug)
    sections = {s["id"]: s["name"] for s in schema["sections"]}
    current_section = None

    while True:
        queue = pending(schema, state, audience)
        if not queue:
            label = schema["audiences"].get(audience, audience)
            print(f"\nAll applicable questions answered for: {label}")
            break

        slot = queue[0]
        remaining = len(queue)
        if slot["section"] != current_section:
            current_section = slot["section"]
            print(f"\n=== {sections[current_section]} ({remaining} question(s) left) ===")

        value = prompt_value(slot)
        if value == "quit":
            print(f"\nSaved. Resume with: python interview.py resume {slug}")
            save_state(state)
            return
        if value == "skip":
            reason = input("  reason / who will answer it: ").strip()
            state["open_questions"][slot["id"]] = {"reason": reason}
            save_state(state)
            continue

        entry: dict[str, Any] = {
            "value": value,
            "answered_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        if check:
            verdict = validate(slot, value)
            if verdict and not verdict.startswith("PASS"):
                print(f"\n  >> {verdict}\n")
                entry["review"] = verdict
        state["answers"][slot["id"]] = entry
        save_state(state)

    save_state(state)
    report(slug)


def render(value: Any) -> str:
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, list):
        return ", ".join(value)
    return str(value)


def oneline(text: str) -> str:
    """Flatten for markdown table cells and list items."""
    return re.sub(r"\s+", " ", text).replace("|", r"\|").strip()


def report(slug: str) -> str:
    schema = load_schema()
    state = load_state(slug)
    OUT_DIR.mkdir(exist_ok=True)

    lines = [
        f"# {schema['title']}: {state['name']}",
        "",
        f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d')} "
        f"| schema v{schema['version']}",
        "",
    ]
    by_id = {s["id"]: s for s in schema["slots"]}

    for audience, label in schema["audiences"].items():
        answered = {
            sid: entry
            for sid, entry in state["answers"].items()
            if by_id[sid]["audience"] == audience
        }
        if not answered:
            continue
        lines += [f"# {label}", ""]
        for section in schema["sections"]:
            rows = [
                (by_id[sid]["question"], entry)
                for sid, entry in answered.items()
                if by_id[sid]["section"] == section["id"]
            ]
            if not rows:
                continue
            lines += [
                f"## {section['name']}",
                "",
                "| Requirement | Answer |",
                "| --- | --- |",
            ]
            for question, entry in rows:
                lines.append(f"| {question} | {oneline(render(entry['value']))} |")
            lines.append("")

    reviews = [
        (by_id[sid]["question"], entry["review"])
        for sid, entry in state["answers"].items()
        if "review" in entry
    ]
    if reviews:
        lines += ["## Flagged for review", ""]
        lines += [f"- **{q}** — {oneline(r)}" for q, r in reviews] + [""]

    if state["open_questions"]:
        lines += ["## Open questions", ""]
        lines += [
            f"- **{by_id[sid]['question']}** — {item['reason'] or 'unassigned'}"
            for sid, item in state["open_questions"].items()
        ]
        lines.append("")

    lines += [
        "## Completeness",
        "",
        "| Audience | Answered | Still to ask |",
        "| --- | --- | --- |",
    ]
    for audience, label in schema["audiences"].items():
        answered = sum(
            1 for sid in state["answers"] if by_id[sid]["audience"] == audience
        )
        lines.append(f"| {label} | {answered} | {len(pending(schema, state, audience))} |")
    lines += ["", f"Open questions: {len(state['open_questions'])}", ""]

    md_path = OUT_DIR / f"{slug}-requirements.md"
    json_path = OUT_DIR / f"{slug}-requirements.json"
    markdown = "\n".join(lines)
    md_path.write_text(markdown, encoding="utf-8")
    json_path.write_text(
        json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Wrote {md_path}\nWrote {json_path}")
    return markdown


def review(slug: str) -> None:
    schema = load_schema()
    state = load_state(slug)
    by_id = {s["id"]: s for s in schema["slots"]}
    for sid, entry in state["answers"].items():
        print(f"{by_id[sid]['audience']:6} {sid:24} {render(entry['value'])[:70]}")
    for sid in state["open_questions"]:
        print(f"{by_id[sid]['audience']:6} {sid:24} [OPEN] {by_id[sid]['question'][:60]}")
    for audience, label in schema["audiences"].items():
        print(f"\n{label}: {len(pending(schema, state, audience))} still to ask.")


def start(name: str, check: bool, audience: str) -> None:
    slug = slugify(name)
    if state_path(slug).exists():
        sys.exit(f"'{slug}' already exists. Use: python interview.py resume {slug}")
    state = {
        "name": name,
        "slug": slug,
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "answers": {},
        "open_questions": {},
    }
    save_state(state)
    run(slug, check, audience)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-check",
        action="store_true",
        help="skip the doc-grounded validation call after each answer",
    )
    parser.add_argument(
        "--audience",
        choices=["owner", "iam", "all"],
        default="owner",
        help="owner = application contact intake, iam = ISC design decisions",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    start_cmd = sub.add_parser("start", help="begin a new onboarding interview")
    start_cmd.add_argument("name")
    for cmd, help_text in [
        ("resume", "continue an interview"),
        ("review", "show what has been captured so far"),
        ("report", "write the requirements document"),
    ]:
        sub.add_parser(cmd, help=help_text).add_argument("slug")
    sub.add_parser("list", help="list interviews in progress")

    args = parser.parse_args()
    check = not args.no_check

    if args.command == "start":
        start(args.name, check, args.audience)
    elif args.command == "resume":
        run(args.slug, check, args.audience)
    elif args.command == "review":
        review(args.slug)
    elif args.command == "report":
        report(args.slug)
    else:
        for path in sorted(STATE_DIR.glob("*.json")) if STATE_DIR.exists() else []:
            print(path.stem)


if __name__ == "__main__":
    main()
