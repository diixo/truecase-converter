import unittest

from compound_dictionary import CompoundDictionary


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


if __name__ == "__main__":
    unittest.main()
