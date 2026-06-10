from __future__ import annotations

import argparse
from pathlib import Path

from .cli import default_config_path
from .research_pipeline import ResearchPipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the auditable computational catalysis research pipeline skeleton."
    )
    parser.add_argument("--config", default=str(default_config_path()), help="Path to YAML config.")
    parser.add_argument(
        "--question-output",
        required=True,
        help="Existing QuestionDiscoveryWorkflow output directory containing question_cards/all_question_cards.json.",
    )
    parser.add_argument("--protocol-registry", default=None, help="Path to protocol registry YAML.")
    parser.add_argument("--scaffold-dir", default=None, help="Directory containing cloned GitHub scaffold repositories.")
    parser.add_argument("--output", default=None, help="Output directory for the research pipeline run.")
    parser.add_argument("--aiida-mode", default="dry_run", choices=["dry_run", "aiida"], help="Execution mode.")
    parser.add_argument("--max-questions", type=int, default=3, help="Maximum question cards to plan.")
    parser.add_argument(
        "--max-protocols-per-question",
        type=int,
        default=3,
        help="Maximum registered protocols to turn into dry-run calculation tasks per question.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    pipeline = ResearchPipeline(
        config_path=args.config,
        question_output_dir=args.question_output,
        protocol_registry_path=args.protocol_registry,
        scaffold_dir=args.scaffold_dir,
        aiida_mode=args.aiida_mode,
        max_questions=args.max_questions,
        max_protocols_per_question=args.max_protocols_per_question,
    )
    result = pipeline.run(output_dir=Path(args.output) if args.output else None)
    print("Mode: auditable research pipeline")
    print(f"Run id: {result.run_id}")
    print(f"Output dir: {result.output_dir}")
    print(f"Selected questions: {result.selected_question_count}")
    print(f"Structures: {result.structure_count}")
    print(f"Tasks: {result.task_count}")
    print(f"Claims: {result.claim_count}")
    print(f"Gate summary: {result.gate_summary}")
    print(f"External scaffolds present: {result.scaffold_count}")
    return 0
