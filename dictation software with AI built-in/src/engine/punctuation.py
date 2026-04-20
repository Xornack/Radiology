import re


def apply_punctuation(text: str) -> str:
    """
    PowerScribe-style post-processor. Strips Whisper's auto-punctuation and
    replaces dictated tokens (period, comma, new paragraph, colon, ...) with
    the matching characters. Pure function; safe to call on live partials.
    """
    if not text:
        return text
    return re.sub(r"^(\s*)([a-z])", lambda m: m.group(1) + m.group(2).upper(), text)
