import csv
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from pydantic import BaseModel, Field

from prune import create_pruned_pdfs

load_dotenv()

BASE_DIR = Path(__file__).parent
SLIDES_DIR = BASE_DIR / "input_slides"
OUTPUT_PATH = BASE_DIR / "slide_classification.csv"
MODEL_PDF = os.getenv("MODEL_PDF")
API_KEY = os.getenv("API_KEY")
SYSTEM_PROMPT = (BASE_DIR / "system_prompt.txt").read_text(encoding="utf-8")
DELAY_BETWEEN_REQUESTS = 60  # seconds
FIELDNAMES = ["file_name", "page_num", "classification", "justification"]


class PageAnalysis(BaseModel):
    file_name: str = Field(description="The name of the PDF file this page belongs to")
    page_num: int = Field(description="The page number of the file")
    classification: bool = Field(
        description="True if page relevant and should be kept, False if it should be deleted"
    )
    justification: str = Field(
        description="A brief justification for the classification"
    )


class DocumentAnalysis(BaseModel):
    pages: list[PageAnalysis] = Field(
        description="A list of page analyses for the document"
    )


def get_processed_files():
    if not OUTPUT_PATH.exists() or OUTPUT_PATH.stat().st_size == 0:
        return set()

    with OUTPUT_PATH.open("r", newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        return {row["file_name"] for row in reader}


def send_file(client, pdf_file):
    pdf = client.files.upload(file=pdf_file)
    return client.interactions.create(
        model=MODEL_PDF,
        system_instruction=SYSTEM_PROMPT,
        stream=False,
        input=[{"type": "document", "uri": pdf.uri, "mime_type": pdf.mime_type}],
        response_format={
            "type": "text",
            "mime_type": "application/json",
            "schema": DocumentAnalysis.model_json_schema(),
        },
    )


def write_classifications(document_analysis):
    file_is_empty = not OUTPUT_PATH.exists() or OUTPUT_PATH.stat().st_size == 0
    with OUTPUT_PATH.open("a", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=FIELDNAMES)
        if file_is_empty:
            writer.writeheader()
        for page in document_analysis.pages:
            writer.writerow(page.model_dump())
    print(f"Analysis saved to {OUTPUT_PATH}")


def gemini_calls():
    client = genai.Client(api_key=API_KEY)
    pdf_files = sorted(SLIDES_DIR.glob("*.pdf"))
    processed_files = get_processed_files()

    for pdf_file in pdf_files:
        if pdf_file.name in processed_files:
            # if crash midway file will still count as processed so keep in mind
            print(f"Skipping already processed file: {pdf_file.name}")
            continue

        interaction = send_file(client, pdf_file)

        if interaction.output_text is None:
            raise ValueError("No output text received from the model interaction.")

        document_analysis = DocumentAnalysis.model_validate_json(
            interaction.output_text
        )

        if not document_analysis.pages:
            raise ValueError(f"No pages found in {pdf_file.name}.")

        for page in document_analysis.pages:
            page.file_name = pdf_file.name

        write_classifications(document_analysis)
        processed_files.add(pdf_file.name)
        # will have one extra sleep but whatever
        time.sleep(DELAY_BETWEEN_REQUESTS)


if __name__ == "__main__":
    # uncomment to start fresh each run
    # OUTPUT_PATH.unlink(missing_ok=True)
    gemini_calls()
    create_pruned_pdfs()
