
from pathlib import Path
import json
import re


def str_tokenize_words(s: str):
    # removed defis from original
    s = re.findall("(\.?\w[\w'\.&]*\w|\w\+*#?)", s)
    if s: return s
    return []


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


def read_embedded_dict() -> set:
    word_set = set()

    path = Path("data/db-full.txt")
    with path.open("r", encoding="utf-8") as f:
        word_list = [line.strip() for line in f if line.strip()]

        for w in word_list:
            if w not in word_set:
                word_set.add(w)
            else:
                print("###:", w)

    print(f"db-full.sz={len(word_set)}")
    return word_set


def read_names(input_path: str = "data/person_names_truecase.json") -> dict[str, str]:
    path = Path(input_path)
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data


if __name__ == "__main__":

    names = read_names()
    print(f"Read names: {len(names)}")
