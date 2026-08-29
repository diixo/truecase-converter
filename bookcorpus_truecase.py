import json
import re

from datasets import load_dataset

from utils import read_embedded_dict, str_tokenize_words


DATASET_NAME = "aitetic/bookcorpus"
SPLIT = "train"

NEW_WORDS_FILE = "bookcorpus_new_words.txt"
NEW_WORDS_SENTENCES_FILE = "bookcorpus_new_words_sentences.jsonl"
MAX_SENTENCES = 1000  # Use None for the complete dataset.
LOG_EVERY = 100


def normalize_sentence(sentence: str) -> str:
    sentence = sentence.replace(" .", ".")
    sentence = sentence.replace(" ,", ",")
    sentence = sentence.replace(" ?", "?")
    sentence = sentence.replace(" !", "!")
    sentence = sentence.replace(" '", "'")
    sentence = sentence.replace("''", '"')
    sentence = sentence.replace("``", '"')
    sentence = sentence.replace(" n't", "n't")
    sentence = sentence.replace(" ...", "...")
    sentence = sentence.replace(".-", ". -")
    sentence = sentence.replace("i 'm", " I'm")
    sentence = sentence.replace("i 'll", " I'll")
    sentence = sentence.replace("i 'd", " I'd")
    sentence = sentence.replace("i 've", " I've")
    return sentence


def main() -> None:
    word_set = read_embedded_dict()

    print("Loading dataset...")
    dataset = load_dataset(DATASET_NAME, split=SPLIT)
    total_sentences = len(dataset)
    if MAX_SENTENCES is not None:
        total_sentences = min(total_sentences, MAX_SENTENCES)
    print(f"Total sentences: {total_sentences:,}")

    new_words: set[str] = set()
    logged_sentences = 0

    with open(NEW_WORDS_SENTENCES_FILE, "w", encoding="utf-8", newline="\n") as output:
        for sentence_id in range(total_sentences):
            original_text = dataset[sentence_id]["text"]
            words = set(str_tokenize_words(normalize_sentence(original_text)))
            sentence_new_words = words - word_set - new_words

            if sentence_new_words:
                item = {"id": sentence_id, "original_text": original_text}
                output.write(json.dumps(item, ensure_ascii=False) + "\n")
                new_words.update(sentence_new_words)
                logged_sentences += 1

            if (sentence_id + 1) % LOG_EVERY == 0:
                print(
                    f"processed={sentence_id + 1:,}/{total_sentences:,} | "
                    f"new_words={len(new_words):,} | logged={logged_sentences:,}"
                )

    with open(NEW_WORDS_FILE, "w", encoding="utf-8", newline="\n") as output:
        for word in sorted(new_words, key=lambda value: (value.lower(), value)):
            output.write(word + "\n")

    print("=" * 60)
    print("DONE")
    print("=" * 60)
    print(f"new words:  {len(new_words):,} -> {NEW_WORDS_FILE}")
    print(f"sentences:  {logged_sentences:,} -> {NEW_WORDS_SENTENCES_FILE}")


if __name__ == "__main__":
    main()
