# PDF Page Filter

A small script that sends PDFs to Gemini, classifies each page as keep or drop, logs the results to a CSV, and saves trimmed copies of the PDFs to a new folder.

I used it on lecture slides up to 200 pages long. 

## Setup

1. Install dependencies: `pip install -r requirements.txt`
2. Add your API key and model to a `.env` file:

   ```
   GEMINI_API_KEY=your_key_here
   MODEL_PDF=gemini-3.8-flash
   ```

   I used Gemini 3.8 Flash, but any Gemini model that accepts PDFs and supports structured output will work.

3. Add your own system prompt to `system_prompt.txt`. It defines what counts as keep or drop.

4. run `python main.py`. Sometimes you have to **run it multiple** times because gemini server hangs or is busy.

Results are written to a CSV, and trimmed PDFs go in a new folder. Originals are untouched. Probably will take a second as gemini has to process them and there is a delay before sending to avoid the rate limits on free models.
