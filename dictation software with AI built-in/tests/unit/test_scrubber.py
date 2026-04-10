import pytest
from src.security.scrubber import scrub_text


def test_scrub_patient_name():
    raw_text = "Patient John Doe has a small mass in the right lung."
    expected = "Patient [NAME] has a small mass in the right lung."
    assert scrub_text(raw_text) == expected


def test_scrub_date_of_birth():
    raw_text = "DOB: 01/01/1980. The scan was performed on 2024-05-12."
    expected = "DOB: [DATE]. The scan was performed on [DATE]."
    assert scrub_text(raw_text) == expected


def test_scrub_mrn():
    raw_text = "MRN: 123-456-7890. Patient presented with cough."
    expected = "MRN: [ID]. Patient presented with cough."
    assert scrub_text(raw_text) == expected


def test_scrub_ssn():
    """Social Security Numbers must be scrubbed."""
    raw_text = "SSN: 123-45-6789. Chest CT ordered."
    result = scrub_text(raw_text)
    assert "123-45-6789" not in result
    assert "[SSN]" in result


def test_scrub_phone_number():
    """US phone numbers must be scrubbed."""
    raw_text = "Call the patient at 555-123-4567 for follow-up."
    result = scrub_text(raw_text)
    assert "555-123-4567" not in result
    assert "[PHONE]" in result


def test_scrub_email():
    """Email addresses must be scrubbed."""
    raw_text = "Contact patient at john.doe@hospital.com for results."
    result = scrub_text(raw_text)
    assert "john.doe@hospital.com" not in result
    assert "[EMAIL]" in result


def test_scrub_spelled_out_date():
    """Month-spelled dates (e.g. 'January 5, 2024') must be scrubbed."""
    raw_text = "Scan performed on January 5, 2024. No acute findings."
    result = scrub_text(raw_text)
    assert "January 5, 2024" not in result
    assert "[DATE]" in result


def test_non_phi_text_unchanged():
    """Normal clinical text without PHI must pass through unmodified."""
    raw_text = "The lungs are clear. No pneumothorax. Heart size normal."
    assert scrub_text(raw_text) == raw_text
