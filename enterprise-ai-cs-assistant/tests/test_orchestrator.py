"""Tests for the agent orchestrator: tool-calling loop, escalation, refusal."""

from typing import Any

import pytest

from app.agent import orchestrator


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
    monkeypatch.setattr(orchestrator, "retrieve", lambda question: [])


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
