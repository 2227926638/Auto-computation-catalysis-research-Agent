from __future__ import annotations

import argparse
import json
from pathlib import Path

from research_agent.adapters.question_agent_adapter import QuestionAgentAdapter
from research_agent.gates.orchestrator import AuditGateOrchestrator
from research_agent.protocols.registry import ProtocolRegistry
from research_agent.schemas.core import GateStatus, P0AuditSummary


def audit_question_agent_output(
    question_agent_output: str | Path,
    protocol_registry_path: str | Path | None = None,
    limit: int | None = None,
) -> tuple[dict[str, object], list[P0AuditSummary]]:
    imported = QuestionAgentAdapter().import_run(question_agent_output)
    registry = ProtocolRegistry.from_yaml(protocol_registry_path) if protocol_registry_path else ProtocolRegistry.default()
    orchestrator = AuditGateOrchestrator(registry)

    questions = imported.questions[:limit] if limit else imported.questions
    summaries = [orchestrator.audit_question(card, imported.evidence) for card in questions]
    counts = {
        "PASS": sum(1 for item in summaries if item.overall_status == GateStatus.PASS),
        "WARN": sum(1 for item in summaries if item.overall_status == GateStatus.WARN),
        "BLOCK": sum(1 for item in summaries if item.overall_status == GateStatus.BLOCK),
    }
    manifest: dict[str, object] = {
        "run_id": imported.run_id,
        "source_dir": imported.source_dir,
        "question_count": len(imported.questions),
        "audited_question_count": len(summaries),
        "adapter_candidate_count": len(imported.candidate_question_ids),
        "evidence_count": len(imported.evidence),
        "method_evidence_count": len(imported.method_evidence),
        "p0_gate_counts": counts,
        "manual_review_required": imported.manual_review_required,
    }
    return manifest, summaries


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run P0 scientific gates on question-agent outputs.")
    parser.add_argument("--question-agent-output", required=True, help="Path to an existing question-agent output directory.")
    parser.add_argument("--protocol-registry", default=None, help="Optional protocol registry YAML path.")
    parser.add_argument("--limit", type=int, default=None, help="Audit only the first N question cards.")
    parser.add_argument("--out", default=None, help="Optional JSON output path. Prints JSON to stdout if omitted.")
    args = parser.parse_args(argv)

    manifest, summaries = audit_question_agent_output(
        question_agent_output=args.question_agent_output,
        protocol_registry_path=args.protocol_registry,
        limit=args.limit,
    )
    payload = {
        "manifest": manifest,
        "summaries": [item.model_dump(mode="json") for item in summaries],
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
