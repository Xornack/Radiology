import re


_DOT_STRIP_RE = re.compile(r"(?<!\d)\.(?!\d)")
_OTHER_STRIP_RE = re.compile(r"[,?!;:]")


def _strip_whisper_punctuation(text: str) -> str:
    """Remove Whisper-inferred punctuation. Preserves decimals and apostrophes."""
    text = _DOT_STRIP_RE.sub("", text)
    text = _OTHER_STRIP_RE.sub("", text)
    return text


def _autocap_first_letter(text: str) -> str:
    return re.sub(
        r"^(\s*)([a-z])",
        lambda m: m.group(1) + m.group(2).upper(),
        text,
    )


def apply_punctuation(text: str) -> str:
    """
    PowerScribe-style post-processor. Strips Whisper's auto-punctuation and
    replaces dictated tokens (period, comma, new paragraph, colon, ...) with
    the matching characters. Pure function; safe to call on live partials.
    """
    if not text:
        return text
    text = _strip_whisper_punctuation(text)
    text = re.sub(r"[ \t]+", " ", text).strip()
    text = _autocap_first_letter(text)
    return text
