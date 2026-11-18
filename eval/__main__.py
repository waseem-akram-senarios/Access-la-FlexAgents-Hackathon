"""CLI: python -m eval [--agent NAME] [--level N] [--tag TAG] [--out DIR]."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from eval.engine.gates import format_judgment_markdown, judge_report
from eval.engine.report import print_summary, write_html, write_json, write_markdown
from eval.engine.runner import EvalRunner


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Universal AI agent testing & evaluation (sandbox only)."
    )
    parser.add_argument("--agent", help="Filter by agent id")
    parser.add_argument("--level", type=int, help="Filter by level 1-7")
    parser.add_argument(
        "--staging-step",
        type=int,
        choices=[1, 2, 3, 4],
        help="Run scenarios for staging agent step 1-4",
    )
    parser.add_argument(
        "--tag",
        action="append",
        default=[],
        help="Filter by tag (repeatable)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("eval/reports"),
        help="Report output directory",
    )
    parser.add_argument(
        "--fail-on-critical",
        action="store_true",
        default=True,
        help="Exit non-zero on critical failures (default)",
    )
    parser.add_argument(
        "--no-fail-on-critical",
        action="store_false",
        dest="fail_on_critical",
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=0.0,
        help="Exit non-zero if overall score is below this",
    )
    parser.add_argument(
        "--judge",
        action="store_true",
        help="Apply team L1-L7 go/no-go criteria and write judgment report",
    )
    args = parser.parse_args(argv)

    agent_filter = args.agent
    if args.staging_step:
        step_agents = {
            1: "answer_policy",
            2: "find_department",
            3: "log_case",
            4: "book_callback",
        }
        agent_filter = agent_filter or step_agents[args.staging_step]

    report = EvalRunner().run(
        agent_filter=agent_filter,
        level_filter=args.level,
        tags=args.tag or None,
    )
    args.out.mkdir(parents=True, exist_ok=True)
    json_path = write_json(report, args.out / "latest.json")
    md_path = write_markdown(report, args.out / "latest.md")
    html_path = write_html(report, args.out / "latest.html")
    print_summary(report)
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"Wrote {html_path}")

    if args.judge:
        from pathlib import Path as _Path

        has_ci = _Path(".github/workflows/ci.yml").is_file()
        judgment = judge_report(report, has_ci=has_ci)
        judge_json = args.out / "judgment.json"
        judge_md = args.out / "judgment.md"
        judge_json.write_text(
            __import__("json").dumps(judgment, indent=2), encoding="utf-8"
        )
        judge_md.write_text(format_judgment_markdown(judgment), encoding="utf-8")
        print(f"Wrote {judge_json}")
        print(f"Wrote {judge_md}")
        print(
            f"Best by your L1–L7 gates: {judgment.get('best_agent')} "
            f"({judgment.get('best_overall')})"
        )
        for j in judgment["judgments"]:
            gate_bits = " ".join(
                f"L{g['level']}={g['status']}" for g in j["gates"]
            )
            print(
                f"  {j['agent']}: {j['overall']} "
                f"({j['passed_gates']}/7 pass) {gate_bits}"
            )

    if args.fail_on_critical and report.critical_failures:
        return 2
    if report.overall_score < args.min_score:
        return 3
    if report.failed:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
