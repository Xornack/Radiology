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
                # Normalize case so mid-sentence "Colon" from Whisper doesn't
                # leak a stray capital; _autocap restores it at sentence starts.
                output.append(key)
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


def _tidy_spacing(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    return text.strip()


def _enforce_punctuation_spacing(text: str) -> str:
    """Guarantee a space follows . , ? when directly adjacent to a letter.

    The letter-only lookahead preserves decimals (7.5) and thousands
    separators (3,000). Runs after _substitute_tokens so dictated-token
    punctuation is untouched (already spaced), but protects against any
    path that leaves punctuation hugging the next word.
    """
    return re.sub(r"([.,?])(?=[A-Za-z])", r"\1 ", text)


def _autocap(text: str, capitalize_first: bool = True) -> str:
    """Capitalize alpha after ., ?, !, or blank line.

    When `capitalize_first` is True, also capitalize the first alpha of the
    string. When False, actively lowercase the first alpha so a mid-sentence
    continuation doesn't inherit Whisper's stray capital (e.g. "And" → "and"
    when appended after "the patient was examined").
    """
    if capitalize_first:
        text = re.sub(
            r"^(\s*)([a-z])",
            lambda m: m.group(1) + m.group(2).upper(),
            text,
        )
    else:
        text = re.sub(
            r"^(\s*)([A-Z])",
            lambda m: m.group(1) + m.group(2).lower(),
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


def apply_punctuation(
    text: str,
    capitalize_first: bool = True,
    strip_inferred: bool = True,
) -> str:
    """
    PowerScribe-style post-processor. Strips Whisper's auto-punctuation and
    replaces dictated tokens (period, comma, new paragraph, colon, ...) with
    the matching characters. Pure function; safe to call on live partials.

    `capitalize_first=False` disables the start-of-text capital so callers
    that treat this as a mid-sentence continuation (e.g. click-off/click-on
    dictation where the previous session didn't end with a terminator) can
    keep the first letter lowercase.

    `strip_inferred=False` skips the Whisper-punctuation stripper for STT
    engines that already emit real glyphs (MedASR). Token substitution +
    spacing + autocap still run so dictated-word punctuation and capital
    conventions stay consistent across engines.
    """
    if not text:
        return text
    if strip_inferred:
        text = _strip_whisper_punctuation(text)
    text = _substitute_tokens(text)
    text = _tidy_spacing(text)
    text = _enforce_punctuation_spacing(text)
    text = _autocap(text, capitalize_first=capitalize_first)
    return text
