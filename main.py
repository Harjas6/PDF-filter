import csv
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from pydantic import BaseModel, Field

load_dotenv()
SLIDES_DIR = Path(__file__).parent / "input_slides"
MODEL_PDF = os.getenv("MODEL_PDF")
API_KEY = os.getenv("API_KEY")
SYSTEM_PROMPT = (Path(__file__).parent / "system_prompt.txt").read_text(
    encoding="utf-8"
)


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


pdf_files = list(SLIDES_DIR.glob("*.pdf"))
client = genai.Client(api_key=API_KEY)
test_pdf_path = SLIDES_DIR / "test_slides.pdf"
test_pdf = client.files.upload(file=test_pdf_path)

interaction = client.interactions.create(
    model=MODEL_PDF,
    system_instruction=SYSTEM_PROMPT,
    stream=False,
    input=[
        {
            "type": "document",
            "uri": test_pdf.uri,
            "mime_type": test_pdf.mime_type,
        },
    ],
    response_format={
        "type": "text",
        "mime_type": "application/json",
        "schema": DocumentAnalysis.model_json_schema(),
    },
)
if interaction.output_text is None:
    raise ValueError("No output text received from the model interaction.")
document_analysis = DocumentAnalysis.model_validate_json(interaction.output_text)

if not document_analysis.pages:
    raise ValueError("No pages found in the document analysis.")

for page in document_analysis.pages:
    page.file_name = test_pdf_path.name

output_path = Path(__file__).parent / f"{test_pdf_path.stem}_analysis.csv"

with output_path.open("w", newline="", encoding="utf-8") as csvfile:
    writer = csv.DictWriter(
        csvfile,
        fieldnames=[
            "file_name",
            "page_num",
            "classification",
            "justification",
        ],
    )
    writer.writeheader()

    for page in document_analysis.pages:
        writer.writerow(page.model_dump())

print(f"Analysis saved to {output_path}")
