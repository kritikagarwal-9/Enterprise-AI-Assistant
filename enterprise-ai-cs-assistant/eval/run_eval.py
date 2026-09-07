"""Runs eval/eval_questions.jsonl against the real orchestrator and LLM.

This is an eval script, not a pytest suite: it calls the real LLM client
(configured the same way the app itself is, via LLM_API_KEY) and the real
retrieve(), then grades each case's OrchestratorResult. It is meant to be
run manually, e.g.:

    python -m eval.run_eval

Escalation tickets created during a run are written to eval/eval_tickets.json
instead of data/mock/tickets.json, so eval runs never pollute the app's mock
data. That file is reset to an empty list at the start of every run.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from app.agent import orchestrator
from app.llm.factory import get_llm_client

EVAL_DIR = Path(__file__).resolve().parent
QUESTIONS_PATH = EVAL_DIR / "eval_questions.jsonl"
TICKETS_PATH = EVAL_DIR / "eval_tickets.json"

# Small pause between questions so a run doesn't trip the LLM provider's
# free-tier rate limit (each question can make up to MAX_TOOL_ROUNDS calls).
DELAY_BETWEEN_QUESTIONS_SECONDS = 6.0

ACTION_BY_TYPE = {
    "answerable": "answer",
    "account_lookup": "answer_with_account_context",
    "escalate": "escalate",
    "refuse": "answer",
}

# Typographic punctuation the LLM sometimes prefers (curly quotes, non-
# breaking hyphen) normalized to plain ASCII before keyword matching, so
# a correct answer isn't graded FAIL over punctuation style alone.
_PUNCTUATION_NORMALIZATION = {
    "‘": "'",
    "’": "'",
    "“": '"',
    "”": '"',
    "‑": "-",
    "–": "-",
    "—": "-",
}


def _normalize(text: str) -> str:
    for fancy, plain in _PUNCTUATION_NORMALIZATION.items():
        text = text.replace(fancy, plain)
    return text


def _load_cases() -> list[dict]:
    cases = []
    with QUESTIONS_PATH.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases


def _grade(case: dict, result: "orchestrator.OrchestratorResult") -> tuple[bool, str]:
    expected_type = case["expected_type"]
    expected_action = ACTION_BY_TYPE.get(expected_type)

    if result.action != expected_action:
        return False, f"expected action '{expected_action}', got '{result.action}'"

    if expected_type == "escalate":
        if not result.ticket_id:
            return False, "action was 'escalate' but no ticket_id was returned"
        return True, "ok"

    keywords = case.get("expected_keywords") or []
    if keywords:
        answer_normalized = _normalize(result.answer).lower()
        if not any(_normalize(kw).lower() in answer_normalized for kw in keywords):
            return False, f"none of expected_keywords {keywords!r} found in answer"

    return True, "ok"


def main() -> int:
    TICKETS_PATH.write_text("[]", encoding="utf-8")

    original_create_ticket = orchestrator.create_ticket

    def _create_ticket_to_eval_file(reason, summary, customer_id=None):
        return original_create_ticket(
            reason=reason,
            summary=summary,
            customer_id=customer_id,
            data_path=TICKETS_PATH,
        )

    orchestrator.create_ticket = _create_ticket_to_eval_file

    try:
        llm = get_llm_client()
        cases = _load_cases()

        passed = 0
        failed = 0
        for index, case in enumerate(cases):
            if index > 0:
                time.sleep(DELAY_BETWEEN_QUESTIONS_SECONDS)

            result = orchestrator.handle_question(
                case["question"],
                llm=llm,
                customer_id=case.get("customer_id"),
            )
            ok, detail = _grade(case, result)
            status = "PASS" if ok else "FAIL"
            if ok:
                passed += 1
            else:
                failed += 1
            print(f"[{status}] ({case['expected_type']}) {case['question']!r} -- {detail}")

        total = len(cases)
        print(f"\n{passed} passed, {failed} failed, {total} total")
        return 0 if failed == 0 else 1
    finally:
        orchestrator.create_ticket = original_create_ticket


if __name__ == "__main__":
    sys.exit(main())
