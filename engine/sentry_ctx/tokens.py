"""Official Sentry credential formats (https://docs.sentry.io/security-legal-pii/security/token-formats/)
and masking. DSNs are public and are never treated as secrets."""
from __future__ import annotations

import re

# Prefixed formats identify themselves. Organization tokens are ~180-250 chars, so no fixed length.
PREFIXED = [
    ("user", re.compile(r"sntryu_[a-f0-9]{64}")),
    ("org", re.compile(r"sntrys_[A-Za-z0-9+/=]+_[A-Za-z0-9+/]{43}")),
    ("reserved", re.compile(r"sntry[ai]_[a-f0-9]{64}")),
]
# A bare 64-hex string is only a credential next to one of these names.
CONTEXT_HEX = re.compile(
    r"(?i)(SENTRY_AUTH_TOKEN|SENTRY_TOKEN|authToken|auth\.token|auth_token|client_secret)"
    r"""["']?\s*[:=]\s*["']?([a-f0-9]{64})\b"""
)
DSN = re.compile(r"https?://[a-f0-9]{32}@[^/\s\"']+/\d+")
ANY_PREFIXED = re.compile(r"sntry[usai]_[A-Za-z0-9+/=_-]{16,}")
# Any prefixed credential is masked even when truncated (a clipped token must not leak its head).
MASK_RE = re.compile(
    r"(sntry[usai]_[A-Za-z0-9+/=_-]{8,})"
    r"""|((?i:SENTRY_AUTH_TOKEN|SENTRY_TOKEN|authToken|auth\.token|auth_token|client_secret)["']?\s*[:=]\s*["']?)([a-f0-9]{64})\b"""
)


def _mask_match(m: "re.Match[str]") -> str:
    if m.group(1):
        return m.group(1)[:7] + "****"
    return m.group(2) + "****"


def mask(text: str) -> str:
    """Replace credential-shaped substrings with a short prefix and ****."""
    if not text:
        return text
    return MASK_RE.sub(_mask_match, text)


def clip(text: str, n: int) -> str:
    """Mask first, then truncate: truncating first would cut a token below the pattern and leak its head."""
    return mask(text)[:n]


def find_tokens(text: str):
    """Yield (kind, start, end) for credential-shaped substrings; DSNs excluded."""
    for kind, rx in PREFIXED:
        for m in rx.finditer(text):
            yield kind, m.start(), m.end()
    for m in CONTEXT_HEX.finditer(text):
        yield "hex-context", m.start(2), m.end(2)


def has_token(text: str) -> bool:
    for _ in find_tokens(text):
        return True
    return False


def mask_deep(obj):
    if isinstance(obj, str):
        return mask(obj)
    if isinstance(obj, list):
        return [mask_deep(x) for x in obj]
    if isinstance(obj, dict):
        return {k: mask_deep(v) for k, v in obj.items()}
    return obj
