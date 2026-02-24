from fastapi import FastAPI, HTTPException
from .models import SignupReq, LoginReq, ChatReq, ChatResp, MemoryCitation
from .auth import init_auth_db, create_user, verify_user, new_session, user_from_session
from .neo4j_client import Neo4jClient
from .memory import should_store_memory, make_memory
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

    memories = []
    with timed("retrieve_memories", trace):
        memories = neo.get_memories(user_id, limit=12)

    # build context pack (ONLY this user's memories)
    context_lines = [f"- ({m['kind']}) {m['text']} [id={m['memory_id']}]" for m in memories]
    prompt = f"""
You are an interview prep assistant. Use ONLY the provided user memory context.
If context is insufficient, ask a clarifying question.

User memory context:
{chr(10).join(context_lines)}

User message:
{req.message}
""".strip()

    with timed("llm_call_gemini", trace):
        answer = gemini_answer(GEMINI_API_KEY, prompt)

    with timed("maybe_store_memory", trace):
        ok, kind = should_store_memory(req.message)
        if ok:
            neo.add_memory(user_id, make_memory(req.message, kind=kind, source="chat"))

    # citations = memories used (for now, just return top few retrieved)
    citations = []
    for i, m in enumerate(memories[:5]):
        citations.append(MemoryCitation(
            memory_id=m["memory_id"],
            snippet=m["text"][:80],
            score=1.0 - (i * 0.05)
        ))

    # read timings from trace
    retrieval_ms = next((x["ms"] for x in trace if x["stage"] == "retrieve_memories" and x["status"] == "ok"), 0)
    llm_ms = next((x["ms"] for x in trace if x["stage"] == "llm_call_gemini" and x["status"] == "ok"), 0)

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