
from pathlib import Path


def str_tokenize_words(s: str):
    import re

    s = re.findall("(\.?\w[\w'\.&-]*\w|\w\+*#?)", s)
    if s: return s
    return []


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

