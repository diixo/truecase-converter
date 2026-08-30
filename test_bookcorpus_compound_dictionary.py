import unittest
from pathlib import Path

from compound_dictionary import CompoundDictionary
from utils import read_embedded_dict


class BookCorpusCompoundDictionaryTests(unittest.TestCase):
    def test_transform_new_words_and_report_statistics(self):
        input_path = Path(__file__).parent / "bookcorpus_new_words.txt"
        input_words = [
            line.strip()
            for line in input_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        unique_words = set(input_words)

        dictionary = CompoundDictionary(read_embedded_dict())
        unknown_words = dictionary.register_missing(unique_words)
        compound_words = {
            word: interpretation
            for word, interpretation in dictionary.entries.items()
            if word != interpretation
        }
        known_words_count = len(unique_words) - len(dictionary)

        print("\nBookCorpus compound dictionary statistics:")
        print(f"  input lines:       {len(input_words):,}")
        print(f"  unique words:      {len(unique_words):,}")
        print(f"  duplicate lines:   {len(input_words) - len(unique_words):,}")
        print(f"  already known:     {known_words_count:,}")
        print(f"  compound words:    {len(compound_words):,}")
        print(f"  unknown words:     {len(unknown_words):,}")

        self.assertEqual(
            len(unique_words),
            known_words_count + len(compound_words) + len(unknown_words),
        )
        self.assertEqual(
            set(dictionary.entries),
            set(compound_words) | unknown_words,
        )


if __name__ == "__main__":
    unittest.main()
