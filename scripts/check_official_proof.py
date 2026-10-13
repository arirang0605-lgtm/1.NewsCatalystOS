"""Run the 1_1 actual-proof gate, WITHOUT collecting any DART/SEC/KRX data.

With only --era-root/--reference/--anchor, verify the existing pinned official
captures and return DATA_UNAVAILABLE (exit 4) until independent issuer/release
attestation is supplied. This is NOT an issuer certification or a notary.

With all witness fields, validate out-of-band evidence against the original
EraLeader read-only capture using authenticate_from_era_readonly. Never copy
proofs or raw evidence into public Git or print their contents.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from newscatalystos.official_promotion import authenticate_from_era_readonly
from newscatalystos.pin_anchor import verify_with_local_anchor
from newscatalystos.source_share import SourceShareError, _read_regular, _when
from newscatalystos.witness_registry import load_operator_witness

PROOF_FIELDS = (
    "source_id", "document_id", "claim", "claim_sha256", "attestation",
    "signature", "witness_key", "witness_id",
)
MAX_CLAIM = 8192
MAX_ATTESTATION = 8192


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--era-root", type=Path, required=True)
    command.add_argument("--reference", type=Path, required=True)
    command.add_argument("--anchor", type=Path, required=True)
    command.add_argument("--decision-at", help="Timezone-aware ISO time; default now")
    command.add_argument("--source-id", choices=["dart-disclosures", "sec-submissions"])
    command.add_argument("--document-id")
    command.add_argument("--claim", type=Path)
    command.add_argument("--claim-sha256")
    command.add_argument("--attestation", type=Path)
    command.add_argument("--signature", type=Path)
    command.add_argument("--witness-key", type=Path)
    command.add_argument("--witness-id")
    return command


def evaluate(args: argparse.Namespace, *, now: datetime | None = None) -> tuple[int, dict]:
    """Return (exit status, non-sensitive structured result); never writes."""
    instant = now or datetime.now(timezone.utc)
    decision = _when(args.decision_at or instant.isoformat(), "decision_at")
    if decision > instant:
        raise SourceShareError("future decision")
    configured = [name for name in PROOF_FIELDS if getattr(args, name) is not None]
    if len(configured) != len(PROOF_FIELDS):
        # Probe only the existing completed EraLeader captures when evidence
        # is absent. A full proof path uses the wrapper below exactly once.
        verified = verify_with_local_anchor(
            args.era_root, args.reference, args.anchor, decision
        )
        return 4, {
            "status": "DATA_UNAVAILABLE",
            "verified_capture_count": len(verified.captures),
            "certified_raw_event_count": 0,
            "reason": ("INDEPENDENT_RELEASE_ATTESTATION_NOT_PROVIDED"
                       if not configured else "INCOMPLETE_INDEPENDENT_WITNESS_INPUT"),
        }

    # Never trust a public-key hash that arrived in the same proof package.
    registered = load_operator_witness(
        args.era_root, args.witness_id, args.source_id, decision, now=instant
    )
    claim = _read_regular(args.claim, MAX_CLAIM)
    attestation = _read_regular(args.attestation, MAX_ATTESTATION)
    signature = _read_regular(args.signature, 128)
    witness_key = _read_regular(args.witness_key, 4096)
    result = authenticate_from_era_readonly(
        args.era_root, args.reference, args.anchor,
        args.source_id, args.document_id,
        claim, args.claim_sha256,
        attestation, signature, witness_key,
        registered.public_key_sha256, registered.witness_id, decision, now=instant,
    )
    event = result.as_of(decision, now=instant)
    return 0, {
        "status": "SIGNED_PROOF_GATE_PASS",
        "certified_raw_event_count": 1,
        "provider_id": event.provider_id,
        "usable_from": result.usable_from.isoformat(),
        "note": "Witness authority and publication facts require independent audit.",
    }


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        code, report = evaluate(args)
    except (SourceShareError, ValueError, OSError) as exc:
        code = 4
        # Error names only: never leak private file paths or proof contents.
        report = {
            "status": "DATA_UNAVAILABLE",
            "certified_raw_event_count": 0,
            "reason": "PROOF_OR_SOURCE_VERIFICATION_FAILED",
            "error_type": type(exc).__name__,
        }
    print(json.dumps(report, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
