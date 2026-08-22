import json
from pathlib import Path

JSONL_FILE = "bookcorpus_truecased.jsonl"
SEARCH_FIELD = "input"
QUERY = "pesh"
CASE_SENSITIVE = False
LIMIT = 0  # 0 = без лимита


def resolve_search_value(record: dict, field: str):
    if field in record:
        return record[field]

    if field == "input":
        for fallback in ("text", "original"):
            if fallback in record:
                return record[fallback]

    return None


def search_jsonl(path: Path, query: str, field: str, case_sensitive: bool, limit: int):
    found = 0
    lowered_query = query if case_sensitive else query.lower()

    with path.open("r", encoding="utf-8") as f:
        for line_index, line in enumerate(f):
            line = line.strip()
            if not line:
                continue

            item = json.loads(line)
            value = resolve_search_value(item, field)
            if not isinstance(value, str):
                continue

            haystack = value if case_sensitive else value.lower()
            if lowered_query not in haystack:
                continue

            result = {
                "line_index": line_index,
                "id": item.get("id"),
                "value": value,
                "record": item,
            }
            print(json.dumps(result, ensure_ascii=False))
            found += 1

            if limit and found >= limit:
                break

    print(f"Found: {found}")


def main():
    path = Path(JSONL_FILE)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if LIMIT < 0:
        raise ValueError("LIMIT must be >= 0")

    search_jsonl(
        path=path,
        query=QUERY,
        field=SEARCH_FIELD,
        case_sensitive=CASE_SENSITIVE,
        limit=LIMIT,
    )


if __name__ == "__main__":
    main()
