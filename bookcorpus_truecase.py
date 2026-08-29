
import json
import os
import re


from datasets import load_dataset

from utils import str_tokenize_words, read_embedded_dict


word_set = read_embedded_dict()


DATASET_NAME = "aitetic/bookcorpus"
SPLIT = "train"

OUTPUT_FILE = "bookcorpus_truecased.jsonl"

NEW_WORDS_FILE = "bookcorpus_new_words.txt"

# Для теста.
# Например 1000.
# Для полного датасета -> None
MAX_SENTENCES = 1000

# Лог каждые N предложений
LOG_EVERY = 100


RESUME = True



def normalize_sentence(sentence: str) -> str:

    sentence = sentence.replace(" .", ".")
    sentence = sentence.replace(" ,", ",")
    sentence = sentence.replace(" ?", "?")
    sentence = sentence.replace(" !", "!")
    sentence = sentence.replace(" '", "'")
    sentence = sentence.replace("''", "\"")
    sentence = sentence.replace("``", "\"")
    sentence = sentence.replace(" n't", "n't")
    sentence = sentence.replace(" ...", "...")

    sentence = sentence.replace(".-", ". -")
    sentence = re.sub(r"\.([^\W\d_])", r". \1", sentence)

    if sentence.startswith("\" "):
        sentence = "\"" + sentence[2:].lstrip()

    sentence = sentence.strip()
    return sentence


def force_capitalize_first_letter(sentence: str) -> str:
    # Поднимаем первую встретившуюся буквенную позицию.
    chars = list(sentence)
    for i, ch in enumerate(chars):
        if ch.isalpha():
            chars[i] = ch.upper()
            break
    return "".join(chars)


print("Loading dataset...")

dataset = load_dataset(DATASET_NAME, split=SPLIT)

total_sentences = len(dataset)

if MAX_SENTENCES is not None:
    total_sentences = min(total_sentences, MAX_SENTENCES)

print(f"Total sentences: {total_sentences:,}")


def get_resume_position():

    if not RESUME:
        return 0

    print("Existing output found. Checking resume position...")

    last_id = -1

    with open(OUTPUT_FILE, "r", encoding="utf-8", ) as f:

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

    new_words = set()

    #file_mode = "a" if start_index > 0 else "w"
    if start_index > 0 and os.path.exists(NEW_WORDS_FILE):
        with open(NEW_WORDS_FILE, "r", encoding="utf-8") as fnew:
            new_words = {line.strip() for line in fnew if line.strip()}


    for sentence_id in range(start_index, total_sentences):

        original_text = dataset[sentence_id]["text"]

        normalized = normalize_sentence(original_text)

        words = set(str_tokenize_words(normalized))
        new_words.update(words - word_set)



    sorted_new_words = sorted(new_words, key=lambda x: (x.lower(), x))
    with open(NEW_WORDS_FILE, "w", encoding="utf-8") as fnew:
        for w in sorted_new_words:
            fnew.write(w + "\n")


    print("=" * 60)
    print("DONE")
    print("=" * 60)

    print(f"output:     {OUTPUT_FILE}")
    print(f"new words:  {len(sorted_new_words):,} -> {NEW_WORDS_FILE}")


if __name__ == "__main__":
    main()
