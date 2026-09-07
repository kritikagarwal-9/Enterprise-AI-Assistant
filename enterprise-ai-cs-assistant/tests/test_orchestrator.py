"""Tests for the agent orchestrator: tool-calling loop, escalation, refusal."""

from typing import Any

import pytest

from app.agent import orchestrator
from app.tools.account_lookup import AccountLookupError
from app.tools.escalation import TicketCreationError


class ScriptedLLM:
    """Fake LLM client that returns a scripted sequence of messages."""

    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self._responses = list(responses)
        self.calls: list[list[dict[str, Any]]] = []

    def complete(self, messages: list[dict[str, str]]) -> str:  # pragma: no cover
        raise AssertionError("orchestrator should use complete_with_tools")

    def complete_with_tools(self, messages, tools) -> dict[str, Any]:
        self.calls.append(messages)
        return self._responses.pop(0)


def _tool_call(call_id: str, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    import json

    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": call_id,
                "function": {"name": name, "arguments": json.dumps(arguments)},
            }
        ],
    }


def _final(text: str) -> dict[str, Any]:
    return {"role": "assistant", "content": text, "tool_calls": []}


@pytest.fixture(autouse=True)
def no_retrieval(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(orchestrator, "retrieve", lambda question, n_results=4: [])


def test_plain_question_answers_without_tools() -> None:
    llm = ScriptedLLM([_final("Starter includes 5 seats.")])
    result = orchestrator.handle_question("What is in Starter?", llm=llm)
    assert result.action == "answer"
    assert result.answer == "Starter includes 5 seats."
    assert result.ticket_id is None


def test_account_question_calls_lookup_account_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        orchestrator,
        "lookup_account",
        lambda customer_id: {"customer_id": customer_id, "plan": "pro", "status": "active"},
    )
    llm = ScriptedLLM(
        [
            _tool_call("call_1", "lookup_account", {}),
            _final("You're on the Pro plan and your account is active."),
        ]
    )
    result = orchestrator.handle_question(
        "What plan am I on?", llm=llm, customer_id="cust_002"
    )
    assert result.action == "answer_with_account_context"
    assert "Pro" in result.answer
    # second call to the LLM should include the tool result as context
    assert any(m.get("role") == "tool" for m in llm.calls[1])


def test_billing_dispute_escalates_and_returns_ticket_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        orchestrator,
        "create_ticket",
        lambda reason, summary, customer_id=None: {
            "ticket_id": "tkt_test123",
            "reason": reason,
            "summary": summary,
        },
    )
    llm = ScriptedLLM(
        [
            _tool_call(
                "call_1",
                "escalate_to_human",
                {"reason": "billing_dispute", "summary": "Customer disputes a charge."},
            ),
            _final("I've escalated this to a Customer Success manager."),
        ]
    )
    result = orchestrator.handle_question(
        "I was charged twice, fix it now.", llm=llm, customer_id="cust_001"
    )
    assert result.action == "escalate"
    assert result.ticket_id == "tkt_test123"


def test_lookup_without_customer_id_returns_error_to_model() -> None:
    llm = ScriptedLLM(
        [
            _tool_call("call_1", "lookup_account", {}),
            _final("I don't have your account on file."),
        ]
    )
    result = orchestrator.handle_question("What plan am I on?", llm=llm, customer_id=None)
    assert result.action == "answer_with_account_context"
    tool_result_message = llm.calls[1][-1]
    assert "error" in tool_result_message["content"]


def test_runaway_tool_loop_fails_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        orchestrator, "lookup_account", lambda customer_id: {"plan": "pro"}
    )
    llm = ScriptedLLM(
        [
            _tool_call("c1", "lookup_account", {}),
            _tool_call("c2", "lookup_account", {}),
            _tool_call("c3", "lookup_account", {}),
        ]
    )
    result = orchestrator.handle_question(
        "loop question", llm=llm, customer_id="cust_001"
    )
    assert "escalate manually" in result.answer.lower()


def test_system_prompt_tells_model_to_refuse_not_escalate_legal_advice() -> None:
    """Regression guard for the eval-discovered bug where a legal-advice
    question was escalated instead of refused. Prompt wording isn't
    deterministically testable against a real LLM in pytest, so this locks
    in that the guardrail text exists; real behavior is confirmed by
    eval/run_eval.py.
    """
    assert "legal advice" in orchestrator.SYSTEM_PROMPT.lower()
    assert "do not use escalate_to_human" in orchestrator.SYSTEM_PROMPT.lower()

    escalate_tool = next(
        tool
        for tool in orchestrator.TOOLS
        if tool["function"]["name"] == "escalate_to_human"
    )
    assert "legal advice" in escalate_tool["function"]["description"].lower()


def test_lookup_account_error_returns_error_to_model_instead_of_crashing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(customer_id: str) -> dict:
        raise AccountLookupError("account data unavailable: corrupt file")

    monkeypatch.setattr(orchestrator, "lookup_account", _boom)
    llm = ScriptedLLM(
        [
            _tool_call("call_1", "lookup_account", {}),
            _final("I couldn't look up your account right now."),
        ]
    )
    result = orchestrator.handle_question(
        "What plan am I on?", llm=llm, customer_id="cust_001"
    )
    assert result.action == "answer_with_account_context"
    tool_result_message = llm.calls[1][-1]
    assert "error" in tool_result_message["content"]


def test_ticket_creation_error_fails_safe_without_escalating(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(reason: str, summary: str, customer_id: str | None = None) -> dict:
        raise TicketCreationError("disk full")

    monkeypatch.setattr(orchestrator, "create_ticket", _boom)
    llm = ScriptedLLM(
        [
            _tool_call(
                "call_1",
                "escalate_to_human",
                {"reason": "billing_dispute", "summary": "Charged twice."},
            ),
        ]
    )
    result = orchestrator.handle_question(
        "I was charged twice.", llm=llm, customer_id="cust_001"
    )
    assert result.action == "answer"
    assert result.ticket_id is None
    assert "escalate manually" in result.answer.lower()
