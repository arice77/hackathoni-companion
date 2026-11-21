"""One working Sarvam call: a chat completion with sarvam-105b-conversations.

Run without touching the app's pinned venv:
    uv run --no-project --with sarvamai python scripts/sarvam_hello.py

Reads SARVAM_API_KEY from the environment or the git-ignored repo-root .env. Never prints it.
"""

import os
import sys
from pathlib import Path

from sarvamai import SarvamAI

env = Path(__file__).resolve().parent.parent / ".env"
if "SARVAM_API_KEY" not in os.environ and env.exists():
    for line in env.read_text().splitlines():
        if line.startswith("SARVAM_API_KEY="):
            os.environ["SARVAM_API_KEY"] = line.split("=", 1)[1].strip()

if not os.environ.get("SARVAM_API_KEY"):
    sys.exit("SARVAM_API_KEY is missing: paste it into .env after SARVAM_API_KEY=")

client = SarvamAI(api_subscription_key=os.environ["SARVAM_API_KEY"])
response = client.chat.completions(
    model="sarvam-105b-conversations",
    messages=[{"role": "user", "content": "In one short Malayalam sentence, greet a shop owner in Alappuzha."}],
)
print(response.choices[0].message.content)
