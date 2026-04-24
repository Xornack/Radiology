import re
from src.utils.config import PHI_PATTERNS

# Precompile at import time — this module is hit on every streaming tick
# and every post-Stop transcript, so per-call re.compile() shows up in
# profiles. Order is preserved because PHI_PATTERNS is a dict (Python 3.7+
# dicts are ordered) and more specific patterns must match before generic
# ones (e.g. MRN before bare number).
_COMPILED_PHI_PATTERNS = [
    (re.compile(pattern), replacement)
    for pattern, replacement in PHI_PATTERNS.items()
]


def scrub_text(text: str) -> str:
    """
    Replaces PHI (Patient Names, MRNs, Dates) with placeholders.
    """
    scrubbed = text
    for pattern, replacement in _COMPILED_PHI_PATTERNS:
        scrubbed = pattern.sub(replacement, scrubbed)
    return scrubbed
