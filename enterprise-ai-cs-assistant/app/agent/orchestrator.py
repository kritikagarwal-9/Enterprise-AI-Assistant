"""Decides: answer from docs, call account_lookup, call escalation, or refuse.

This is the piece that makes the assistant an agent rather than a plain
RAG-and-answer demo. It always retrieves product-doc context up front
(that context is relevant to almost every question), then gives the model
two tools and lets the model decide whether it needs to use them before
producing a final answer.

Security note: the model is never trusted to supply a customer_id. The
customer_id comes only from the authenticated caller's request and is
injected directly when a tool runs, so the model cannot look up or
escalate on behalf of a different account than the one it was asked
about.
"""

from __future__ import annotations

import json
from typing import Any

from app.llm.base import LLMClient
from app.rag.retrieve import retrieve
from app.tools.account_lookup import lookup_account
from app.tools.escalation import create_ticket

MAX_TOOL_ROUNDS = 3

SYSTEM_PROMPT = (
    "You are an internal Customer Success assistant for CloudBoard, a B2B SaaS "
    "project-management product. Be concise and professional.\n\n"
    "Answer product and plan questions only from the retrieved CloudBoard "
    "documents supplied in the conversation. Do not invent product facts, "
    "account data, refunds, contract terms, or tool results.\n\n"
    "Use the lookup_account tool before answering any question that depends "
    "on a specific customer's plan, usage, or account status.\n\n"
    "Use the escalate_to_human tool, instead of answering yourself, for "
    "billing disputes, refund requests, contract changes, or complaints. "
    "Do not attempt to resolve these yourself even if you believe you know "
    "the answer."
)

NO_CONTEXT_INSTRUCTION = (
    "No retrieved documents were found for this question. Do not invent "
    "product facts. If you cannot answer from a tool result either, say "
    "you do not have documentation for this question."
)

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "lookup_account",
            "description": (
                "Look up the current customer's subscription plan, usage, "
                "and account status. Takes no arguments, it always looks up "
                "the customer attached to this conversation."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "escalate_to_human",
            "description": (
                "Create a support ticket and hand off to a human Customer "
                "Success Manager. Use for billing disputes, refund requests, "
                "contract changes, or complaints."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "enum": ["billing_dispute", "contract_issue", "complaint", "other"],
                        "description": "Short reason category for the ticket.",
                    },
                    "summary": {
                        "type": "string",
                        "description": "One or two sentence summary of the customer's issue.",
                    },
                },
                "required": ["reason", "summary"],
            },
        },
    },
]


class OrchestratorResult:
    def __init__(self, answer: str, action: str, sources: list[str], ticket_id: str | None):
        self.answer = answer
        self.action = action
        self.sources = sources
        self.ticket_id = ticket_id


def _unique_sources(hits: list[dict]) -> list[str]:
    seen: list[str] = []
    for hit in hits:
        name = str(hit.get("source") or "").strip()
        if name and name not in seen:
            seen.append(name)
    return seen


def _doc_context_message(question: str, hits: list[dict]) -> str:
    if not hits:
        return f"Question: {question}\n\n{NO_CONTEXT_INSTRUCTION}"
    blocks = []
    for index, hit in enumerate(hits, start=1):
        source = str(hit.get("source") or "unknown")
        text = str(hit.get("text") or "")
        blocks.append(f"[{index}] Source: {source}\n{text}")
    context = "\n\n".join(blocks)
    return f"Question: {question}\n\nRetrieved CloudBoard documents:\n\n{context}"


def _run_tool(name: str, arguments: dict[str, Any], customer_id: str | None) -> tuple[str, str | None]:
    """Executes one tool call. Returns (result_text_for_model, ticket_id_if_any)."""
    if name == "lookup_account":
        if not customer_id:
            return (
                json.dumps({"error": "no customer_id was provided for this conversation"}),
                None,
            )
        account = lookup_account(customer_id)
        if account is None:
            return json.dumps({"error": f"no account found for {customer_id}"}), None
        return json.dumps(account), None

    if name == "escalate_to_human":
        reason = str(arguments.get("reason") or "other")
        summary = str(arguments.get("summary") or "")
        ticket = create_ticket(reason=reason, summary=summary, customer_id=customer_id)
        return json.dumps(ticket), ticket["ticket_id"]

    return json.dumps({"error": f"unknown tool {name}"}), None


def handle_question(
    question: str,
    llm: LLMClient,
    customer_id: str | None = None,
) -> OrchestratorResult:
    hits = retrieve(question)
    sources = _unique_sources(hits)

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _doc_context_message(question, hits)},
    ]

    ticket_id: str | None = None
    action = "answer"

    for _ in range(MAX_TOOL_ROUNDS):
        message = llm.complete_with_tools(messages, TOOLS)
        tool_calls = message.get("tool_calls") or []

        if not tool_calls:
            content = str(message.get("content") or "").strip()
            return OrchestratorResult(
                answer=content,
                action=action,
                sources=sources,
                ticket_id=ticket_id,
            )

        messages.append(message)
        for call in tool_calls:
            fn = call.get("function", {})
            name = fn.get("name", "")
            try:
                arguments = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                arguments = {}

            result_text, maybe_ticket_id = _run_tool(name, arguments, customer_id)
            if name == "lookup_account":
                action = "answer_with_account_context"
            if maybe_ticket_id:
                ticket_id = maybe_ticket_id
                action = "escalate"

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.get("id", ""),
                    "content": result_text,
                }
            )

    # Model kept calling tools past the round limit. Fail safe rather than loop forever.
    return OrchestratorResult(
        answer="I was not able to finish handling this request. Please escalate manually.",
        action=action,
        sources=sources,
        ticket_id=ticket_id,
    )
