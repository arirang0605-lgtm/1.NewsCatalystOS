"""One-shot, read-only verification. No API calls, no EraLeader mutations."""
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from newscatalystos.verified_reference import verify_official_research_reference


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--era-root", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--reference-sha256", required=True,
                        help="SHA256 previously preserved via a separate trusted channel")
    parser.add_argument("--decision-at", required=True,
                        help="ISO 8601 timezone-aware time of research decision")
    opts = parser.parse_args()
    result = verify_official_research_reference(
        opts.era_root, opts.reference, opts.reference_sha256,
        datetime.fromisoformat(opts.decision_at.replace("Z", "+00:00")))
    print("RESEARCH_ONLY VERIFIED_SOURCE_COUNT", len(result.captures))
    for row in sorted(result.captures, key=lambda item: item.source_id):
        print(row.source_id, "raw_observations", row.observed_count,
              "metadata_records", len(row.records), "quality", row.quality)
    print("NO_RELEASE_TIME_PROOF NO_ISSUER_ATTESTATION NO_AUTO_PROMOTION")


if __name__ == "__main__":
    main()
