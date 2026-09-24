import os
import requests
from dotenv import load_dotenv
from pprint import pprint

load_dotenv()

API_KEY = os.getenv("OPENROUTER_API_KEY")

if not API_KEY:
    raise ValueError("OPENROUTER_API_KEY not found in .env")

url = "https://openrouter.ai/api/alpha/decisions"

payload = {
    "model": "typesafe/jev-1.13",

    "state": {
        "message": "I worked really hard but failed my interview and now I feel useless."
    },

    "questions": {
        "situation": {
            "type": "choice",
            "instructions": "Classify the primary life situation described by the user.",
            "criteria": {
                "fear_of_failure": "Fear or disappointment related to failing",
                "comparison": "Comparing oneself with others",
                "anger": "Anger or resentment",
                "grief": "Loss or grief",
                "other": "None of the above"
            }
        }
    }
}

response = requests.post(
    url,
    headers={
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    },
    json=payload,
    timeout=30
)

print("STATUS:", response.status_code)
print("\nRAW RESPONSE:")
pprint(response.json())