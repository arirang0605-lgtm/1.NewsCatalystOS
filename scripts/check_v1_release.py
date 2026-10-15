"""Check operational readiness; exit 0 when required execution checks pass.

--evidence accepts a JSON object with ReadinessInputs fields populated from real
run reports. The command evaluates supplied results; it does not independently
authenticate them, create a tag or deploy. Missing results remain incomplete.
"""
from __future__ import annotations

import argparse
from dataclasses import fields
import json
from pathlib import Path

from newscatalystos.release_readiness import ReadinessInputs, evaluate_v1_readiness
from newscatalystos.source_share import SourceShareError


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--completed",default=None,
                        help="comma-separated task IDs, e.g. 1_1,1_2 (not proof)")
    parser.add_argument("--evidence", type=Path,
                        help="JSON execution results using ReadinessInputs fields")
    args=parser.parse_args(argv)
    try:
        data = {}
        if args.evidence is not None:
            with args.evidence.open("rb") as stream:
                raw = stream.read(65537)
            if len(raw) > 65536:
                raise SourceShareError("execution report too large")
            data = json.loads(raw)
            if not isinstance(data, dict) or set(data) - {f.name for f in fields(ReadinessInputs)}:
                raise SourceShareError("unknown execution report fields")
        if args.completed is not None:
            data["completed_tasks"] = tuple(x.strip() for x in args.completed.split(",") if x.strip())
        result=evaluate_v1_readiness(ReadinessInputs(**data))
        report={
            "status":result.status,"done":result.completed_tasks,
            "total":result.total_tasks,
            "missing_task_ids":result.missing_tasks,
            "release_blockers":result.blockers,
            "operation_ready":result.operation_ready,
            "follow_ups":result.follow_ups,
            "evidence_basis":"SUPPLIED_EXECUTION_RESULTS",
            "verified_release":result.independently_release_certified,
            "v1_git_tag_authorized":result.permitted_to_tag_v1,
        }
        code = 0 if result.operation_ready else 4
    except (SourceShareError, OSError, ValueError, TypeError) as exc:
        code = 4
        report={"status":"DATA_UNAVAILABLE","error_type":type(exc).__name__,
                "v1_git_tag_authorized":False}
    print(json.dumps(report,ensure_ascii=False,sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
