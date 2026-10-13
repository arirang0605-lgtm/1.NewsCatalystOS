"""1_2 operator-approved new-source registry. No network, no EraLeader overlap.

Every URL and rights statement is operator-supplied metadata, NOT automatically
verified legal permission. Unless permission is explicitly reviewed, never
activate collection. This module does not download articles or register keys.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from ipaddress import ip_address
from urllib.parse import parse_qsl, urlsplit

from .source_share import SourceShareError, _json, _must_id, _when

SCHEMA = "newscatalyst.provider_registry.v1"
TYPES = frozenset({"GOVERNMENT_POLICY", "COMPANY_IR", "LICENSED_NEWS", "SNS_TIP"})
METHODS = frozenset({"RSS", "JSON_API"})
GRANTS = frozenset({"OFFICIAL_TERMS_REVIEWED", "WRITTEN_LICENSE", "NOT_REVIEWED"})
RESERVED = frozenset({
    "dart-disclosures", "sec-submissions", "sec-companyfacts",
    "krx-kospi", "krx-kosdaq", "dart", "sec", "krx",
})
FIELDS = frozenset({"schema", "providers"})
PROVIDER_FIELDS = frozenset({
    "provider_id", "kind", "method", "endpoint", "grant",
    "rights_reference", "reviewed_at", "expires_at", "approved",
    "allow_full_text_storage", "hourly_limit",
})
MAX_BYTES = 32768


def _safe_https_endpoint(text: object) -> str:
    if not isinstance(text, str) or len(text) > 2048 or any(
        ord(c) < 33 or ord(c) == 127 for c in text
    ):
        raise SourceShareError("invalid provider endpoint")
    try:
        uri = urlsplit(text)
        host = uri.hostname
        port = uri.port
    except ValueError as exc:
        raise SourceShareError("malformed provider endpoint") from exc
    if (uri.scheme != "https" or not host or uri.username or uri.password
            or uri.fragment or port is not None):
        raise SourceShareError("provider endpoint must be HTTPS without credentials")
    # Government RSS/article links commonly require non-secret query IDs.
    # Never let credentials creep into Public configs or logged URLs.
    forbidden = {"token", "api_key", "apikey", "servicekey", "access_token",
                 "secret", "password", "authorization", "auth", "key"}
    if any(key.lower() in forbidden for key, _ in parse_qsl(uri.query, keep_blank_values=True)):
        raise SourceShareError("provider endpoint cannot embed API credentials")
    if host in ("localhost", "localhost.localdomain") or host.endswith(".local"):
        raise SourceShareError("local provider endpoint not permitted")
    try:
        ip_address(host.strip("[]"))
    except ValueError:
        pass
    else:
        raise SourceShareError("IP-literal provider endpoint not permitted")
    if "." not in host or host.startswith(".") or host.endswith("."):
        raise SourceShareError("not a registered provider domain")
    return text


@dataclass(frozen=True)
class Provider:
    provider_id: str
    kind: str
    method: str
    endpoint: str
    grant: str
    rights_reference: str | None
    reviewed_at: datetime | None
    expires_at: datetime | None
    approved: bool
    allow_full_text_storage: bool
    hourly_limit: int

    def enabled_at(self, at: datetime) -> bool:
        return (
            self.approved and self.grant != "NOT_REVIEWED"
            and bool(self.rights_reference) and self.reviewed_at is not None
            and self.reviewed_at <= at
            and (self.expires_at is None or at < self.expires_at)
            and self.kind != "SNS_TIP"
        )


@dataclass(frozen=True)
class ProviderRegistry:
    providers: tuple[Provider, ...]

    def active(self, provider_id: str, at: datetime | None = None) -> Provider:
        """Fail closed for missing, unapproved, expired, or SNS providers."""
        when = _when((at or datetime.now(timezone.utc)).isoformat(), "at")
        matches = [x for x in self.providers if x.provider_id == provider_id]
        if len(matches) != 1 or not matches[0].enabled_at(when):
            raise SourceShareError("provider not approved for ingestion")
        return matches[0]

    def approved_ids(self, at: datetime | None = None) -> tuple[str, ...]:
        when = _when((at or datetime.now(timezone.utc)).isoformat(), "at")
        return tuple(x.provider_id for x in self.providers if x.enabled_at(when))


def parse_provider_registry(data: bytes, *, now: datetime | None = None) -> ProviderRegistry:
    """Parse bounded operator configuration; default-deny on any ambiguity."""
    instant = _when((now or datetime.now(timezone.utc)).isoformat(), "now")
    if not isinstance(data, bytes) or not 0 < len(data) <= MAX_BYTES:
        raise SourceShareError("missing/bounded provider registry required")
    document = _json(data, "provider registry")
    if set(document) != FIELDS or document["schema"] != SCHEMA:
        raise SourceShareError("invalid provider registry schema")
    items = document["providers"]
    if not isinstance(items, list) or len(items) > 100:
        raise SourceShareError("invalid provider list")
    result = []
    seen = set()
    for row in items:
        if not isinstance(row, dict) or set(row) != PROVIDER_FIELDS:
            raise SourceShareError("invalid provider fields")
        name = _must_id(row["provider_id"], "provider_id")
        if name.lower() in RESERVED or name.lower().startswith(("eraleader", "krx-", "sec-", "dart-")):
            raise SourceShareError("duplicated EraLeader official collector")
        if name in seen:
            raise SourceShareError("duplicate provider")
        seen.add(name)
        kind, method, grant = row["kind"], row["method"], row["grant"]
        if kind not in TYPES or method not in METHODS or grant not in GRANTS:
            raise SourceShareError("invalid provider category/rights")
        endpoint = _safe_https_endpoint(row["endpoint"])
        permission = row["rights_reference"]
        if permission is not None and (not isinstance(permission, str)
                or not 0 < len(permission) <= 512):
            raise SourceShareError("invalid rights reference")
        reviewed = (_when(row["reviewed_at"], "reviewed_at")
                    if row["reviewed_at"] is not None else None)
        expires = (_when(row["expires_at"], "expires_at")
                   if row["expires_at"] is not None else None)
        if reviewed is not None and reviewed > instant:
            raise SourceShareError("future rights review")
        if expires is not None and reviewed is not None and expires <= reviewed:
            raise SourceShareError("license expires before review")
        approved = row["approved"]
        fulltext = row["allow_full_text_storage"]
        limit = row["hourly_limit"]
        if type(approved) is not bool or type(fulltext) is not bool or (
            type(limit) is not int or not 1 <= limit <= 10000
        ):
            raise SourceShareError("invalid provider permissions/rate limit")
        if approved and (grant == "NOT_REVIEWED" or not permission or reviewed is None
                         or kind == "SNS_TIP"):
            raise SourceShareError("unreviewed or social source cannot be active")
        if fulltext and (not approved or grant != "WRITTEN_LICENSE"):
            raise SourceShareError("full-text storage requires explicit written license")
        result.append(Provider(
            name, kind, method, endpoint, grant, permission, reviewed,
            expires, approved, fulltext, limit,
        ))
    return ProviderRegistry(tuple(result))
