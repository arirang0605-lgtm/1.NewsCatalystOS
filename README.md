# NewsCatalystOS

Evidence-first economic news and disclosure analysis. V1.0 development is staged across 36 tasks (1_1–6_6); only the semiconductor industry is included for supply-chain validation.

**Current status (2026-10-15):** Core code paths are implemented for **36/36 tasks**. Operational readiness now requires a successful real pipeline run, a live AI response with cost records, source linkage, a backup restore, passing regression tests and no unresolved critical incidents. Human news review is not required; five trading sessions are a post-start observation goal. External consumer integration and off-device backup are follow-ups. See [current operating policy](docs/V1_RELEASE_POLICY_2026-10-15.md). Actual live AI generation remains pending; changing the policy does not create execution evidence.

## Development checkpoints

- `START_HERE_NEXT_CHAT.md` → `AGENTS.md` → `PROJECT_STATE.md` → `DECISIONS.md` → `NEXT_TASK.md`
- Detailed scope: `NewsCatalystOS_V1.0_상세개발명세_1_1-6_6.md`
- Developer execution instructions: `NewsCatalystOS_V1.0_CHAT_개발마스터프롬프트.md`
- Public repository boundary: `GITHUB_PUBLIC_POLICY.md`
- The first source metadata contract: `docs/1_1_SOURCE_SHARE_CONTRACT.md`
- Read-only existing EraLeader captures: `docs/1_1_ERA_CAPTURE_READONLY_INTEGRATION.md`

## Local targeted tests

```bash
python3 -m pytest -q tests/test_source_share.py
```

The 57 tests use only generated fixtures. Separately, the local read-only integration verified five previously captured EraLeader official API sources using SHA-pinned research records. This is **not** independent publication-time certification, a new live API authentication test, or operational readiness.

## Privacy and scope

The `.gitignore` prevents most common raw API evidence, credentials, local databases, caches, backups and logs from being staged accidentally. Public commits additionally require explicit file-by-file staging and content review. Never put API keys, source receipts containing restricted materials, or paid news articles in public Git. No license is selected simply because the repository is public.
