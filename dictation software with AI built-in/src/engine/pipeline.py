"""Post-transcription text pipeline: PHI scrub → punctuation → radiology.

Consolidates the three text transformations that the orchestrator used to
chain by hand. Keeping them behind one class makes the full final-text
contract testable as a unit and lets the future PowerScribe-D work
(field templates, macros) hook in as additional pipeline stages without
touching the orchestrator.
"""
from src.engine.lexicon import correct_radiology
from src.engine.punctuation import apply_punctuation
from src.security.scrubber import scrub_text


class TextPipeline:
    """Final-text pipeline applied to a raw STT transcript.

    `radiology_mode` flips the fuzzy radiology-vocabulary correction pass
    (e.g. "plural" → "pleural"). The UI checkbox rewires this at runtime.
    """

    def __init__(self, radiology_mode: bool = True):
        self.radiology_mode = radiology_mode

    def process(
        self,
        raw: str,
        *,
        capitalize_first: bool,
        strip_inferred: bool = True,
    ) -> str:
        """Run scrub → punctuation → optional radiology correction.

        `capitalize_first` gates the leading-capital behavior inside
        `apply_punctuation`; the orchestrator sets it from its wedge-
        terminator flag, and leaves it False for in-app mode so the UI
        layer decides from editor context.

        `strip_inferred=False` tells the punctuation stage to leave real
        glyphs alone — set it for engines like MedASR that already emit
        punctuation themselves, otherwise their periods/commas get erased.
        """
        clean = scrub_text(raw)
        clean = apply_punctuation(
            clean,
            capitalize_first=capitalize_first,
            strip_inferred=strip_inferred,
        )
        if self.radiology_mode:
            clean = correct_radiology(clean)
        return clean
