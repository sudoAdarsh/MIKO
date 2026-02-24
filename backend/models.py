from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class SignupReq(BaseModel):
    username: str
    password: str

class LoginReq(BaseModel):
    username: str
    password: str

class ChatReq(BaseModel):
    session_token: str
    message: str

class MemoryCitation(BaseModel):
    memory_id: str
    snippet: str
    score: float

class ChatResp(BaseModel):
    answer: str
    retrieval_time_ms: int
    llm_time_ms: int
    memory_citations: List[MemoryCitation]
    debug_trace: List[Dict[str, Any]]