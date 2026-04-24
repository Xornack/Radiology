"""Single source of truth for available STT backends.

Adding one here makes it appear in the UI dropdown and be reachable by
`main.py` without touching either file. Removing a backend is the reverse:
drop its row, its client, its test, and any matching extra in pyproject.

Currently supported: Whisper local (CPU + GPU) and Alibaba's SenseVoice.
Backends that didn't pan out were removed after user testing:
  - Moonshine: poor accuracy for clinical speech.
  - Vosk: failed on startup against the small-en model.
  - Whisper large-v3-turbo: too slow on consumer GPUs for live partials.
  - Gemma 4: dependency on an unreleased transformers main branch + 4-bit
    quantization bugs.
  - Parakeet-TDT: NeMo import chain crashed the process on Python 3.13 Windows.
  - Whisper HTTP: meant for remote deployments; on a single workstation it
    always connection-refuses.
"""
from dataclasses import dataclass
from typing import Any, Callable

from loguru import logger


STTBuilder = Callable[[Any], Any]   # (settings) -> stt_client


@dataclass(frozen=True)
class STTBackendSpec:
    """One on-device STT backend the app can run.

    `key`: unique dropdown / env-var value.
    `display_name`: user-visible combo label (None means hidden from UI).
    `build`: settings -> stt_client factory. Responsible for raising
        ImportError with a "install with pip install -e '.[extra]'" hint
        if the backend's optional deps aren't present.
    """
    key: str
    display_name: str | None
    build: STTBuilder


# --- Builders. Kept as module-level functions so they can be reused in tests. ---

def _build_whisper_local_cpu(settings) -> Any:
    from src.ai.local_whisper_client import LocalWhisperClient
    logger.info(
        f"STT: Whisper local CPU (model={settings.whisper_model}, cpu/int8)"
    )
    return LocalWhisperClient(
        model_size=settings.whisper_model,
        device="cpu",
        compute_type="int8",
    )


def _build_whisper_local_gpu(settings) -> Any:
    from src.ai.local_whisper_client import LocalWhisperClient
    # Force CUDA + float16. If runtime DLLs are missing the client falls
    # back to CPU+int8 automatically at inference time.
    logger.info(
        f"STT: Whisper local GPU (model={settings.whisper_model}, cuda/float16)"
    )
    return LocalWhisperClient(
        model_size=settings.whisper_model,
        device="cuda",
        compute_type="float16",
    )


def _build_sensevoice(_settings) -> Any:
    try:
        import funasr  # noqa: F401
    except ImportError as e:
        raise ImportError(
            "SenseVoice STT requires the [sensevoice] extra "
            f"(missing: {getattr(e, 'name', None) or e}). "
            "Install with: pip install -e '.[sensevoice]'"
        ) from e
    from src.ai.sensevoice_stt_client import SenseVoiceSTTClient
    logger.info("STT: SenseVoice (iic/SenseVoiceSmall)")
    return SenseVoiceSTTClient()


def _build_medasr(_settings) -> Any:
    try:
        import torch  # noqa: F401
    except ImportError as e:
        raise ImportError(
            f"MedASR requires the [medasr] extra (missing: "
            f"{getattr(e, 'name', None) or e}). "
            "Install with: pip install -e '.[medasr]'"
        ) from e
    try:
        # Direct submodule imports, not `from transformers import ...`.
        # transformers' top-level `_LazyModule.__getattr__` races under
        # Python 3.13 when another thread (e.g. a still-running SenseVoice
        # warm that pulled in funasr→transformers) touches the same lazy
        # attribute concurrently — one thread gets a bogus "cannot import
        # name 'AutoModelForCTC' from 'transformers'" even though it's
        # actually there. Going through the real submodules side-steps
        # the lazy machinery entirely.
        from transformers.models.auto.modeling_auto import AutoModelForCTC  # noqa: F401
        from transformers.models.auto.processing_auto import AutoProcessor  # noqa: F401
    except ImportError as e:
        import transformers as _t
        raise ImportError(
            f"MedASR requires `AutoModelForCTC` + `AutoProcessor` from "
            f"transformers {_t.__version__}, but the import failed: {e}\n\n"
            "If the extra isn't installed: pip install -e '.[medasr]'\n"
            "If transformers is too old: pip install --upgrade "
            "'transformers @ git+https://github.com/huggingface/transformers.git'"
        ) from e
    from src.ai.medasr_stt_client import MedASRSTTClient
    logger.info("STT: MedASR (google/medasr)")
    return MedASRSTTClient()


# --- The registry itself. Order here = order in the UI dropdown. ---
BACKENDS: list[STTBackendSpec] = [
    STTBackendSpec("whisper-local-cpu", "Whisper (local, CPU)",  _build_whisper_local_cpu),
    STTBackendSpec("whisper-local-gpu", "Whisper (local, GPU)",  _build_whisper_local_gpu),
    STTBackendSpec("sensevoice",        "SenseVoice (Alibaba)",  _build_sensevoice),
    STTBackendSpec("medasr",            "MedASR (Google Health)", _build_medasr),
]


# --- Public API ---

DEFAULT_BACKEND_KEY = "whisper-local-cpu"


def dropdown_backends() -> list[STTBackendSpec]:
    """Specs to render in the UI combo, in the order they should appear."""
    return [b for b in BACKENDS if b.display_name is not None]


def build_stt_client(backend_key: str, settings) -> Any:
    """Construct the STT client for the requested key.

    Unknown keys fall back to the default so a stale env var (e.g. from
    before a backend was removed) doesn't disable dictation.
    """
    key = (backend_key or "").lower()
    for spec in BACKENDS:
        if spec.key == key:
            return spec.build(settings)
    logger.warning(
        f"Unknown STT backend {backend_key!r}; falling back to "
        f"'{DEFAULT_BACKEND_KEY}'."
    )
    for spec in BACKENDS:
        if spec.key == DEFAULT_BACKEND_KEY:
            return spec.build(settings)
    raise RuntimeError("STT registry missing its default entry")
