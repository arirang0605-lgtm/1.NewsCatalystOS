# NewsCatalystOS 1_5 → 2_2 implementation and verification

## 1_5 Immutable evidence receipts
- `evidence_archive.py`: privately store **only operator-approved metadata** or source bytes when explicitly licensed for original storage. The root must be owner-only (0700), files 0600; each immutable revision uses SHA-derived identity, payload SHA, receipt SHA, initial verification time and actual archive-created time. Same version is idempotent; a correction references its prior version instead of overwriting it.
- Historical replay checks `archived_at`, not just earlier source receipt, so a file archived now cannot be treated as archived yesterday. Hash mismatches, symlinks, path escapes, missing permission, future timestamps and changes to correction chain are rejected.
- Real owner-private configuration / real Mac local filesystem **synthetic metadata-only smoke test PASS**. No actual copyrighted article body or EraLeader original stored. Synthetic local receipt is not an external notarization.

## 1_6 Collection quality watcher
- `quality_watch.py` and `scripts/check_feed_quality.py`: report provider state `HEALTHY`, `STALE`, `NOT_COLLECTED`, `RETRY_PENDING`, `AUTH_BLOCKED` or `NOT_AUTHORIZED`; track first report and resolution of pending incidents in an isolated NewsCatalystOS SQLite table, no sensitive raw data.
- Empty source responses cannot advance the success watermark. Later permitted 1_3 retry can recover a failed source without replacing prior successful evidence. The private Mac data check for two approved providers reported HEALTHY/CLEAR, pending incidents 0; an actual multi-day outage was not simulated live, but fault-injection tests cover 403, 429, staleness, no capture and recovery.

## 2_1 Deterministic normalization
- `text_normalization.py`: decode bounded UTF-8, remove active markup, normalize NFKC/whitespace and safe URL tracking parameters; preserve official document-ID query keys. Expose raw SHA and actual verified time. Never alter original source bytes or infer company IDs, published time, source independence or market impact. Synthesized authorized feed tests cover deterministic replay/HTML/unsafe URL/PIT.

## 2_2 Exact dedup and revisions
- `exact_dedup.py`: private SHA-only SQLite index keyed by source ID, document fingerprint and title digest. First record NEW, exact repeat DUPLICATE (AI-ineligible), same document with changed digest REVISED (eligible and prior record preserved). Duplicate aliases of same URL+digest within a source are suppressed, but separate providers are not silently treated as a single independent fact. New/changed stories remain subject to later provenance/event cluster filtering.
- Tests use synthetic sources and deterministic data. Real 5-trading-day deployment, human gold-label duplicate precision and source provenance checks remain later V1.0 gates. No AI APIs were called.

## Evidence and boundaries
- All implementation runs on `/Volumes/T5DATA/1.NewsCatalystOS`; EraLeader code/DB/Git/DART/SEC/KRX collectors are untouched. Private receipts, databases, credentials, copyrighted source bodies and backups are excluded from GitHub Public.
- Remaining: 2_3 event similarity clustering; 2_4 ads/rumors; 2_5 source independence; 2_6 labeled evaluation (95% duplicate precision plus missed important cases), then 3_1–6_6, semiconductor live validation, five trading days, release gates. Do not infer a full 36/36 result from these unit tests.
