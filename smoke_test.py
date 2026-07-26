"""Minimal first call to confirm authentication, model access, and response parsing."""

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()
client = Anthropic()

MODEL = "claude-opus-5"

response = client.messages.create(
    model=MODEL,
    max_tokens=1024,
    messages=[
        {
            "role": "user",
            "content": (
                "A pytest assertion fails with: assert 0 == 1. "
                "In one sentence, what should I check first?"
            ),
        }
    ],
)

print("Block types:", [block.type for block in response.content])

text = next((b.text for b in response.content if b.type == "text"), "")
print("\nText:", text)

print("\nModel:", response.model)
print("Stop reason:", response.stop_reason)
print("Input tokens:", response.usage.input_tokens)
print("Output tokens:", response.usage.output_tokens)
