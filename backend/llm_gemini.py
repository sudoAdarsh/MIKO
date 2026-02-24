import json
import re
import requests

def gemini_answer(api_key: str, prompt: str) -> str:
    if not api_key:
        raise ValueError("Missing Gemini API key")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ]
    }

    r = requests.post(url, json=payload, timeout=30)

    if r.status_code != 200:
        raise RuntimeError(f"Gemini API error: {r.status_code} - {r.text}")

    data = r.json()

    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        raise RuntimeError(f"Unexpected Gemini response format: {data}")
    


def _extract_json(text: str) -> dict:
    # Gemini sometimes wraps JSON in ```json ... ```
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError("No JSON object found in extractor output")
    return json.loads(m.group(0))

def gemini_extract_memories(api_key: str, message: str) -> list[dict]:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"

    prompt = f"""
You extract long-term memory from a user's chat message for an interview-prep assistant.

Only extract if it is STABLE and useful later:
- personal background (role, level, domain)
- goals (target role/company, timeline)
- preferences (learning style, constraints)
- weaknesses/strengths
- hard constraints (time per day, deadlines)

Do NOT extract:
- greetings, filler, single-use requests
- temporary stuff ("today", "right now") unless it's a deadline
- the assistant's own text

Return STRICT JSON only in this exact schema:
{{
  "memories": [
    {{
      "text": "short canonical memory sentence",
      "kind": "fact|goal|preference|weakness|strength|constraint",
      "confidence": 0.0
    }}
  ]
}}

If nothing important, return:
{{ "memories": [] }}

User message:
{message}
""".strip()

    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    r = requests.post(url, json=payload, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"Gemini API error: {r.status_code} - {r.text}")

    data = r.json()
    out = data["candidates"][0]["content"]["parts"][0]["text"]
    parsed = _extract_json(out)
    return parsed.get("memories", [])