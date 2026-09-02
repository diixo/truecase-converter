import json
import re
from collections import Counter

from datasets import load_dataset

from utils import read_embedded_dict, read_names, str_tokenize_words


DATASET_NAME = "aitetic/bookcorpus"
SPLIT = "train"

NEW_WORDS_FILE = "bookcorpus_new_words.txt"
NEW_WORDS_COUNTS_FILE = "bookcorpus_new_words.json"
NEW_WORDS_SENTENCES_FILE = "bookcorpus_new_words_sentences.jsonl"

MAX_SENTENCES = 10000
MAX_SENTENCES = None  # Use None for the complete dataset.

LOG_EVERY = 1000

NUMBER_TOKEN_RE = re.compile(r"^-?\.?\d+(?:[.']\d+)*$")

REPLACE_TABLE = {
    "youre": "you're",
    "dont": "don't",
    "cant": "can't",
    "wont": "won't",
    "youve": "you've",
    "weve": "we've",
    "theyre": "they're",
    "youll": "you'll",
    "oh": "ok",
    "im": "i'm",
    "didnt": "didn't",
    "doesnt": "doesn't",
    "isnt": "isn't",
    "wasnt": "wasn't",
    "arent": "aren't",
    "ive": "i've",
    "id": "i'd",
    "couldnt": "couldn't",
    "shouldnt": "shouldn't",
    "wouldnt": "wouldn't",
    "theres": "there's",
    "whats": "what's",
    "hadnt": "hadn't",
    "hes": "he's",
    "shes": "she's",
    "havent": "haven't",
    "youd": "you'd",
    "wow": "good",
    "theyll": "they'll",
    "whos": "who's",
    "goin": "going",
    "hed": "he'd",
    "waitin": "waiting",
    "livin": "living",
    "whys": "why's",
    "workin": "working",
    "livin": "living",
    "werent": "weren't",
    "theyve": "they've",
    "hasnt": "hasn't",
    "ty": "tyler",
    "ah": "",
    "um": "",
    "oh": "",
    "uh": "",
    "huh": "",
    "ha": "",
    "ya": "you",
    "thad": "that",
    "meg": "meggy",
    "wouldve": "would've",
    "whod": "who'd",
    "nothin": "nothing",
    "darlin": "darling",
    "heres": "here's",
    "fuckin": "fucking",
    "outta": "out of",
    "theyd": "they'd",
    "whycan't": "why can't",
    "goodnight": "good night",
    "goddamn": "god damn",
    "whoa": "who a",
    "youcant": "you can't",
    "youcan't": "you can't",
    "ican't": "i can't",
    "hecan't": "he can't",
    "wecan't": "we can't",
    "dammit": "damn it",
    "oclock": "o'clock",
    "shecan't": "she can't",
    "theycan't": "they can't"
}


def is_number_token(word: str) -> bool:
    """Return True for numeric tokens such as 123, -123, .25, or 1'000."""
    return NUMBER_TOKEN_RE.fullmatch(word) is not None


def normalize_strong(sentence: str) -> str:

    sentence = sentence.replace(" 's ", " ")
    sentence = sentence.replace(" 'd ", " ")
    sentence = sentence.replace(" 's,", ",")
    sentence = sentence.replace(" 'd,", ",")
    sentence = sentence.replace(" 've", " ")
    sentence = sentence.replace(" 'll", " ")
    sentence = sentence.replace(" ca n't", "can't")
    sentence = sentence.replace("wo n't", "won't")

    sentence = sentence.replace("ai n't", "ain't")

    sentence = sentence.replace(" n't", " not")

    sentence = sentence.replace("i 'm ", "i'm ")
    sentence = sentence.replace(" i 'm", " i'm")

    sentence = sentence.replace("youi", "you i")
    sentence = sentence.replace("buti", "but i")
    sentence = sentence.replace("gon na", "going")

    return sentence


def construct_candidate_words(sentence: str) -> list[str]:
    """Return normalized non-numeric words that are eligible for counting."""
    tokenized_words = str_tokenize_words(normalize_strong(sentence))
    words = [
        word
        for word in tokenized_words
        if not is_number_token(word) and "-" not in word and len(word) > 1
    ]
    replaced_words = (REPLACE_TABLE.get(word, word) for word in words)
    return [
        token
        for replaced_word in replaced_words
        for token in str_tokenize_words(replaced_word)
    ]


def main():

    embed_set = read_embedded_dict()
    embed_set.update(read_names().keys())

    print("Loading dataset...")
    dataset = load_dataset(DATASET_NAME, split=SPLIT)
    total_sentences = len(dataset)
    if MAX_SENTENCES is not None:
        total_sentences = min(total_sentences, MAX_SENTENCES)
    print(f"Total sentences: {total_sentences:,}")

    new_word_counts: Counter[str] = Counter()
    new_words: set[str] = set()

    logged_sentences = 0

    with (
        open(NEW_WORDS_SENTENCES_FILE, "w", encoding="utf-8", newline="\n") as output
    ):
        for sentence_id in range(total_sentences):
            original_text = dataset[sentence_id]["text"]

            words = construct_candidate_words(original_text)

            sentence_new_word_counts = Counter(
                word for word in words if word not in embed_set
            )
            sentence_new_words = set(sentence_new_word_counts)
            unseen_new_words = sentence_new_words - new_words

            if sentence_new_words:
                item = {
                    "id": sentence_id,
                    "original_text": original_text
                }
                output.write(json.dumps(item, ensure_ascii=False) + "\n")

                output.flush()
                new_word_counts.update(sentence_new_word_counts)
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

    sorted_new_word_counts = dict(
        sorted(
            new_word_counts.items(),
            key=lambda item: (-item[1], item[0].lower(), item[0]),
        )
    )
    with open(NEW_WORDS_COUNTS_FILE, "w", encoding="utf-8", newline="\n") as output:
        json.dump(sorted_new_word_counts, output, ensure_ascii=False, indent=2)
        output.write("\n")

    print("=" * 60)
    print("DONE:")
    print(f"new words:  {len(new_words):,} -> {NEW_WORDS_FILE}")
    print(f"word counts: {len(new_word_counts):,} -> {NEW_WORDS_COUNTS_FILE}")
    print(f"sentences:  {logged_sentences:,} -> {NEW_WORDS_SENTENCES_FILE}")


if __name__ == "__main__":
    main()
