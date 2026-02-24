import uuid

IMPORTANT_TRIGGERS = [
    "i am", "i'm", "my goal", "i want", "i prefer", "i hate", "i love",
    "my weakness", "my strength", "i struggle", "i am preparing", "target"
]

def should_store_memory(text: str) -> tuple[bool, str]:
    t = text.lower().strip()
    if any(k in t for k in IMPORTANT_TRIGGERS):
        # kind guess
        if "prefer" in t or "love" in t or "hate" in t:
            return True, "preference"
        if "goal" in t or "want" in t or "preparing" in t or "target" in t:
            return True, "goal"
        return True, "fact"
    return False, "fact"

def make_memory(text: str, kind: str, source: str, confidence: float = 1.0) -> dict:
    return {
        "memory_id": str(uuid.uuid4()),
        "text": text.strip(),
        "kind": kind,
        "confidence": confidence,
        "source": source
    }