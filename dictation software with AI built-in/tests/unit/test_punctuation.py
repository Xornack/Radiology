from src.engine.punctuation import apply_punctuation


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
