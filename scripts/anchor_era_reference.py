"""Store / consume EraLeader research SHA on Mac internal disk (local TOFU only).

No direct DART/SEC/KRX calls, raw content copies, or EraLeader writes.
Never use this anchor to claim earlier verified publication timestamps.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from newscatalystos.pin_anchor import (
    ANCHOR_FILENAME, create_local_reference_anchor,
    verify_with_local_anchor, read_local_reference_anchor,
)
from newscatalystos.official_normalization import normalize_official_capture


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--era-root", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--create", action="store_true",
                        help="one-time trust-on-first-use pin; refuses overwrite")
    args = parser.parse_args()
    private_dir = (Path.home() / "Library" / "Application Support" /
                   "NewsCatalystOS" / "pins")
    # Never use shared SSD or GitHub project directory for this anchor.
    if args.create:
        private_dir.mkdir(parents=True, mode=0o700, exist_ok=True)
    target = private_dir / ANCHOR_FILENAME
    if args.create:
        pin = create_local_reference_anchor(args.era_root, args.reference, target)
        print("LOCAL_TOFU_PIN_CREATED", pin.report_sha256[:16],
              "NO_EXTERNAL_TIMESTAMP_ATTESTATION")
    when = datetime.now(timezone.utc)
    pin = read_local_reference_anchor(args.era_root, args.reference, target, when)
    batch = verify_with_local_anchor(args.era_root, args.reference, target, when)
    candidates = tuple(item for capture in batch.captures
                       for item in normalize_official_capture(capture, when))
    if any(item.verified_published_at is not None for item in candidates):
        raise RuntimeError("unverified release promoted")
    print("PIN_VERIFIED_RESEARCH_ONLY", "sources", len(batch.captures),
          "metadata_candidates", len(candidates))
    print("UNVERIFIED_RELEASE_AT NONE; RAW_EVENT_PROMOTION_FORBIDDEN")


if __name__ == "__main__":
    main()
