"""HR/IT helpdesk agent: scope check -> MCP tool call -> policy retrieval -> answer."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from . import llm
from .guardrails import EMPLOYEE_ID_RE, check_query, redact
from .mcp_client import MCPClient
from .rag import PolicyIndex, citation

ROOT = Path(__file__).resolve().parent.parent
POLICY_DIR = ROOT / "policies"
INDEX_PATH = ROOT / "data" / "index.json"
MIN_SCORE = 0.08

RULE_WORDS = {"carry", "forward", "notice", "certificate", "encash", "accrual", "rule", "allowed", "entitled"}

BLOCKED_INJECTION = "I can't help with that request. I only answer HR and IT policy questions."
BLOCKED_SCOPE = "That's outside what I can help with. I only cover HR and IT topics such as leave, expenses, travel, laptops, access and security."
NOT_FOUND = "I could not find this in the policy library. Please contact HR at hr@company.example or raise a helpdesk ticket."


class HelpdeskAgent:
    def __init__(self, use_llm: bool = True) -> None:
        self.index = PolicyIndex.load(INDEX_PATH) if INDEX_PATH.exists() else PolicyIndex.build(POLICY_DIR)
        if not INDEX_PATH.exists():
            self.index.save(INDEX_PATH)
        self.mcp = MCPClient()
        self.use_llm = use_llm and llm.available() is not None

    def close(self) -> None:
        self.mcp.close()

    def ask(self, query: str) -> dict:
        verdict = check_query(query)
        if not verdict["allowed"]:
            text = BLOCKED_INJECTION if verdict["kind"] == "injection" else BLOCKED_SCOPE
            return {"answer": text, "citations": [], "tools": [], "blocked": verdict["kind"]}

        tools: list[dict] = []
        employee: dict | None = None
        balance: dict | None = None
        employee_id = EMPLOYEE_ID_RE.search(query)
        if employee_id:
            emp = employee_id.group(0).upper()
            profile = self.mcp.call_tool("get_employee_profile", {"employee_id": emp})
            leaves = self.mcp.call_tool("get_leave_balance", {"employee_id": emp})
            tools.append({"name": "get_employee_profile", "ok": not profile["is_error"], "data": profile["data"]})
            tools.append({"name": "get_leave_balance", "ok": not leaves["is_error"], "data": leaves["data"]})
            employee, balance = profile["data"], leaves["data"]

        hits = [(score, sec) for score, sec in self.index.search(query, k=3) if score >= MIN_SCORE]

        answer, citations = self._compose(query, hits, employee, balance, employee_id.group(0).upper() if employee_id else None)
        safe_answer, pii = redact(answer)
        return {"answer": safe_answer, "citations": citations, "tools": tools, "blocked": None, "pii_redacted": pii}

    def _compose(self, query, hits, employee, balance, emp_id):
        citations: list[str] = []
        if self.use_llm:
            text = self._ask_llm(query, hits, employee, balance)
            if text:
                citations = [citation(sec) for _, sec in hits[:2]]
                if balance:
                    citations.append("HR database (MCP) › leave_balances")
                if "source:" not in text.lower() and citations:
                    text = f"{text} (source: {citations[0]})"
                return text, citations

        parts: list[str] = []
        if emp_id and balance:
            name = employee["full_name"] if employee else emp_id
            parts.append(
                f"{name} ({emp_id}) has {balance['annual_remaining']} annual, "
                f"{balance['sick_remaining']} sick and {balance['casual_remaining']} casual leave days "
                f"remaining as of {balance['as_of']}."
            )
            citations.append("HR database (MCP) › leave_balances")
        elif emp_id and not balance:
            parts.append(f"I could not find employee {emp_id} in the HR directory.")

        wants_rule = any(word in query.lower() for word in RULE_WORDS)
        if hits and (not emp_id or wants_rule):
            score, top = hits[0]
            parts.append(_first_sentences(top["text"], 2))
            citations.append(citation(top))
        elif not parts:
            parts.append(NOT_FOUND)

        return " ".join(parts), citations

    def _ask_llm(self, query, hits, employee, balance) -> str | None:
        context = "\n\n".join(f"[{citation(sec)}]\n{sec['text']}" for _, sec in hits) or "no matching policy text"
        tool_data = json.dumps({"employee": employee, "leave_balance": balance}) if employee or balance else "none"
        prompt = (
            "You are an HR/IT helpdesk assistant. Answer only from the CONTEXT and TOOL DATA. "
            "Cite every claim as (source: <file> § <heading>). If the context cannot answer, say so and "
            "point to hr@company.example. Answer in at most 80 words.\n\n"
            f"CONTEXT:\n{context}\n\nTOOL DATA:\n{tool_data}\n\nQUESTION: {query}"
        )
        return llm.generate(prompt)


def _first_sentences(text: str, count: int) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return " ".join(sentences[:count]).strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask the HR/IT helpdesk agent a question.")
    parser.add_argument("--ask", help="question to answer")
    parser.add_argument("--json", action="store_true", help="print the full JSON result")
    parser.add_argument("--no-llm", action="store_true", help="force deterministic mode")
    args = parser.parse_args()
    agent = HelpdeskAgent(use_llm=not args.no_llm)
    try:
        if args.ask:
            result = agent.ask(args.ask)
            print(json.dumps(result, indent=2) if args.json else result["answer"])
            return
        print("HR/IT helpdesk agent. Empty line exits.")
        while True:
            try:
                query = input("\n> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not query:
                break
            result = agent.ask(query)
            print(result["answer"])
            if result["citations"]:
                print("sources:", "; ".join(result["citations"]))
    finally:
        agent.close()


if __name__ == "__main__":
    main()
