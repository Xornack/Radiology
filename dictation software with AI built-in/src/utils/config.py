# PHI Regex Patterns
PHI_PATTERNS = {
    r'\b\d{1,2}/\d{1,2}/\d{2,4}\b': '[DATE]',
    r'\b\d{4}-\d{1,2}-\d{1,2}\b': '[DATE]',
    r'\bMRN:\s*\d+[-]\d+[-]\d+\b': 'MRN: [ID]',
    r'Patient\s+[A-Z][a-z]+\s+[A-Z][a-z]+': 'Patient [NAME]'
}
