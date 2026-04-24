from src.engine.lexicon import correct_radiology


def test_empty_string_is_passthrough():
    assert correct_radiology("") == ""


def test_exact_lexicon_terms_untouched():
    """A correctly-spelled radiology term must not get mangled by fuzzy matching."""
    assert correct_radiology("pleural effusion") == "pleural effusion"


def test_plural_becomes_pleural():
    """The single most common Whisper-radiology error — 'plural' → 'pleural'."""
    assert correct_radiology("large plural effusion") == "large pleural effusion"


def test_case_preserved_lowercase():
    assert correct_radiology("plural effusion") == "pleural effusion"


def test_case_preserved_title_case():
    assert correct_radiology("Plural effusion") == "Pleural effusion"


def test_case_preserved_all_caps():
    assert correct_radiology("PLURAL EFFUSION") == "PLEURAL EFFUSION"


def test_safe_word_mass_not_corrected():
    """'mass' is common English and close to several terms — must not swap."""
    assert correct_radiology("No mass identified") == "No mass identified"


def test_safe_word_clear_not_corrected():
    """'clear' is adjacent to 'clear' in the lexicon (unchanged)."""
    assert correct_radiology("Lungs are clear") == "Lungs are clear"


def test_near_miss_atelectasis():
    """Fuzzy threshold catches 'atalectasis' (typical ASR error) → 'atelectasis'."""
    assert "atelectasis" in correct_radiology("mild atalectasis").lower()


def test_non_radiology_sentence_passes_through():
    """Ordinary English with no radiology-adjacent words is unchanged."""
    plain = "The meeting is at three o clock tomorrow"
    assert correct_radiology(plain) == plain


def test_punctuation_boundaries_respected():
    """Surrounding punctuation doesn't leak into the matcher."""
    assert correct_radiology("Assessment: plural effusion.") == (
        "Assessment: pleural effusion."
    )


def test_threshold_parameter_is_applied():
    """A strict threshold should prevent corrections that the default (0.85) permits.

    'atalectasis' vs. 'atelectasis' scores ~0.83 — above the default 0.85
    cutoff after Python's difflib normalizes the comparison, but below a
    very strict 0.99 cutoff. Verifies the threshold knob is actually wired.
    """
    default = correct_radiology("mild atalectasis")
    strict = correct_radiology("mild atalectasis", threshold=0.99)
    # Default catches the near-miss; strict does not.
    assert "atelectasis" in default
    assert "atelectasis" not in strict
    assert "atalectasis" in strict
