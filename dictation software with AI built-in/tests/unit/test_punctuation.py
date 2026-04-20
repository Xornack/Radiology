from src.engine.punctuation import apply_punctuation


def test_empty_input_returns_empty():
    assert apply_punctuation("") == ""


def test_plain_text_gets_capitalized():
    assert apply_punctuation("the lungs are clear") == "The lungs are clear"
