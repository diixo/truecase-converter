import unittest

from compound_dictionary import CompoundDictionary, split_compound_word
from utils import read_embedded_dict


class CompoundDictionaryTests(unittest.TestCase):
    def setUp(self):
        self.dictionary = CompoundDictionary({"note", "book", "known"})

    def test_known_words_are_not_registered(self):
        self.assertEqual(self.dictionary.register_missing({"known"}), set())
        self.assertEqual(self.dictionary.entries, {})

    def test_compound_word_is_registered_with_interpretation(self):
        unknown_words = self.dictionary.register_missing({"notebook"})

        self.assertEqual(unknown_words, set())
        self.assertEqual(self.dictionary.entries["notebook"], "note book")

    def test_word_that_cannot_be_split_remains_unknown(self):
        unknown_words = self.dictionary.register_missing({"mystery"})

        self.assertEqual(unknown_words, {"mystery"})
        self.assertEqual(self.dictionary.entries["mystery"], "mystery")

    def test_registered_word_is_reused(self):
        self.dictionary.register("notebook")

        self.assertEqual(self.dictionary.register("notebook"), "note book")
        self.assertEqual(len(self.dictionary), 1)


class SplitCompoundWordTests(unittest.TestCase):
    def test_compound_word_is_split_into_known_words(self):
        self.assertEqual(
            split_compound_word("notebookcase", read_embedded_dict()),
            ["notebook", "case"],
        )

    def test_suffixes_are_checked_from_the_end(self):
        self.assertEqual(
            split_compound_word("anotebook", read_embedded_dict()),
            ["a", "note", "book"],
        )

    def test_long_compound_word_is_split_from_right_to_left(self):
        self.assertEqual(
            split_compound_word("ithinkiloveyou", read_embedded_dict()),
            ["i", "think", "i", "love", "you"],
        )

    def test_unknown_or_single_known_word_is_not_split(self):
        known_words = {"note", "book"}
        self.assertIsNone(split_compound_word("unknown", known_words))
        self.assertIsNone(split_compound_word("note", known_words))


if __name__ == "__main__":
    unittest.main()
