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
TIMEOUT = 300_000  # ms


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
    print(
        f"Uploading {pdf_file.name}\n ({pdf_file.stat().st_size / (1024 * 1024):.2f} MB)"
    )
    pdf = client.files.upload(file=pdf_file)
    print(f"File uploaded: {pdf.uri}")
    print(f"Sending {pdf_file.name} to model")
    stream = client.interactions.create(
        model=MODEL_PDF,
        system_instruction=SYSTEM_PROMPT,
        stream=True,
        input=[{"type": "document", "uri": pdf.uri, "mime_type": pdf.mime_type}],
        response_format={
            "type": "text",
            "mime_type": "application/json",
            "schema": DocumentAnalysis.model_json_schema(),
        },
    )
    response_chunks = []
    completed = False
    for event in stream:
        event_type = event.event_type
        print(f"Received event: {event_type}")

        if event_type == "interaction.created":
            print(f"Interaction created: {event.interaction.id}")

        elif event_type == "step.start":
            print(f"Started step: {event.step.type}")

        elif event_type == "step.delta":
            if event.delta.type == "text":
                text = event.delta.text
                response_chunks.append(text)
                print(text, end="", flush=True)

        elif event_type == "step.stop":
            print("\nStep finished.")

        elif event_type == "interaction.completed":
            completed = True
            print("\nInteraction completed.")

            usage = getattr(event.interaction, "usage", None)
            if usage:
                print(f"Total tokens: {usage.total_tokens}")
                print(f"Input tokens: {usage.total_input_tokens}")
                print(f"Output tokens: {usage.total_output_tokens}")
                print(f"Thought tokens: {usage.total_thought_tokens}")

        elif event_type == "error":
            raise RuntimeError(f"Gemini streaming error: {event.error}")
    if not completed:
        raise RuntimeError("Gemini streaming did not complete successfully.")
    return "".join(response_chunks)


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
    client = genai.Client(
        api_key=API_KEY,
        http_options={"timeout": TIMEOUT},
    )
    pdf_files = sorted(SLIDES_DIR.glob("*.pdf"))
    processed_files = get_processed_files()

    for pdf_file in pdf_files:
        if pdf_file.name in processed_files:
            # if crash midway file will still count as processed so keep in mind
            print(f"Skipping already processed file: {pdf_file.name}")
            continue
        print(f"\nProcessing: {pdf_file.name}")
        response = send_file(client, pdf_file)
        print(f"Received interaction response for {pdf_file.name}")

        if not response:
            raise ValueError("No output text received from the model interaction.")

        document_analysis = DocumentAnalysis.model_validate_json(response)

        if not document_analysis.pages:
            raise ValueError(f"No pages found in {pdf_file.name}.")

        print(f"Received {len(document_analysis.pages)} page classifications")
        for page in document_analysis.pages:
            page.file_name = pdf_file.name

        write_classifications(document_analysis)
        processed_files.add(pdf_file.name)
        # will have one extra sleep but whatever
        print(f"Sleeping for {DELAY_BETWEEN_REQUESTS} seconds before next request...")
        time.sleep(DELAY_BETWEEN_REQUESTS)
        print("Finished processing waiting, starting next request...\n")


if __name__ == "__main__":
    # uncomment to start fresh each run
    # OUTPUT_PATH.unlink(missing_ok=True)
    gemini_calls()
    create_pruned_pdfs()
