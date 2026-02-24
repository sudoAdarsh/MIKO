from fastapi import FastAPI, HTTPException
from .models import SignupReq, LoginReq, ChatReq, ChatResp, MemoryCitation
from .auth import init_auth_db, create_user, verify_user, new_session, user_from_session
from .neo4j_client import Neo4jClient
from .memory import make_memory
from .llm_gemini import gemini_answer
from .config import GEMINI_API_KEY
from .utils import timed

app = FastAPI()
neo = Neo4jClient()

@app.on_event("startup")
def startup():
    init_auth_db()
    neo.init_schema()

@app.on_event("shutdown")
def shutdown():
    neo.close()

@app.post("/auth/signup")
def signup(req: SignupReq):
    try:
        user_id = create_user(req.username, req.password)
    except Exception:
        raise HTTPException(status_code=400, detail="username already exists or invalid")
    neo.ensure_user_node(user_id, req.username)

    # seed interview prep onboarding memories (baseline)
    seed = [
        f"Interview prep mode: enabled",
        f"Username: {req.username}"
    ]
    for s in seed:
        neo.add_memory(user_id, make_memory(s, kind="fact", source="system"))

    return {"user_id": user_id}

@app.post("/auth/login")
def login(req: LoginReq):
    user_id = verify_user(req.username, req.password)
    if not user_id:
        raise HTTPException(status_code=401, detail="invalid credentials")
    token = new_session(user_id)
    return {"session_token": token, "user_id": user_id}

@app.post("/chat", response_model=ChatResp)
def chat(req: ChatReq):
    trace = []
    user_id = user_from_session(req.session_token)
    if not user_id:
        raise HTTPException(status_code=401, detail="invalid session")

    # 1) Retrieve memories FIRST
    with timed("retrieve_memories", trace):
        memories = neo.get_memories(user_id, limit=12)

    # 2) Build prompt from retrieved memories
    context_lines = [f"- ({m['kind']}) {m['text']} [id={m['memory_id']}]" for m in memories]
    prompt = f"""
You are an interview prep assistant. Use ONLY the provided user memory context.
If context is insufficient, still answer normally using general knowledge, and ask 1 clarifying question if needed.

User memory context:
{chr(10).join(context_lines)}

User message:
{req.message}
""".strip()

    # 3) Call Gemini once
    with timed("llm_call_gemini", trace):
        try:
            answer = gemini_answer(GEMINI_API_KEY, prompt)
        except Exception as e:
            answer = f"[LLM ERROR] {str(e)}"

    # 4) Extract "important memories" (Gemini)
    from .llm_gemini import gemini_extract_memories

    MEMORY_CONF_THRESHOLD = 0.75
    ALLOWED_KINDS = {"fact", "goal", "preference", "weakness", "strength", "constraint"}

    with timed("extract_memories_llm", trace):
        extracted = []
        try:
            extracted = gemini_extract_memories(GEMINI_API_KEY, req.message)
        except Exception as e:
            trace.append({"stage": "extract_memories_llm", "status": "error", "error": str(e)})

    # 5) Store extracted memories
    with timed("store_memories", trace):
        stored = []
        for m in extracted:
            try:
                text = (m.get("text") or "").strip()
                kind = (m.get("kind") or "").strip()
                conf = float(m.get("confidence") or 0.0)

                if not text or kind not in ALLOWED_KINDS or conf < MEMORY_CONF_THRESHOLD:
                    continue

                neo.add_memory(user_id, make_memory(text, kind=kind, source="chat", confidence=conf))
                stored.append({"text": text, "kind": kind, "confidence": conf})
            except Exception as e:
                trace.append({"stage": "store_memories", "status": "error", "error": str(e), "item": m})

    trace.append({"stage": "stored_memories", "status": "ok", "count": len(stored), "items": stored[:5]})

    # 6) Citations = retrieved memories (top few)
    citations = []
    for i, m in enumerate(memories[:5]):
        citations.append(MemoryCitation(
            memory_id=m["memory_id"],
            snippet=m["text"][:80],
            score=1.0 - (i * 0.05)
        ))

    # 7) timings
    def last_ms(stage: str) -> int:
        ms = 0
        for x in trace:
            if x.get("stage") == stage and x.get("status") == "ok":
                ms = int(x.get("ms", 0))
        return ms

    retrieval_ms = last_ms("retrieve_memories")
    llm_ms = last_ms("llm_call_gemini")

    return ChatResp(
        answer=answer,
        retrieval_time_ms=retrieval_ms,
        llm_time_ms=llm_ms,
        memory_citations=citations,
        debug_trace=trace
    )

@app.get("/health")
def health():
    return {"ok": True}