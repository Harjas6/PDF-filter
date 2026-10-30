# PDF Page Filter

A small script that sends PDFs to Gemini, which classifies each page as keep or drop in a CSV. It then saves a copy of each PDF with only the kept pages. Originals are moved to an archive folder, and the CSV is archived too, so you can review it later without rerunning anything.

I used it on lecture slides up to 200 pages long, on the free tier of `gemini-3.8-flash`. I think the free tier handles roughly 850-1000 pages.

## Setup

1. Create a virtual environment and install dependencies:

   ```bash
   python3 -m venv .venv && source .venv/bin/activate && python -m pip install -r requirements.txt
   ```

2. Add your API key from [Google AI Studio](https://aistudio.google.com/apikey) and a model name to a `.env` file:

   ```
   GEMINI_API_KEY=your_key_here
   MODEL_PDF=gemini-3.8-flash
   ```

   Any Gemini model that accepts PDFs and supports structured output will work.

3. Add your own system prompt to `system_prompt.txt`. It defines what counts as keep or drop.
4. Run `python main.py`. It's slow, since there's a delay between requests to avoid free-tier rate limits. If Gemini hangs or is busy, just rerun. Files that are already classified aren't sent again so tokens aren't wasted.

## Reviewing the CSV first

To inspect or edit the classifications before pruning, comment out the pruning call at the bottom of `main`. Edit the CSV, then run `python prune.py` or uncomment it and rerun `main.py`.
