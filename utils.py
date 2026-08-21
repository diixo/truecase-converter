
from pathlib import Path
import json


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

Person_names = [
    'Aaron', 'Adam', 'Airis', 'Alan', "Alex", 'Alexander', 'Alfred', 'Alice', "Allegra", 'Amanda', 'Amber', 'Amelia', 'Amy',
    'Anatole', 'Anna', 'Audrey', 'Anastasia', 'Andrew', 'Angela', 'Angelina', 'Anthony', 'Arthur', 'Ashley',
    'Barbara', 'Benjamin', 'Betty', 'Bill', 'Bob', 'Brad', 'Brandon', 'Brenda', 'Brian', 'Bruce', 'Bryan', "Benedict",
    'Cameron', 'Carl', 'Carlos', 'Carol', 'Caroline', 'Carolyn', 'Casey', 'Catherine', 'Cecil', 'Cedric', 'Charles', 'Charlie',
    'Charlotte', 'Cheryl', "Chris", 'Christian', 'Christine', 'Christopher', 'Christy', 'Cindy', 'Clara', 'Crystal', 'Cynthia',
    'Daniel', 'David', 'Deborah', 'Dennis', 'Diana', 'Diane', 'Donald', 'Donna', 'Dorothy', "Dylan",
    'Edward', 'Eleanor', "Elliot", "Elvis", 'Elizabeth', 'Emily', 'Emma', 'Eric', 'Ethan', 'Eve', 'Evelyn',
    'Frank', 'Frederick',
    'Gabriel', 'Gabriella', 'Gary', 'George', 'Gerald', 'Grace', 'Gregory', "Greg",
    'Hannah', 'Halle', 'Harold', 'Helen', 'Henry', 'Howard', 'Hugh',
    'Ian', 'Isaac', 'Isabella', 'Ivan', 
    'Jack', 'Jacob', 'Jake', 'James', 'Jamie', 'Jane', 'Jason', 'Jasper', 'Jay', 'Jeff', 'Jeffrey',
    'Jennifer', 'Jenny', 'Jeremy', 'Jerome', 'Jerry', 'Jesse', 'Jessica', 'Jim', 'Jimmy', 'Joe', 'Joel',
    'John', 'Jonathan', 'Jordan', 'Jose', 'Joseph', 'Josh', 'Joshua', 'Julia', 'Justin',
    'Karen', "Kate", 'Katherine', 'Kathleen', 'Katie', 'Keith', 'Kenneth', 'Kevin', 'Kimberly', 'Kyle',
    'Larry', 'Laura', "Lewis", 'Linda', 'Lisa', 'Liz',
    'Margaret', 'Maria', 'Mark', 'Martin', 'Mary', 'Matthew', 'Megan', 'Melanie', 'Melissa', 'Michael', 'Michelle', "Mike", 'Molly', 'Monica', 'Morgan',
    'Nancy', 'Natalie', 'Nathan', 'Nicholas', 'Nicole',
    'Oliver', 'Olivia', 'Oscar',
    'Pamela', 'Patrick', 'Paul', 'Peter', 'Philip', "Phil", "Priscilla",
    'Rachel', "Randy", "Ralph", 'Raymond', 'Rebecca', "Richard", 'Robert', 'Roger', 'Ronald', 'Ryan', "Ronny", "Ronnie", "Robin",
    "Sabrina", 'Samantha', 'Samuel', 'Sandra', 'Sarah', 'Scarlett', 'Scott', 'Sharon', 'Shirley', 'Sophia', 'Stephanie', 'Stephen', 'Steven', 'Susan', "Simon", "Simona",
    'Teddy', 'Terry', "Terence", 'Theodore', 'Thomas', 'Tim', 'Timothy', 'Tina', 'Tom', 'Tyler', "Tony",
    'Vanessa', 'Veronica', 'Victor', 'Victoria', 'Vincent',
    'Walter', "Warren", 'William', "Winston", "Wesley", "Woodrow"
    ]


# def build_person_names_truecase_map() -> dict[str, str]:
#     person_map: dict[str, str] = {}

#     for name in Person_names:
#         key = name.lower()
#         if key in person_map and person_map[key] != name:
#             raise ValueError(f"Conflicting truecase for key '{key}': '{person_map[key]}' vs '{name}'")
#         person_map[key] = name

#     return person_map


# def write_person_names_json(output_path: str = "data/person_names_truecase.json") -> None:
#     person_map = build_person_names_truecase_map()
#     path = Path(output_path)
#     path.parent.mkdir(parents=True, exist_ok=True)
#     with path.open("w", encoding="utf-8") as f:
#         json.dump(person_map, f, ensure_ascii=False, indent=2, sort_keys=True)
#         f.write("\n")


def read_names(input_path: str = "data/person_names_truecase.json") -> dict[str, str]:
    path = Path(input_path)
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data


if __name__ == "__main__":
    #write_person_names_json()
    print(f"Person names: {len(Person_names)}")
    names = read_names()
    print(f"Read names: {len(names)}")
