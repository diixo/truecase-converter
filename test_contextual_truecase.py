import unittest

from contextual_truecase import (
    Pair, allowed_truecase_equal, case_only_equal, load_pairs,
    sentence_baseline, truecase_records,
)


class ContextualTruecaseTests(unittest.TestCase):
    def test_baseline_preserves_format(self):
        source = "`` i went home . '' then i slept !"
        result = sentence_baseline(source)
        self.assertEqual(result, "`` I went home . '' Then I slept !")
        self.assertTrue(case_only_equal(source, result))

    def test_context_propagates_single_name(self):
        rows = [{"id": 1, "text": "eunice arrived ."}, {"id": 2, "text": "i saw eunice ."}]
        pair = Pair(("eunice",), ("Eunice",))
        result = truecase_records(rows, [pair], [{0}, set()], 2, "balanced")
        self.assertEqual(result[1]["text"], "I saw Eunice .")

    def test_ambiguous_single_pair_is_not_global(self):
        rows = [{"id": 1, "text": "the train stopped ."}]
        pair = Pair(("train",), ("Train",))
        result = truecase_records(rows, [pair], [set()], 20, "balanced")
        self.assertEqual(result[0]["text"], "The train stopped .")

    def test_possessive_apostrophe_can_be_restored(self):
        rows = [{"id": 1, "text": "amastras eyes narrowed ."}]
        pair = Pair(("amastras",), ("Amastra's",))
        # An explicit possessive pair is actionable even when lowercase Stanza
        # does not recognise the fictional name as PROPN/NER.
        result = truecase_records(rows, [pair], [set()], 20, "balanced")
        self.assertEqual(result[0]["text"], "Amastra's eyes narrowed .")
        self.assertTrue(allowed_truecase_equal(rows[0]["text"], result[0]["text"]))
        self.assertFalse(allowed_truecase_equal("amastras", "Amastra-s"))


if __name__ == "__main__":
    unittest.main()
