import unittest

from utils import str_tokenize_words


class StrTokenizeWordsTests(unittest.TestCase):
    def test_words_are_separated_from_punctuation(self):
        self.assertEqual(
            str_tokenize_words("Hello, world! How are you?"),
            ["Hello", "world", "How", "are", "you"],
        )

    def test_apostrophes_and_hyphens_are_kept_inside_words(self):
        self.assertEqual(
            str_tokenize_words("Bella 's well-known dog isn't here day-by-day -abc."),
            ["Bella", "s", "well-known", "dog", "isn't", "here", "day-by-day", "abc"],
        )

    def test_numeric_tokens_keep_dots_and_apostrophes(self):
        self.assertEqual(
            str_tokenize_words("Values: .25, 12.5 and 1'000."),
            ["Values", ".25", "12.5", "and", "1'000"],
        )

    def test_programming_language_names_and_ampersand(self):
        self.assertEqual(
            str_tokenize_words("C, C++, C# and A&B"),
            ["C", "C++", "C#", "and", "A&B"],
        )

    def test_empty_or_punctuation_only_string(self):
        self.assertEqual(str_tokenize_words(""), [])
        self.assertEqual(str_tokenize_words("... , !?"), [])


if __name__ == "__main__":
    unittest.main()
