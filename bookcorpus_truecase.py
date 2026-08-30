import json
import os
import re

from datasets import load_dataset

from utils import read_embedded_dict, str_tokenize_words


DATASET_NAME = "aitetic/bookcorpus"
SPLIT = "train"

NEW_WORDS_FILE = "bookcorpus_new_words.txt"
NEW_WORDS_SENTENCES_FILE = "bookcorpus_new_words_sentences.jsonl"

MAX_SENTENCES = 10000
MAX_SENTENCES = None  # Use None for the complete dataset.

LOG_EVERY = 1000

RESUME = False

NUMBER_TOKEN_RE = re.compile(r"^-?\.?\d+(?:[.']\d+)*$")


def is_number_token(word: str) -> bool:
    """Return True for numeric tokens such as 123, -123, .25, or 1'000."""
    return NUMBER_TOKEN_RE.fullmatch(word) is not None


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


def get_resume_position():

    if (not RESUME or not os.path.exists(NEW_WORDS_SENTENCES_FILE)):
        return 0

    print("Existing output found. Checking resume position...")
    last_id = -1
    with open(NEW_WORDS_SENTENCES_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            last_id = max(last_id, item["id"])

    start = last_id + 1
    print(f"Resume from sentence: {start:,}")
    return start



def main():

    start_index = get_resume_position()

    word_set = read_embedded_dict()

    print("Loading dataset...")
    dataset = load_dataset(DATASET_NAME, split=SPLIT)
    total_sentences = len(dataset)
    if MAX_SENTENCES is not None:
        total_sentences = min(total_sentences, MAX_SENTENCES)
    print(f"Total sentences: {total_sentences:,}")

    new_words: set[str] = set()
    if start_index > 0 and os.path.exists(NEW_WORDS_FILE):
        with open(NEW_WORDS_FILE, "r", encoding="utf-8") as words_input:
            new_words = {line.strip() for line in words_input if line.strip()}

    logged_sentences = 0
    file_mode = "a" if start_index > 0 else "w"

    with (
        open(NEW_WORDS_SENTENCES_FILE, file_mode, encoding="utf-8", newline="\n") as output,
        open(NEW_WORDS_FILE, file_mode, encoding="utf-8", newline="\n") as words_output,
    ):
        for sentence_id in range(start_index, total_sentences):
            original_text = dataset[sentence_id]["text"]
            tokenized_words = str_tokenize_words(original_text)
            words = {
                word
                for word in tokenized_words
                if not is_number_token(word)
            }
            sentence_new_words = words - word_set
            unseen_new_words = sentence_new_words - new_words

            if sentence_new_words:
                item = {
                    "id": sentence_id,
                    "original_text": original_text
                }
                output.write(json.dumps(item, ensure_ascii=False) + "\n")

                for word in sorted(unseen_new_words):
                    words_output.write(word + "\n")

                output.flush()
                words_output.flush()
                new_words.update(unseen_new_words)

                logged_sentences += 1

            if (sentence_id + 1) % LOG_EVERY == 0:
                print(
                    f"...{sentence_id + 1:,} / {total_sentences:,} | "
                    f"new_words={len(new_words):,} | sentence_new_words={logged_sentences:,}"
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
