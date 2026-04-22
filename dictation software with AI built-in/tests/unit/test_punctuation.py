from src.engine.punctuation import apply_punctuation, _enforce_punctuation_spacing


def test_empty_input_returns_empty():
    assert apply_punctuation("") == ""


def test_plain_text_gets_capitalized():
    assert apply_punctuation("the lungs are clear") == "The lungs are clear"


def test_strips_whisper_commas():
    assert apply_punctuation("the lungs, are clear") == "The lungs are clear"


def test_strips_whisper_periods():
    assert apply_punctuation("lungs clear. heart normal") == "Lungs clear heart normal"


def test_strips_whisper_question_and_exclamation():
    assert apply_punctuation("is it clear? yes!") == "Is it clear yes"


def test_strips_whisper_colon_and_semicolon():
    assert apply_punctuation("findings: clear; no masses") == "Findings clear no masses"


def test_preserves_decimals():
    assert apply_punctuation("the mass measures 7.5 mm") == "The mass measures 7.5 mm"


def test_preserves_apostrophes_in_contractions():
    assert apply_punctuation("it's normal") == "It's normal"


def test_token_period():
    assert apply_punctuation("lungs clear period") == "Lungs clear."


def test_token_comma():
    assert apply_punctuation("lungs comma heart comma kidneys") == "Lungs, heart, kidneys"


def test_token_semicolon():
    assert apply_punctuation("lungs clear semicolon heart normal") == "Lungs clear; heart normal"


def test_token_semicolon_hyphenated_variant():
    assert apply_punctuation("lungs clear semi-colon heart normal") == "Lungs clear; heart normal"


def test_token_hyphen():
    assert apply_punctuation("follow up hyphen imaging") == "Follow up - imaging"


def test_token_dash():
    assert apply_punctuation("finding dash incidental") == "Finding — incidental"


def test_token_question_mark():
    assert apply_punctuation("is it clear question mark") == "Is it clear?"


def test_token_exclamation_point():
    assert apply_punctuation("ouch exclamation point") == "Ouch!"


def test_token_exclamation_mark_variant():
    assert apply_punctuation("ouch exclamation mark") == "Ouch!"


def test_token_new_paragraph():
    assert apply_punctuation("first line new paragraph second line") == "First line\n\nSecond line"


def test_token_next_paragraph_variant():
    assert apply_punctuation("first line next paragraph second line") == "First line\n\nSecond line"


def test_token_new_line():
    assert apply_punctuation("line one new line line two") == "Line one\nline two"


def test_token_parentheses():
    assert apply_punctuation(
        "incidental finding open paren likely benign close paren"
    ) == "Incidental finding (likely benign)"


def test_token_open_parenthesis_variant():
    assert apply_punctuation(
        "incidental finding open parenthesis likely benign close parenthesis"
    ) == "Incidental finding (likely benign)"


def test_token_quotes():
    assert apply_punctuation(
        "open quote normal close quote study"
    ) == "\u201cnormal\u201d study"


def test_chained_period_and_new_paragraph():
    assert (
        apply_punctuation("sentence one period new paragraph sentence two period")
        == "Sentence one.\n\nSentence two."
    )


def test_colon_as_punctuation():
    assert apply_punctuation("findings colon one mass") == "Findings: one mass"


def test_colon_anatomy_preceded_by_distal():
    assert apply_punctuation("fluid in the distal colon") == "Fluid in the distal colon"


def test_colon_anatomy_preceded_by_sigmoid():
    assert apply_punctuation("mass in the sigmoid colon") == "Mass in the sigmoid colon"


def test_colon_anatomy_followed_by_cancer():
    assert apply_punctuation("colon cancer screening") == "Colon cancer screening"


def test_colon_anatomy_followed_by_polyp():
    assert apply_punctuation("the colon polyp was removed") == "The colon polyp was removed"


def test_colon_at_start_not_anatomy_becomes_punctuation():
    assert apply_punctuation("colon finding") == ": finding"


def test_autocap_after_period():
    assert (
        apply_punctuation("first sentence period second sentence period")
        == "First sentence. Second sentence."
    )


def test_autocap_after_new_paragraph():
    assert (
        apply_punctuation("sentence one period new paragraph sentence two period")
        == "Sentence one.\n\nSentence two."
    )


def test_autocap_after_question_mark():
    assert (
        apply_punctuation("is it clear question mark yes period")
        == "Is it clear? Yes."
    )


def test_autocap_after_exclamation():
    assert (
        apply_punctuation("great exclamation point more to come period")
        == "Great! More to come."
    )


def test_collapses_interior_whitespace():
    assert apply_punctuation("hello    world   period") == "Hello world."


def test_strips_leading_whitespace_per_line():
    assert (
        apply_punctuation("one period new paragraph    two period")
        == "One.\n\nTwo."
    )


def test_no_space_before_punctuation():
    assert apply_punctuation("word  comma  word  period") == "Word, word."


def test_collapses_triple_newlines():
    assert (
        apply_punctuation("one new paragraph new paragraph two")
        == "One\n\nTwo"
    )


def test_acceptance_full_dictation():
    dictated = (
        "the lungs are clear period no acute findings period "
        "new paragraph impression colon normal chest x-ray period"
    )
    expected = (
        "The lungs are clear. No acute findings.\n\n"
        "Impression: normal chest x-ray."
    )
    assert apply_punctuation(dictated) == expected


def test_acceptance_decimal_measurement():
    dictated = "the mass measures 7.5 mm period"
    assert apply_punctuation(dictated) == "The mass measures 7.5 mm."


def test_acceptance_colon_mixed_usage():
    dictated = (
        "findings colon fluid in the distal colon period "
        "new paragraph impression colon colitis period"
    )
    expected = (
        "Findings: fluid in the distal colon.\n\n"
        "Impression: colitis."
    )
    assert apply_punctuation(dictated) == expected


def test_enforce_spacing_period_adjacent_to_letter():
    assert _enforce_punctuation_spacing("one.two") == "one. two"


def test_enforce_spacing_comma_adjacent_to_letter():
    assert _enforce_punctuation_spacing("one,two") == "one, two"


def test_enforce_spacing_question_mark_adjacent_to_letter():
    assert _enforce_punctuation_spacing("ok?yes") == "ok? yes"


def test_enforce_spacing_preserves_decimals():
    assert _enforce_punctuation_spacing("7.5 mm") == "7.5 mm"


def test_enforce_spacing_preserves_thousands_separators():
    assert _enforce_punctuation_spacing("3,000 ml") == "3,000 ml"


def test_enforce_spacing_leaves_already_spaced_untouched():
    assert _enforce_punctuation_spacing("one. two, three? four") == "one. two, three? four"


def test_autocap_follows_inserted_space():
    # After enforcement adds a space, _autocap sees ". n" and capitalizes.
    # (First letter also gets capitalized by _autocap's start-of-doc rule.)
    from src.engine.punctuation import _autocap
    assert _autocap(_enforce_punctuation_spacing("sentence.next")) == "Sentence. Next"


def test_capitalize_first_false_keeps_first_letter_lowercase():
    """apply_punctuation(capitalize_first=False) suppresses the start-of-text cap
    but still capitalizes after a sentence terminator."""
    assert apply_punctuation("hello period world", capitalize_first=False) == "hello. World"


def test_capitalize_first_false_on_plain_text():
    """Mid-sentence continuation with no terminator stays lowercase."""
    assert apply_punctuation("and no abnormalities", capitalize_first=False) == "and no abnormalities"


def test_capitalize_first_default_true_preserves_legacy_behavior():
    """Default behavior is unchanged for callers that don't pass the flag."""
    assert apply_punctuation("hello period world") == "Hello. World"
