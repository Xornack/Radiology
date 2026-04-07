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
