"""Radiology vocabulary correction.

Post-transcription pass that fuzzy-matches each word against a curated list
of radiology terms and swaps in the lexicon spelling when the STT engine
produces a close-but-wrong variant (e.g. "plural" → "pleural", "atalectasis"
→ "atelectasis"). Engine-agnostic — runs after apply_punctuation regardless
of which STT produced the text.

This is a starter vocabulary. A future slice should load the full RSNA
RadLex XML for comprehensive coverage.
"""
import re
from difflib import get_close_matches
from functools import lru_cache


# Terms most commonly mis-transcribed in radiology dictation. Keep this
# file editable; adding a term is a one-line change.
RADIOLOGY_TERMS = frozenset([
    # Thoracic anatomy
    "pleural", "pericardium", "pericardial", "gastroesophageal", "nasogastric",
    "endotracheal", "retroperitoneal", "mediastinum", "mediastinal",
    "hilum", "hilar", "subpleural", "subsegmental", "bronchovascular",
    "peribronchial", "perivascular", "parenchyma", "parenchymal",
    "diaphragm", "diaphragmatic", "intercostal", "costophrenic",
    "cardiophrenic", "retrocardiac", "hemithorax",
    # CNS anatomy
    "cortical", "medullary", "subcortical", "periventricular",
    "cerebellar", "pons", "medulla", "thalamus", "thalamic",
    "corona", "radiata", "semiovale",
    # Orientation
    "ipsilateral", "contralateral", "bilateral", "unilateral",
    "anterior", "posterior", "superior", "inferior",
    "medial", "lateral", "proximal", "distal",
    # Pathology
    "atelectasis", "consolidation", "opacity", "opacification",
    "effusion", "pneumothorax", "hemothorax", "pneumomediastinum",
    "pneumopericardium", "bronchiectasis", "emphysema", "emphysematous",
    "ground-glass", "reticular", "nodular", "micronodular",
    "lymphadenopathy", "adenopathy", "thickening", "stenosis",
    "sclerosis", "lesion", "lesions", "neoplasm", "neoplastic",
    "hemorrhage", "hematoma", "thrombosis", "thromboembolism",
    "embolism", "embolus", "infarct", "infarction", "ischemic",
    "ischemia", "edema", "edematous",
    # Attenuation / intensity / echogenicity
    "hypoattenuating", "hyperattenuating", "isoattenuating",
    "hypointense", "hyperintense", "isointense",
    "hypodense", "hyperdense", "isodense",
    "hypoechoic", "hyperechoic", "anechoic", "isoechoic",
    # Modalities / sequences
    "fluoroscopy", "mammography", "angiography", "venography",
    "cholangiography", "urography", "tomography",
    "flair", "dwi", "adc", "swi", "mra", "mrcp", "ercp",
    # Units and measurements
    "millimeter", "millimeters", "centimeter", "centimeters", "hounsfield",
])

# Words we never want to "correct" — common English that happens to be close
# to a radiology term and would over-match. Guard list grows with experience.
_SAFE_WORDS = frozenset([
    "please", "clear", "claim", "mass", "small", "large",
    "and", "or", "the", "is", "was", "are", "of", "in", "to",
    "with", "without", "normal", "abnormal", "appears", "appear",
    "seen", "shows", "shown", "show",
])

# Exact-swap dictionary — high-confidence known replacements that we don't
# want to go through fuzzy matching (e.g. homophones where the fuzzy score
# would be unstable).
_KNOWN_SWAPS = {
    "plural": "pleural",   # the single most common English-radiology confusion
}

_WORD_RE = re.compile(r"\b[\w\-']+\b")


def correct_radiology(text: str, threshold: float = 0.85) -> str:
    """Swap near-miss spellings for their radiology-vocabulary form.

    Exact lexicon matches, safe English words, and anything further than
    `threshold` similarity (0-1) are left alone. Case style from the
    original word is preserved in the replacement.
    """
    if not text:
        return text
    return _WORD_RE.sub(lambda m: _correct_one_word(m.group(0), threshold), text)


def _correct_one_word(word: str, threshold: float) -> str:
    """Case-preserving correction for a single token.

    Hot path: `difflib.get_close_matches` dominates when the word misses
    both the RADIOLOGY_TERMS set and the safe-words set. Delegating to
    `_best_match` (which is `lru_cache`d by lowercase+threshold) means
    repeated misses in a dictation session pay the cost once.
    """
    lower = word.lower()
    if lower in RADIOLOGY_TERMS:
        return word
    if lower in _KNOWN_SWAPS:
        return _preserve_case(word, _KNOWN_SWAPS[lower])
    if lower in _SAFE_WORDS:
        return word
    best = _best_match(lower, threshold)
    if best is not None:
        return _preserve_case(word, best)
    return word


@lru_cache(maxsize=4096)
def _best_match(lower: str, threshold: float):
    """Cached fuzzy lookup. Key is (lowercase-word, threshold) so the
    same miss in a long dictation hits the cache instead of re-running
    difflib.get_close_matches over the ~100-term vocabulary."""
    candidates = get_close_matches(lower, RADIOLOGY_TERMS, n=1, cutoff=threshold)
    return candidates[0] if candidates else None


def _preserve_case(original: str, replacement: str) -> str:
    """ALL-CAPS in → ALL-CAPS out; Title → Title; otherwise lowercase."""
    if original.isupper() and len(original) > 1:
        return replacement.upper()
    if original[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement
