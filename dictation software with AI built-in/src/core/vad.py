"""Energy-based voice-activity detector.

Finds a "commit point" inside an audio buffer: the sample index after
a long-enough silence gap that starts after a long-enough leading
chunk of audio. Used by the streaming transcriber to decide where
it's safe to lock in transcribed text so future ticks don't have to
re-do that work.

Self-calibrating: the RMS threshold is relative to the buffer's own
rolling maximum RMS, so it adapts to mic gain without per-user config.
"""
from typing import Optional

import numpy as np


def find_commit_point(
    samples: np.ndarray,
    sample_rate: int = 16000,
    min_silence_ms: int = 600,
    min_chunk_ms: int = 2000,
    rms_window_ms: int = 30,
    fallback_cap_s: float = 30.0,
    fallback_search_s: float = 10.0,
) -> Optional[int]:
    """Return sample index at end of a qualifying silence, or None.

    Qualifies when: there are >= min_chunk_ms of audio BEFORE a silence
    of >= min_silence_ms. Threshold for "silence" is self-calibrated as
    max(0.002, 0.15 * rolling_max_rms) over non-overlapping windows of
    `rms_window_ms`.

    Fallback: if the buffer is longer than fallback_cap_s AND no natural
    commit point qualifies, return the index at the quietest 100 ms
    window inside the last `fallback_search_s` of the buffer. This
    bounds partial-region growth on continuous-talk dictations.
    """
    if samples.size == 0:
        return None

    win_len = max(1, int(sample_rate * rms_window_ms / 1000))
    n_windows = samples.size // win_len
    if n_windows == 0:
        return None

    trimmed = samples[: n_windows * win_len].reshape(n_windows, win_len)
    rms = np.sqrt(np.mean(trimmed.astype(np.float32) ** 2, axis=1))
    rolling_max = np.max(rms) if rms.size else 0.0
    threshold = max(0.002, 0.15 * float(rolling_max))

    min_silence_windows = max(1, int(min_silence_ms / rms_window_ms))
    min_chunk_windows = max(1, int(min_chunk_ms / rms_window_ms))

    silence_start: Optional[int] = None
    for i, r in enumerate(rms):
        is_silent = r < threshold
        if is_silent:
            if silence_start is None:
                silence_start = i
        else:
            if silence_start is not None:
                run_len = i - silence_start
                if run_len >= min_silence_windows and silence_start >= min_chunk_windows:
                    return i * win_len
                silence_start = None

    if silence_start is not None:
        run_len = n_windows - silence_start
        if run_len >= min_silence_windows and silence_start >= min_chunk_windows:
            return n_windows * win_len

    if samples.size >= int(fallback_cap_s * sample_rate):
        search_start_sample = samples.size - int(fallback_search_s * sample_rate)
        search_start_win = max(0, search_start_sample // win_len)
        if search_start_win < n_windows:
            local_min_idx = search_start_win + int(np.argmin(rms[search_start_win:]))
            return local_min_idx * win_len

    return None
