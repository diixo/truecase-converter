import unittest

from contextual_truecase import (
    Pair, add_builtin_pairs, allowed_truecase_equal, case_only_equal, load_pairs,
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

    def test_single_pairs_follow_contextual_model_evidence(self):
        rows = [
            {"id": 1, "text": "we landed on amazon ."},
            {"id": 2, "text": "fanio answered ."},
        ]
        pairs = [
            Pair(("amazon",), ("Amazon",)),
            Pair(("fanio",), ("Fanio",)),
        ]
        result = truecase_records(rows, pairs, [{3}, {0}], 20, "balanced")
        self.assertEqual(result[0]["text"], "We landed on Amazon .")
        self.assertEqual(result[1]["text"], "Fanio answered .")

    def test_uppercase_homonym_is_not_applied_globally(self):
        rows = [{"id": 1, "text": "i am ready ."}]
        pair = Pair(("am",), ("AM",))
        result = truecase_records(rows, [pair], [set()], 20, "balanced")
        self.assertEqual(result[0]["text"], "I am ready .")

    def test_unambiguous_builtin_contractions(self):
        rows = [{"id": 1, "text": "im sure ive seen it ."}]
        result = truecase_records(rows, add_builtin_pairs([]), [set()], 20, "balanced")
        self.assertEqual(result[0]["text"], "I'm sure I've seen it .")

    def test_ambiguous_builtin_contractions_need_context(self):
        rows = [
            {"id": 1, "text": "ill stay here ."},
            {"id": 2, "text": "the patient is ill ."},
            {"id": 3, "text": "id prefer tea ."},
            {"id": 4, "text": "enter the id number ."},
        ]
        result = truecase_records(
            rows, add_builtin_pairs([]), [{0}, set(), {0}, set()], 20,
            "balanced", propagate_evidence=False,
        )
        self.assertEqual(result[0]["text"], "I'll stay here .")
        self.assertEqual(result[1]["text"], "The patient is ill .")
        self.assertEqual(result[2]["text"], "I'd prefer tea .")
        self.assertEqual(result[3]["text"], "Enter the id number .")


if __name__ == "__main__":
    unittest.main()
