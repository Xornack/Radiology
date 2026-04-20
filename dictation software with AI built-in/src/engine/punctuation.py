import re


_DOT_STRIP_RE = re.compile(r"(?<!\d)\.(?!\d)")
_OTHER_STRIP_RE = re.compile(r"[,?!;:]")


_MULTI_WORD_MAP = {
    "question mark": "?",
    "exclamation point": "!",
    "exclamation mark": "!",
    "new paragraph": "\n\n",
    "next paragraph": "\n\n",
    "new line": "\n",
    "open paren": "(",
    "open parenthesis": "(",
    "close paren": ")",
    "close parenthesis": ")",
    "open quote": "\u201c",
    "close quote": "\u201d",
}


_COLON_ANATOMY_BEFORE = {
    "transverse", "sigmoid", "ascending", "descending",
    "distal", "proximal", "hepatic", "splenic",
    "rectosigmoid", "right", "left", "entire", "intra",
}

_COLON_ANATOMY_AFTER = {
    "cancer", "polyp", "polyps", "mass", "wall", "lumen",
    "mucosa", "stricture", "diverticulosis", "diverticulitis",
    "stenosis", "obstruction", "perforation", "resection",
    "carcinoma", "neoplasm", "tumor", "tumour", "lesion", "lesions",
}


_SINGLE_WORD_MAP = {
    "period": ".",
    "comma": ",",
    "semicolon": ";",
    "semi-colon": ";",
    "hyphen": "-",
    "dash": " \u2014 ",
}


def _strip_whisper_punctuation(text: str) -> str:
    """Remove Whisper-inferred punctuation. Preserves decimals and apostrophes."""
    text = _DOT_STRIP_RE.sub("", text)
    text = _OTHER_STRIP_RE.sub("", text)
    return text


def _substitute_tokens(text: str) -> str:
    """Replace multi-word and single-word spoken tokens with their characters."""
    words = text.split()
    output: list[str] = []
    i = 0
    while i < len(words):
        if i + 1 < len(words):
            pair = f"{words[i].lower()} {words[i + 1].lower()}"
            if pair in _MULTI_WORD_MAP:
                output.append(_MULTI_WORD_MAP[pair])
                i += 2
                continue
        key = words[i].lower()
        if key == "colon":
            prev_word = words[i - 1].lower() if i > 0 else ""
            next_word = words[i + 1].lower() if i + 1 < len(words) else ""
            if prev_word in _COLON_ANATOMY_BEFORE or next_word in _COLON_ANATOMY_AFTER:
                output.append(words[i])
            else:
                output.append(":")
            i += 1
            continue
        if key in _SINGLE_WORD_MAP:
            output.append(_SINGLE_WORD_MAP[key])
        else:
            output.append(words[i])
        i += 1
    joined = " ".join(output)
    joined = re.sub(r"\s+([.,!?;:)\u201d])", r"\1", joined)
    joined = re.sub(r"([(\u201c])\s+", r"\1", joined)
    joined = re.sub(r"[ \t]*\n[ \t]*", "\n", joined)
    return joined


def _autocap(text: str) -> str:
    """Capitalize first alpha of document, and first alpha after ., ?, !, or blank line."""
    text = re.sub(
        r"^(\s*)([a-z])",
        lambda m: m.group(1) + m.group(2).upper(),
        text,
    )
    text = re.sub(
        r"([.!?]\s+)([a-z])",
        lambda m: m.group(1) + m.group(2).upper(),
        text,
    )
    text = re.sub(
        r"(\n\n+)([a-z])",
        lambda m: m.group(1) + m.group(2).upper(),
        text,
    )
    return text


def apply_punctuation(text: str) -> str:
    """
    PowerScribe-style post-processor. Strips Whisper's auto-punctuation and
    replaces dictated tokens (period, comma, new paragraph, colon, ...) with
    the matching characters. Pure function; safe to call on live partials.
    """
    if not text:
        return text
    text = _strip_whisper_punctuation(text)
    text = _substitute_tokens(text)
    text = re.sub(r"[ \t]+", " ", text).strip()
    text = _autocap(text)
    return text
