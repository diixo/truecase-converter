import json
import re

from datasets import load_dataset

from compound_dictionary import CompoundDictionary
from utils import read_embedded_dict, str_tokenize_words


DATASET_NAME = "aitetic/bookcorpus"
SPLIT = "train"

NEW_WORDS_FILE = "bookcorpus_new_words.json"
NEW_WORDS_SENTENCES_FILE = "bookcorpus_new_words_sentences.jsonl"

MAX_SENTENCES = 10000
MAX_SENTENCES = None  # Use None for the complete dataset.

LOG_EVERY = 1000

NUMBER_TOKEN_RE = re.compile(r"^-?\.?\d+(?:[.']\d+)*$")


def is_number_token(word: str) -> bool:
    """Return True for numeric tokens such as 123, -123, .25, or 1'000."""
    return NUMBER_TOKEN_RE.fullmatch(word) is not None


def main():
    embed_set = read_embedded_dict()

    print("Loading dataset...")
    dataset = load_dataset(DATASET_NAME, split=SPLIT)
    total_sentences = len(dataset)
    if MAX_SENTENCES is not None:
        total_sentences = min(total_sentences, MAX_SENTENCES)
    print(f"Total sentences: {total_sentences:,}")

    compound_dictionary = CompoundDictionary(embed_set)

    logged_sentences = 0

    with open(NEW_WORDS_SENTENCES_FILE, "w", encoding="utf-8", newline="\n") as output:

        for sentence_id in range(total_sentences):
            original_text = dataset[sentence_id]["text"]
            tokenized_words = str_tokenize_words(original_text)
            words = {
                word
                for word in tokenized_words
                if not is_number_token(word)
            }
            sentence_new_words = compound_dictionary.register_missing(words)

            if sentence_new_words:
                item = {
                    "id": sentence_id,
                    "original_text": original_text
                }
                output.write(json.dumps(item, ensure_ascii=False) + "\n")

                output.flush()

                logged_sentences += 1

            if (sentence_id + 1) % LOG_EVERY == 0:
                print(
                    f"...{sentence_id + 1:,} / {total_sentences:,} | "
                    f"new_words={len(compound_dictionary):,} | "
                    f"sentence_new_words={logged_sentences:,}"
                )


    with open(NEW_WORDS_FILE, "w", encoding="utf-8", newline="\n") as output:
        sorted_new_words = {
            word: compound_dictionary.entries[word]
            for word in sorted(
                compound_dictionary.entries,
                key=lambda value: (value.lower(), value),
            )
        }
        json.dump(sorted_new_words, output, ensure_ascii=False, indent=2)
        output.write("\n")


    print("=" * 60)
    print("DONE")
    print("=" * 60)
    print(f"new words:  {len(compound_dictionary):,} -> {NEW_WORDS_FILE}")
    print(f"sentences:  {logged_sentences:,} -> {NEW_WORDS_SENTENCES_FILE}")


if __name__ == "__main__":
    main()
