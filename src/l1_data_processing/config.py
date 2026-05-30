from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GraphConfig:
    split_threshold_chars: int = 6000
    chunk_size_chars: int = 2500
    chunk_overlap_chars: int = 200

    def __post_init__(self) -> None:
        if self.split_threshold_chars <= 0:
            raise ValueError("split_threshold_chars must be positive")
        if self.chunk_size_chars <= 0:
            raise ValueError("chunk_size_chars must be positive")
        if self.chunk_overlap_chars < 0:
            raise ValueError("chunk_overlap_chars must not be negative")
        if self.chunk_overlap_chars >= self.chunk_size_chars:
            raise ValueError("chunk_overlap_chars must be smaller than chunk_size_chars")
