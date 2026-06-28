from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types


DEFAULT_MODEL = "gemini-3.5-flash"


def load_api_key() -> str:
    load_dotenv(".env")
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_GENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Set GEMINI_API_KEY, GOOGLE_API_KEY, or GOOGLE_GENAI_API_KEY in .env")
    return api_key


def model_call_to_dict(function_call: types.FunctionCall) -> dict[str, Any]:
    return {
        "name": function_call.name,
        "args": dict(function_call.args or {}),
        "id": function_call.id,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Return one Gemini Computer Use action for a browser screenshot.")
    parser.add_argument("--screenshot", type=Path, required=True)
    parser.add_argument("--instruction", required=True)
    parser.add_argument("--model", default=os.getenv("GEMINI_COMPUTER_USE_MODEL", DEFAULT_MODEL))
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    client = genai.Client(api_key=load_api_key())
    response = client.models.generate_content(
        model=args.model,
        contents=[
            types.Part.from_text(text=args.instruction),
            types.Part.from_bytes(data=args.screenshot.read_bytes(), mime_type="image/png"),
        ],
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

    calls = []
    texts = []
    for candidate in response.candidates or []:
        if not candidate.content or not candidate.content.parts:
            continue
        for part in candidate.content.parts:
            if part.function_call:
                calls.append(model_call_to_dict(part.function_call))
            if part.text:
                texts.append(part.text)

    payload = {
        "model": args.model,
        "response_id": response.response_id,
        "function_calls": calls,
        "text": "\n".join(texts),
        "computer_use": {
            "environment": "ENVIRONMENT_BROWSER",
            "native_injection_defense": "built_in_computer_use_tool_enabled",
            "sdk_exposes_explicit_flag": False,
        },
    }
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
