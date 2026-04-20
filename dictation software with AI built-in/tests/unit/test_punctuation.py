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
