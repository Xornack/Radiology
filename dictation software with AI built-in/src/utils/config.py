# PHI Regex Patterns
# Each key is a regex pattern; each value is the replacement placeholder.
# Order matters: more specific patterns (SSN, MRN) are checked before generic ones.
PHI_PATTERNS = {
    # Social Security Numbers: 123-45-6789
    r'\b\d{3}-\d{2}-\d{4}\b': '[SSN]',

    # MRN: various formats (must come before generic number patterns)
    r'\bMRN[:\s#]*\d[\d\-]+\b': 'MRN: [ID]',
    r'\bMedical\s+Record\s+(?:Number|No\.?|#)\s*:?\s*\d[\d\-]+\b': 'MRN: [ID]',

    # Dates — month-spelled: January 5, 2024 / Jan 5 2024
    r'\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|'
    r'Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
    r'\.?\s+\d{1,2},?\s+\d{4}\b': '[DATE]',

    # Dates — numeric: MM/DD/YYYY or MM/DD/YY
    r'\b\d{1,2}/\d{1,2}/\d{2,4}\b': '[DATE]',

    # Dates — ISO: YYYY-MM-DD
    r'\b\d{4}-\d{1,2}-\d{1,2}\b': '[DATE]',

    # Phone numbers: (555) 123-4567 / 555-123-4567 / 555.123.4567 / +1 555 123 4567
    r'\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b': '[PHONE]',

    # Email addresses
    r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b': '[EMAIL]',

    # Patient name: "Patient <1+ capitalized words>"
    # Handles: "Patient John Doe", "Patient JOHN DOE", "Patient Mary-Jane Smith",
    #          "Patient José García", "Patient Madonna"
    r'\bPatient\s+(?:[A-Z][\w\-\']*\s+)*[A-Z][\w\-\']*\b': 'Patient [NAME]',

    # Titled names: "Mr. John Smith", "Dr. Jane Doe", "Mrs. O'Brien"
    r'\b(?:Mr|Mrs|Ms|Dr|Prof)\.?\s+(?:[A-Z][\w\-\']*\s+)*[A-Z][\w\-\']*\b': '[NAME]',

    # "Name:" labels from report headers
    r'\bName\s*:\s*(?:[A-Z][\w\-\']*\s+)*[A-Z][\w\-\']*\b': 'Name: [NAME]',
}
