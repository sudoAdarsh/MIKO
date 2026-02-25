from fastapi import FastAPI, HTTPException
from .models import SignupReq, LoginReq, ChatReq, ChatResp, MemoryCitation
from .auth import init_auth_db, create_user, verify_user, new_session, user_from_session
from .neo4j_client import Neo4jClient
from .memory import make_memory
from .llm_groq import groq_answer_and_memories
from .config import GROQ_API_KEY, GROQ_MODEL
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
    trace.append({
        "stage": "auth_scope",
        "status": "ok",
        "user_id": user_id,
        "session_token_prefix": req.session_token[:8]
    })
    if not user_id:
        raise HTTPException(status_code=401, detail="invalid session")

    # 1) Retrieve memories
    with timed("retrieve_memories", trace):
        memories = neo.get_memories(user_id, limit=12)

    # 2) Build prompt with strict JSON contract
    context_lines = [f"- ({m['kind']}) {m['text']} [id={m['memory_id']}]" for m in memories]

    prompt = f"""
Return STRICT JSON only (no markdown, no extra text) with this shape:
{{
  "answer": "string",
  "memories": [
    {{"text": "string", "kind": "fact|goal|preference|weakness|strength|constraint", "confidence": 0.0}}
  ]
}}

Answer rules:
- Give a helpful, complete answer (normally 10-15 lines) around 150–250 words.
- Use bullets/steps when useful.
- If the user asks something vague, ask 1 clarifying question at the end.

Memory rules:
- Extract ONLY durable user-specific info worth saving for future personalization.
- Max 5 items.
- confidence in [0,1]. Use >=0.75 only when clearly stated by user.
- Do NOT store generic questions like "explain normalization", keep it user oriented.
- If no durable info, return empty memories: [].

User memory context:
{chr(10).join(context_lines)}

User message:
{req.message}
""".strip()


    # 3) One Groq call: answer + extracted memories
    with timed("llm_call_groq", trace):
        result = groq_answer_and_memories(GROQ_API_KEY, GROQ_MODEL, prompt)

    answer = result.get("answer", "")
    extracted = result.get("memories", [])

    dbg = result.get("debug", {})
    trace.append({
        "stage": "groq_io",
        "status": "ok",
        "model": dbg.get("model"),
        "usage": dbg.get("usage"),
        "http_preview_len": len(dbg.get("raw_http_text", "") or ""),
        "prompt_preview": (dbg.get("prompt","")[:1200]),  # avoid huge UI spam
        "raw_preview": (dbg.get("raw_content","")[:1200]),
    })

    # 4) Store extracted memories (threshold)
    MEMORY_CONF_THRESHOLD = 0.75

    with timed("store_memories", trace):
        stored = []
        for m in extracted:
            text = (m.get("text") or "").strip()
            kind = (m.get("kind") or "").strip()
            conf = float(m.get("confidence") or 0.0)

            if not text or conf < MEMORY_CONF_THRESHOLD:
                continue

            neo.add_memory(user_id, make_memory(text, kind=kind, source="chat", confidence=conf))
            stored.append({"text": text, "kind": kind, "confidence": conf})

    trace.append({"stage": "stored_memories", "status": "ok", "count": len(stored), "items": stored[:5]})

    # 5) citations = retrieved memories (top few)
    citations = []
    for i, m in enumerate(memories[:5]):
        citations.append(MemoryCitation(
            memory_id=m["memory_id"],
            snippet=m["text"][:80],
            score=1.0 - (i * 0.05)
        ))

    # timings
    def last_ms(stage: str) -> int:
        ms = 0
        for x in trace:
            if x.get("stage") == stage and x.get("status") == "ok":
                ms = int(x.get("ms", 0))
        return ms

    retrieval_ms = last_ms("retrieve_memories")
    llm_ms = last_ms("llm_call_groq")

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