from collections.abc import Iterable
from functools import lru_cache



def split_compound_word(word: str, known_words: set[str]) -> list[str] | None:
    """Split an unknown word by looking for known suffixes right to left."""

    @lru_cache(maxsize=None)
    def split_prefix(prefix: str) -> tuple[str, ...] | None:
        for split_at in range(len(prefix) - 1, 0, -1):
            suffix = prefix[split_at:]
            if suffix not in known_words:
                continue

            remainder = prefix[:split_at]
            if remainder in known_words:
                return remainder, suffix

            remainder_parts = split_prefix(remainder)
            if remainder_parts is not None:
                return *remainder_parts, suffix

        return None

    result = split_prefix(word)
    return list(result) if result is not None else None


class CompoundDictionary:
    def __init__(self, known_words: set[str]) -> None:
        self.known_words = known_words
        self.entries: dict[str, str] = {}

    def register(self, word: str) -> str:
        """Register a missing word and return its dictionary interpretation."""
        if word in self.entries:
            return self.entries[word]

        parts = split_compound_word(word, self.known_words)
        interpretation = " ".join(parts) if parts else word
        self.entries[word] = interpretation
        return interpretation

    def register_missing(self, words: Iterable[str]) -> set[str]:
        """Register missing words and return those that cannot be decomposed."""
        unknown_words: set[str] = set()

        for word in words:
            if word in self.known_words:
                continue
            if self.register(word) == word:
                unknown_words.add(word)

        return unknown_words

    def __len__(self) -> int:
        return len(self.entries)
