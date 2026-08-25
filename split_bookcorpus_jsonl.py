import json
from pathlib import Path

from datasets import load_dataset


DATASET_NAME = "aitetic/bookcorpus"
SPLIT = "train"
CHUNK_SIZE = 10_000
OUTPUT_DIR = Path("splitted")
OUTPUT_PREFIX = "bookcorpus_part"
MAX_SPLIT_FILES = 2000  # 0 = без лимита


def write_chunk(chunk, chunk_index: int) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_{chunk_index:05d}.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for row in chunk:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return out_path


def main():
    if MAX_SPLIT_FILES < 0:
        raise ValueError("MAX_SPLIT_FILES must be >= 0")

    print(f"Loading dataset: {DATASET_NAME} [{SPLIT}]")
    dataset = load_dataset(DATASET_NAME, split=SPLIT)
    total = len(dataset)
    print(f"Total records: {total:,}")

    chunk = []
    chunk_index = 1
    written = 0

    for record_index, row in enumerate(dataset):
        if MAX_SPLIT_FILES and chunk_index > MAX_SPLIT_FILES:
            break

        item = dict(row)
        chunk.append(
            {
                "id": item.get("id", record_index),
                "text": item.get("text", ""),
            }
        )
        if len(chunk) == CHUNK_SIZE:
            out_path = write_chunk(chunk, chunk_index)
            written += len(chunk)
            print(f"Wrote {out_path} | records: {len(chunk):,} | total written: {written:,}")
            chunk_index += 1
            chunk = []

    if chunk and (not MAX_SPLIT_FILES or chunk_index <= MAX_SPLIT_FILES):
        out_path = write_chunk(chunk, chunk_index)
        written += len(chunk)
        print(f"Wrote {out_path} | records: {len(chunk):,} | total written: {written:,}")

    print("Done")
    print(f"Output dir: {OUTPUT_DIR}")
    print(f"Total written: {written:,}")


if __name__ == "__main__":
    main()
