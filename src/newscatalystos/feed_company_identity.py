"""Exact RSS title names -> existing pinned filing identities; no source polling.

The cache binds title/event/URL and directory version. Its first decision time
is retained on replay; a changed directory produces a new observation today.
Identity is source context, never confirmation of a reported transaction.
"""
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path

from .article_company_identity import (
    encoded, resolve_names, validate_name_results, RESOLVER_VERSION, MAX_BYTES,
)
from .economic_changes import mentions_name
from .evidence_archive import _private_root, _read_once, _write_new
from .source_share import SourceShareError, _json, _must_sha, _when

SCHEMA = 'newscatalyst.feed_company_identity.v1'
BINDING_KEYS = ('provider_id', 'source_event_sha256', 'source_title_sha256',
                'source_url', 'source_available_at')


def load_directory(config, *, now):
    from .official_filing_context import read_pinned_filing_context
    settings = _json(_read_once(Path(config), 8192), 'company identity configuration')
    if not isinstance(settings, dict) or set(settings) != {'era_root', 'era_report', 'independent_anchor'}:
        raise SourceShareError('invalid company identity configuration')
    paths = {k: Path(v) for k, v in settings.items()}
    if any(not p.is_absolute() or '..' in p.parts for p in paths.values()):
        raise SourceShareError('absolute filing snapshot paths required')
    return read_pinned_filing_context(paths['era_root'], paths['era_report'],
                                      paths['independent_anchor'], now=now)


def validate_feed_identity(identity, row, *, at):
    keys = set(BINDING_KEYS) | ({'normalized_headline_sha256'} if 'normalized_headline_sha256' in identity else set()) | {'schema', 'directory_sha256', 'resolver_version', 'decision_at',
        'matches', 'unresolved', 'evidence_level', 'verified_real_transaction', 'verified_real_benefit'}
    if (not isinstance(identity, dict) or set(identity) != keys
            or identity['schema'] != SCHEMA or identity['resolver_version'] != RESOLVER_VERSION
            or identity['evidence_level'] != 'SOURCE_REPORTED_IDENTITY'
            or identity['verified_real_transaction'] is not False
            or identity['verified_real_benefit'] is not False
            or any(identity[k] != row[k] for k in BINDING_KEYS)):
        raise SourceShareError('RSS company identity binding mismatch')
    for key in ('source_event_sha256', 'source_title_sha256', 'directory_sha256'):
        _must_sha(identity[key], key)
    # Source title SHA pins the pre-normalization title; the displayed headline
    # has HTML/whitespace normalization. Bind both without equating their bytes.
    headline_sha = identity.get('normalized_headline_sha256', identity['source_title_sha256'])
    _must_sha(headline_sha, 'normalized headline')
    if sha256(row['headline'].encode()).hexdigest() != headline_sha:
        raise SourceShareError('RSS identity title SHA mismatch')
    decision = _when(identity['decision_at'], 'identity decision')
    if not _when(identity['source_available_at'], 'source available') <= decision <= at:
        raise SourceShareError('RSS company identity unavailable at decision')
    validate_name_results(identity['matches'], identity['unresolved'], decision)
    if any(not mentions_name(row['headline'], r['source_name'])
           for r in identity['matches'] + identity['unresolved']):
        raise SourceShareError('company name absent from RSS title')


def ensure_feed_identity(item, contexts, root, *, at):
    # Match directory names only: no guessing an issuer from a prefix or suffix.
    names = {r.issuer_name_observed for r in contexts.values()
             if mentions_name(item['headline'], r.issuer_name_observed)}
    if len(names) > 100:
        raise SourceShareError('too many RSS company names')
    matches, unresolved = resolve_names(names, contexts, at=at)
    directory = []
    for row in contexts.values():
        fields = asdict(row)
        fields.pop('local_context_verified_at')
        directory.append(fields)
    fingerprint = sha256(encoded(sorted(directory,
        key=lambda r: (r['source_id'], r['document_id'])))).hexdigest()
    binding = dict(provider_id=item['provider_id'], source_event_sha256=item['event_id'],
        source_title_sha256=item['title_sha256'], source_url=item['canonical_url'],
        source_available_at=item['available_at'])
    key = {**binding, 'directory_sha256': fingerprint, 'resolver_version': RESOLVER_VERSION,
           'normalized_headline_sha256': sha256(item['headline'].encode()).hexdigest()}
    path = _private_root(root) / ('feed_identity_' + sha256(encoded(key)).hexdigest() + '.json')
    source = {**binding, 'headline': item['headline']}
    if path.exists():
        saved = _json(_read_once(path, MAX_BYTES), 'cached RSS identity')
        identity = saved['identity']
        if (saved.get('sha256') != sha256(encoded(identity)).hexdigest()
                or any(identity[k] != v for k, v in key.items())):
            raise SourceShareError('RSS identity cache mismatch')
        validate_feed_identity(identity, source, at=at)
        return identity
    identity = {**key, 'schema': SCHEMA, 'decision_at': at.isoformat(),
        'matches': matches, 'unresolved': unresolved, 'evidence_level': 'SOURCE_REPORTED_IDENTITY',
        'verified_real_transaction': False, 'verified_real_benefit': False}
    validate_feed_identity(identity, source, at=at)
    raw = encoded({'identity': identity, 'sha256': sha256(encoded(identity)).hexdigest()})
    if len(raw) > MAX_BYTES:
        raise SourceShareError('oversized RSS identity')
    try:
        _write_new(path, raw)
    except FileExistsError:
        # Another scheduler won this exact version; retain its first decision.
        return ensure_feed_identity(item, contexts, root, at=at)
    return identity
