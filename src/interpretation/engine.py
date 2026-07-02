import json
import requests

from interpretation.prompt import build_messages
from interpretation.schema import Interpretation

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.2:3b"


def run_interpretation(user_text: str) -> Interpretation:
    messages = build_messages(user_text)

    prompt = "\n".join(
        [f"{m['role']}: {m['content']}" for m in messages]
    )

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
        },
        timeout=60,
    )

    response.raise_for_status()

    raw = response.json()["response"].strip()

    # Remove Markdown if the model wraps JSON in code fences
    raw = raw.replace("```json", "").replace("```", "").strip()

    print("\n===== RAW MODEL OUTPUT =====")
    print(raw)
    print("============================\n")
    
    data = json.loads(raw)

    return Interpretation(**data)