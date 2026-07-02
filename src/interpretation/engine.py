import json
from openai import OpenAI
from .prompt import build_messages
from .schema import Interpretation

client = OpenAI()

def run_interpretation(user_text: str) -> Interpretation:
    messages = build_messages(user_text)

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=messages,
        temperature=0.2
    )

    raw = response.choices[0].message.content

    data = json.loads(raw)

    return Interpretation(**data)
