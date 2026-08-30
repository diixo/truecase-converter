from collections.abc import Iterable

from utils import split_compound_word


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
