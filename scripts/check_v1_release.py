"""6_6 produce a release BLOCKER report; never tag/push a release itself.

--completed accepts comma-separated task IDs from the locally audited state
file. Missing real validation evidence remains unavailable by default.
"""
from __future__ import annotations

import argparse
import json

from newscatalystos.release_readiness import ReadinessInputs, evaluate_v1_readiness
from newscatalystos.source_share import SourceShareError


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--completed",default="",
                        help="comma-separated task IDs, e.g. 1_1,1_2 (not proof)")
    args=parser.parse_args(argv)
    try:
        names=tuple(x.strip() for x in args.completed.split(",") if x.strip())
        result=evaluate_v1_readiness(ReadinessInputs(completed_tasks=names))
        report={
            "status":result.status,"done":result.completed_tasks,
            "total":result.total_tasks,
            "missing_task_ids":result.missing_tasks,
            "release_blockers":result.blockers,
            "verified_release":result.independently_release_certified,
            "v1_git_tag_authorized":result.permitted_to_tag_v1,
        }
    except SourceShareError as exc:
        report={"status":"DATA_UNAVAILABLE","error_type":type(exc).__name__,
                "v1_git_tag_authorized":False}
    print(json.dumps(report,ensure_ascii=False,sort_keys=True))
    return 4


if __name__ == "__main__":
    raise SystemExit(main())
