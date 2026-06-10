from __future__ import annotations

import argparse
import json
from pathlib import Path

from .natural_request import NaturalLanguageRequestRunner
from .models import SourceCandidate
from .source_harvester import SourceHarvester
from .source_intake import SourceIntakeBuilder
from .workflow import QuestionDiscoveryWorkflow


def default_config_path() -> Path:
    return Path(__file__).resolve().parents[2] / "05_config_catalysis_question_agent.yaml"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the catalysis innovation and research-question discovery MVP workflow."
    )
    parser.add_argument(
        "--config",
        default=str(default_config_path()),
        help="Path to YAML config.",
    )
    parser.add_argument(
        "--input",
        action="append",
        default=[],
        help="Local md/txt/csv file or directory. Can be repeated.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output directory. Defaults to config output base_dir plus a run id.",
    )
    parser.add_argument(
        "--request",
        default=None,
        help="Natural-language research request. DeepSeek converts it into an isolated run config.",
    )
    parser.add_argument(
        "--request-file",
        default=None,
        help="Path to a text/markdown file containing a natural-language research request.",
    )
    parser.add_argument(
        "--harvest",
        action="store_true",
        help="Run source harvesting/triage only. This writes new_sources.csv and source_triage.md.",
    )
    parser.add_argument(
        "--harvest-workflow",
        action="store_true",
        help="Run source harvesting, build metadata intake stubs, then run the question workflow on those stubs.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum online results per registry query for --harvest.",
    )
    parser.add_argument(
        "--query",
        action="append",
        default=[],
        help="Extra harvest query. Can be repeated and is appended to every enabled registry source.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    request_text = args.request
    if args.request_file:
        request_text = Path(args.request_file).read_text(encoding="utf-8")

    if args.harvest_workflow:
        harvester = SourceHarvester(args.config)
        harvest_result = harvester.run(output_dir=args.output, limit=args.limit, extra_queries=args.query)
        harvest_dir = Path(harvest_result.output_dir)
        candidates = _read_harvest_candidates(harvest_dir / "new_sources.jsonl")
        stub_dir, _intake_files = SourceIntakeBuilder(harvester.config).build(candidates, harvest_dir / "intake")
        workflow_result = QuestionDiscoveryWorkflow(config_data=harvester.config).run(
            inputs=[stub_dir],
            output_dir=harvest_dir / "workflow",
        )
        print("Mode: source harvest + workflow")
        print(f"Harvest run id: {harvest_result.run_id}")
        print(f"Workflow run id: {workflow_result.run_id}")
        print(f"Output dir: {harvest_result.output_dir}")
        print(f"Candidates: {harvest_result.candidate_count}")
        print(f"Intake stubs: {len(list(stub_dir.glob('*.md')))}")
        print(f"Sources entering workflow: {workflow_result.source_count}")
        print(f"Evidence items: {workflow_result.evidence_count}")
        print(f"Question cards: {workflow_result.question_count_final}")
        print(f"Recommended: {workflow_result.recommended_count}")
        if harvest_result.errors:
            print(f"Harvest errors: {len(harvest_result.errors)}")
        return 0

    if args.harvest:
        harvester = SourceHarvester(args.config)
        result = harvester.run(output_dir=args.output, limit=args.limit, extra_queries=args.query)
        print("Mode: source harvest")
        print(f"Run id: {result.run_id}")
        print(f"Output dir: {result.output_dir}")
        print(f"Candidates: {result.candidate_count}")
        print(f"OA fulltext ready: {result.oa_ready_count}")
        print(f"Fulltext queue: {result.fulltext_queue_count}")
        print(f"Metadata watch: {result.metadata_watch_count}")
        if result.errors:
            print(f"Errors: {len(result.errors)}")
        return 0

    if request_text:
        runner = NaturalLanguageRequestRunner(args.config)
        result, _patch, out_dir = runner.run(request_text, output_dir=args.output)
        print("Mode: natural-language request")
        print(f"Request archive: {out_dir / 'request'}")
    else:
        workflow = QuestionDiscoveryWorkflow(args.config)
        result = workflow.run(inputs=args.input, output_dir=args.output)
        print("Mode: config")
    print(f"Run id: {result.run_id}")
    print(f"Output dir: {result.output_dir}")
    print(f"Sources: {result.source_count}")
    print(f"Evidence items: {result.evidence_count}")
    print(f"Question cards: {result.question_count_final}")
    print(f"Recommended: {result.recommended_count}")
    return 0


def _read_harvest_candidates(path: Path) -> list[SourceCandidate]:
    candidates: list[SourceCandidate] = []
    if not path.exists():
        return candidates
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            candidates.append(SourceCandidate.model_validate(json.loads(line)))
    return candidates
