import re
from src.utils.config import PHI_PATTERNS

def scrub_text(text: str) -> str:
    """
    Replaces PHI (Patient Names, MRNs, Dates) with placeholders.
    """
    scrubbed = text
    for pattern, replacement in PHI_PATTERNS.items():
        scrubbed = re.sub(pattern, replacement, scrubbed)
    return scrubbed
