from __future__ import annotations

import os
from argparse import ArgumentParser
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types


DEFAULT_COMPUTER_USE_MODEL = "gemini-2.5-computer-use-preview-10-2025"


@dataclass(frozen=True)
class SmokeResult:
    model: str
    function_call_name: str
    function_call_args: dict[str, Any]
    response_id: str | None


def load_api_key() -> str:
    load_dotenv(".env")
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_GENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Set GEMINI_API_KEY, GOOGLE_API_KEY, or GOOGLE_GENAI_API_KEY in .env")
    return api_key


def run_smoke(screenshot_path: Path | None = None, instruction: str | None = None) -> SmokeResult:
    api_key = load_api_key()
    model = os.getenv("GEMINI_COMPUTER_USE_MODEL", DEFAULT_COMPUTER_USE_MODEL)
    client = genai.Client(api_key=api_key)
    prompt = instruction or (
        "You are controlling a browser for a local paper brokerage demo. "
        "The page has a button labeled Start run. Return the next computer-use action."
    )
    contents: str | list[types.Part]
    if screenshot_path:
        contents = [
            types.Part.from_text(text=prompt),
            types.Part.from_bytes(data=screenshot_path.read_bytes(), mime_type="image/png"),
        ]
    else:
        contents = prompt

    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=types.GenerateContentConfig(
            tools=[
                types.Tool(
                    computer_use=types.ComputerUse(
                        environment=types.Environment.ENVIRONMENT_BROWSER,
                    )
                )
            ],
            temperature=0,
        ),
    )

    for candidate in response.candidates or []:
        if not candidate.content or not candidate.content.parts:
            continue
        for part in candidate.content.parts:
            if part.function_call:
                return SmokeResult(
                    model=model,
                    function_call_name=part.function_call.name,
                    function_call_args=dict(part.function_call.args or {}),
                    response_id=response.response_id,
                )

    raise RuntimeError("Gemini computer-use smoke did not return a function_call")


def main() -> None:
    parser = ArgumentParser(description="Verify Gemini Computer Use returns browser actions.")
    parser.add_argument("--screenshot", type=Path, help="Optional browser screenshot to send to Gemini.")
    parser.add_argument(
        "--instruction",
        help="Optional instruction. Example: 'Click the Confirm Order button. Return the next action only.'",
    )
    args = parser.parse_args()

    result = run_smoke(args.screenshot, args.instruction)
    print(f"model={result.model}")
    print(f"function_call={result.function_call_name}")
    print(f"function_call_args={result.function_call_args}")
    print(f"response_id={result.response_id}")


if __name__ == "__main__":
    main()
