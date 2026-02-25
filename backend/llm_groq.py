import json
import re
import requests

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

ALLOWED_KINDS = {"fact", "goal", "preference", "weakness", "strength", "constraint"}

def _strip_fences(s: str) -> str:
    s = s.strip()
    # remove ```json ... ``` or ``` ... ```
    s = re.sub(r"^```(?:json)?\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    return s.strip()


def groq_answer_and_memories(api_key: str, model: str, prompt: str) -> dict:
    if not api_key:
        raise RuntimeError("Missing GROQ_API_KEY")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "temperature": 0.5,
        "max_tokens": 900,
        "messages": [
            {"role": "system", "content": "You are a helpful interview-prep assistant."},
            {"role": "user", "content": prompt},
        ],
        # If Groq supports it for your model, this massively improves JSON compliance:
        "response_format": {"type": "json_object"},
    }

    r = requests.post(GROQ_URL, headers=headers, json=payload, timeout=60)

    raw_http_text = r.text
    if r.status_code != 200:
        raise RuntimeError(f"Groq API error: {r.status_code} - {raw_http_text}")

    data = r.json()
    content = data["choices"][0]["message"]["content"]
    content = _strip_fences(content)

    debug = {
        "model": model,
        "prompt": prompt,
        "raw_content": content,
        "raw_http_text": raw_http_text,
        "usage": data.get("usage", {}),
    }

    # 1) Try strict json
    out = None
    try:
        out = json.loads(content)
    except Exception:
        # 2) Try to salvage first JSON object in the text
        try:
            m = re.search(r"\{[\s\S]*\}", content)
            if m:
                out = json.loads(m.group(0))
        except Exception:
            out = None

    if not isinstance(out, dict):
        # graceful fallback but still return debug
        return {"answer": content, "memories": [], "debug": debug}

    answer = (out.get("answer") or "").strip()
    memories = out.get("memories") or []

    cleaned = []
    for m in memories:
        try:
            text = (m.get("text") or "").strip()
            kind = (m.get("kind") or "").strip()
            conf = float(m.get("confidence") or 0.0)
            if not text:
                continue
            if kind not in ALLOWED_KINDS:
                continue
            conf = max(0.0, min(1.0, conf))
            cleaned.append({"text": text, "kind": kind, "confidence": conf})
        except Exception:
            continue

    return {
        "answer": answer or content,
        "memories": cleaned,
        "debug": debug,
    }



# def groq_answer_and_memories(api_key: str, model: str, prompt: str) -> dict:
#     if not api_key:
#         raise RuntimeError("Missing GROQ_API_KEY")

#     headers = {
#         "Authorization": f"Bearer {api_key}",
#         "Content-Type": "application/json",
#     }

#     payload = {
#         "model": model,
#         "temperature": 0.5,
#         "max_tokens": 700,   # add this
#         "messages": [
#             {"role": "system", "content": "You are a helpful interview-prep assistant. Output STRICT JSON only."},
#             {"role": "user", "content": prompt},
#         ],
#     }

#     r = requests.post(GROQ_URL, headers=headers, json=payload, timeout=60)

#     if r.status_code != 200:
#         raise RuntimeError(f"Groq API error: {r.status_code} - {r.text}")

#     raw_text = r.text
#     data = r.json()
#     content = data["choices"][0]["message"]["content"]
#     content = _strip_fences(content)

#     # Parse strict JSON
#     try:
#         out = json.loads(content)
#     except Exception:
#     # try to salvage: extract first {...} block
#         m = re.search(r"\{.*\}", content, flags=re.S)
#         if m:
#             try:
#                 out = json.loads(m.group(0))
#             except Exception:
#                 return {"answer": content, "memories": []}
#         else:
#             return {"answer": content, "memories": []}

#     answer = (out.get("answer") or "").strip()
#     memories = out.get("memories") or []

#     # sanitize memories
#     cleaned = []
#     for m in memories:
#         try:
#             text = (m.get("text") or "").strip()
#             kind = (m.get("kind") or "").strip()
#             conf = float(m.get("confidence") or 0.0)

#             if not text:
#                 continue
#             if kind not in ALLOWED_KINDS:
#                 continue
#             if conf < 0 or conf > 1:
#                 conf = max(0.0, min(1.0, conf))

#             cleaned.append({"text": text, "kind": kind, "confidence": conf})
#         except Exception:
#             continue

#     return {
#         "answer": answer or content,
#         "memories": cleaned,
#         "debug": {
#             "model": model,
#             "prompt": prompt,
#             "raw_content": content,
#             "raw_http_text": raw_text,
#             "usage": data.get("usage", {}),
#         }
#     }