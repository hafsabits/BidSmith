"""The one place BidSmith Lite talks to Claude.

extract_facts() sends RFP text to Claude and gets back an RfpFacts object.
Claude only reads and classifies here. It never makes the bid decision.
"""

import os
from datetime import date

import anthropic

from app.schemas import RfpFacts

MODEL = "claude-haiku-5-5"

SYSTEM_PROMPT = """You are a capture analyst at a commercial construction firm.
You read federal solicitations (RFPs) and extract the facts a bid committee needs.
Extract only what the text supports. If a fact is not stated, use null.
Do not guess dollar values or dates."""


class ExtractionError(Exception):
    """Claude could not return usable facts for this RFP."""


def extract_facts(rfp_text: str) -> RfpFacts:
    client = anthropic.Anthropic(
        api_key=os.environ["ANTHROPIC_API_KEY"],
        base_url="https://api.anthropic.com",
    )
    response = client.messages.parse(
        model=MODEL,
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"Today's date: {date.today().isoformat()}\n\n<rfp>\n{rfp_text}\n</rfp>",
            }
        ],
        output_format=RfpFacts,
        output_config={"effort": "low"},
    )
    if response.stop_reason == "refusal":
        raise ExtractionError("Claude declined to process this text.")
    if response.stop_reason == "max_tokens" or response.parsed_output is None:
        raise ExtractionError(f"Claude's answer was incomplete (stop_reason={response.stop_reason}).")
    return response.parsed_output


if __name__ == "__main__":
    # Try it from the project root: python -m app.extract samples/office_minneapolis.txt
    import sys

    from dotenv import load_dotenv

    load_dotenv()
    with open(sys.argv[1]) as f:
        facts = extract_facts(f.read())
    print(facts.model_dump_json(indent=2))