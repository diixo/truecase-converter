
import json
import os
import nltk

import truecase

from datasets import load_dataset

from utils import str_tokenize_words, read_embedded_dict


word_set = read_embedded_dict()

# Загружаем необходимый ресурс NLTK
try:
    nltk.data.find('tokenizers/punkt_tab')
except LookupError:
    print("Downloading NLTK punkt_tab resource...")
    nltk.download('punkt_tab')


DATASET_NAME = "aitetic/bookcorpus"
SPLIT = "train"

OUTPUT_FILE = "bookcorpus_truecased.jsonl"
REJECTED_FILE = "bookcorpus_rejected.jsonl"
NEW_WORDS_FILE = "bookcorpus_new_words.txt"

# Для теста.
# Например 1000.
# Для полного датасета -> None
MAX_SENTENCES = 1000
MAX_SENTENCES = None

# Лог каждые N предложений
LOG_EVERY = 100

# Если True, при повторном запуске продолжит с того места,
# где остановился.
RESUME = True


def valid_truecase(original, generated) -> bool:
    return original.lower() == generated.lower()


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

# ============================================================
# LOAD DATASET
# ============================================================

print("Loading dataset...")

dataset = load_dataset(DATASET_NAME, split=SPLIT)

total_sentences = len(dataset)

if MAX_SENTENCES is not None:
    total_sentences = min(total_sentences, MAX_SENTENCES)

print(f"Total sentences: {total_sentences:,}")


def get_resume_position():

    if not RESUME:
        return 0

    if not os.path.exists(OUTPUT_FILE):
        return 0

    print("Existing output found. Checking resume position...")

    last_id = -1

    with open(OUTPUT_FILE, "r", encoding="utf-8", ) as f:

        for line in f:

            line = line.strip()

            if not line:
                continue
            try:

                item = json.loads(line)

                last_id = max(last_id, item["id"])

            except Exception:
                continue

    start = last_id + 1

    print(f"Resume from sentence: {start:,}")

    return start


# ============================================================
# MAIN
# ============================================================

def main():

    start_index = get_resume_position()

    accepted = 0
    rejected = 0
    new_words = set()

    file_mode = "a" if start_index > 0 else "w"
    if start_index > 0 and os.path.exists(NEW_WORDS_FILE):
        with open(NEW_WORDS_FILE, "r", encoding="utf-8") as fnew:
            new_words = {line.strip() for line in fnew if line.strip()}

    with open(OUTPUT_FILE, file_mode, encoding="utf-8") as fout, open(REJECTED_FILE, file_mode, encoding="utf-8") as frej:

        for sentence_id in range(start_index, total_sentences):

            original_text = dataset[sentence_id]["text"]
            words = set(str_tokenize_words(original_text))
            new_words.update(words - word_set)

            normalized = normalize_sentence(original_text)

            try:
                # Используем truecase.get_true_case для обработки
                if not normalized or len(normalized.strip()) == 0:
                    print(f"SKIPPED sentence {sentence_id}: empty after normalization")
                    rejected += 1
                    continue

                truecased = truecase.get_true_case(normalized)
                truecased = truecased.strip()

                # Проверяем валидность
                valid = valid_truecase(normalized, truecased)

                if valid and normalized != truecased:
                    accepted += 1
                    final_text = truecased
                elif valid and normalized == truecased:
                    forced_truecased = force_capitalize_first_letter(normalized)

                    if forced_truecased != normalized:
                        accepted += 1
                        final_text = forced_truecased
                        print(f"FORCED sentence {sentence_id}: {normalized} -> {forced_truecased}")
                    else:
                        rejected += 1
                        final_text = normalized
                        print(f"REJECTED sentence {sentence_id}: no change: {normalized}")
                        rejected_row = {
                            "id": sentence_id,
                            "original": original_text,
                            "input": normalized,
                            "truecased": truecased,
                        }
                        frej.write(json.dumps(rejected_row, ensure_ascii=False) + "\n")
                else:
                    rejected += 1
                    final_text = normalized
                    print(f"REJECTED sentence {sentence_id}: validation failed\n")
                    #print(f"INPUT : {normalized}")
                    #print(f"OUTPUT: {truecased}")
                    #print()

                    rejected_row = {
                        "id": sentence_id,
                        "original": original_text,
                        "input": normalized,
                        "truecased": truecased,
                    }
                    frej.write(json.dumps(rejected_row, ensure_ascii=False) + "\n")

            except Exception as e:
                print(f"ERROR sentence {sentence_id}: {type(e).__name__}: {e}")
                print(f"  Input text: {repr(normalized[:100])}")
                rejected += 1
                final_text = normalized
                valid = False

            # Записываем результат
            row = {
                "id": sentence_id,
                "text": original_text,
                "truecased": final_text,
                "truecase_valid": valid,
            }

            fout.write(json.dumps(row, ensure_ascii=False) + "\n")

            # Логируем прогресс
            if (sentence_id + 1) % LOG_EVERY == 0:
                processed = accepted + rejected
                success_rate = (accepted / processed if processed else 0)
                
                print(
                    f"processed={sentence_id + 1:,} | "
                    f"accepted={accepted:,} | "
                    f"rejected={rejected:,} | "
                    f"success={success_rate:.2%}"
                )

            fout.flush()
            frej.flush()

    sorted_new_words = sorted(new_words, key=lambda x: (x.lower(), x))
    with open(NEW_WORDS_FILE, "w", encoding="utf-8") as fnew:
        for w in sorted_new_words:
            fnew.write(w + "\n")

    print("=" * 60)
    print("DONE")
    print("=" * 60)

    print(f"accepted:   {accepted:,}")
    print(f"rejected:   {rejected:,}")
    print(f"output:     {OUTPUT_FILE}")
    print(f"new words:  {len(sorted_new_words):,} -> {NEW_WORDS_FILE}")


if __name__ == "__main__":
    main()
