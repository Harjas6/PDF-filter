import csv
import shutil
from pathlib import Path

import pymupdf

BASE_DIR = Path(__file__).parent
INPUT_DIR = BASE_DIR / "input_slides"
OUTPUT_DIR = BASE_DIR / "pruned_slides"
ARCHIVE_DIR = BASE_DIR / "archived_slides"
CSV_PATH = BASE_DIR / "slide_classification.csv"


def read_classifications():
    pages_to_keep = {}

    with CSV_PATH.open("r", newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)

        for row in reader:
            if row["classification"].strip().lower() == "true":
                file_name = row["file_name"]
                page_num = int(row["page_num"])

                pages_to_keep.setdefault(file_name, set()).add(page_num)

    return pages_to_keep


def create_pruned_pdfs():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    pages_to_keep = read_classifications()

    for file_name, page_numbers in pages_to_keep.items():
        input_path = INPUT_DIR / file_name
        output_path = OUTPUT_DIR / f"{Path(file_name).stem}_pruned.pdf"

        if not input_path.is_file():
            print(f"File not found, skipping: {input_path}")
            continue

        with pymupdf.open(input_path) as source, pymupdf.open() as output:
            for page_num in sorted(page_numbers):
                page_index = page_num - 1  # CSV is one-based

                if not 0 <= page_index < len(source):
                    raise ValueError(
                        f"Invalid page {page_num} in {file_name}; "
                        f"document has {len(source)} pages."
                    )

                output.insert_pdf(
                    source,
                    from_page=page_index,
                    to_page=page_index,
                )

            output.save(output_path)

        shutil.move(str(input_path), str(ARCHIVE_DIR / file_name))

        print(f"Created: {output_path}")


if __name__ == "__main__":
    create_pruned_pdfs()
