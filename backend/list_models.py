from dotenv import load_dotenv

load_dotenv(".env")

from google import genai

client = genai.Client()
for m in client.models.list():
    actions = getattr(m, "supported_actions", None)
    if not actions or "generateContent" in actions:
        print(m.name)
