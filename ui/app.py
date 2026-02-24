import streamlit as st
import requests

API = "http://localhost:8000"

# ---- persistent session state ----
if "session_token" not in st.session_state:
    st.session_state["session_token"] = None
if "user_id" not in st.session_state:
    st.session_state["user_id"] = None
if "chat_log" not in st.session_state:
    st.session_state["chat_log"] = []
if "msg" not in st.session_state:
    st.session_state["msg"] = ""

st.set_page_config(page_title="GraphMind Dev Tool", layout="wide")
st.title("GraphMind — Interview Prep Memory Engine (Dev Tool)")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Auth")
    tab1, tab2 = st.tabs(["Signup", "Login"])

    with tab1:
        su_user = st.text_input("Username (signup)", key="su_user")
        su_pass = st.text_input("Password (signup)", type="password", key="su_pass")
        if st.button("Create account", key="signup_btn"):
            r = requests.post(f"{API}/auth/signup", json={"username": su_user, "password": su_pass})
            st.write("API: POST /auth/signup")
            try:
                st.json(r.json())
            except Exception:
                st.code(r.text)

    with tab2:
        li_user = st.text_input("Username (login)", key="li_user")
        li_pass = st.text_input("Password (login)", type="password", key="li_pass")
        if st.button("Login", key="login_btn"):
            r = requests.post(f"{API}/auth/login", json={"username": li_user, "password": li_pass})
            st.write("API: POST /auth/login")

            try:
                data = r.json()
            except Exception:
                st.code(r.text)
                st.stop()

            st.json(data)

            # only set session if login succeeded
            if r.status_code == 200 and "session_token" in data:
                st.session_state["session_token"] = data["session_token"]
                st.session_state["user_id"] = data["user_id"]
                st.success("Logged in!")
            else:
                st.error("Login failed.")

with col2:
    st.subheader("Session")
    st.write("Logged in user_id:", st.session_state["user_id"])
    st.write("session_token:", st.session_state["session_token"])

st.divider()
st.subheader("Chat")

# tie textarea to session_state so it survives reruns
st.text_area(
    "Message",
    height=120,
    placeholder="Tell me what role you’re preparing for, your weaknesses, goals, etc.",
    key="msg",
)

if st.button("Send to /chat", key="chat_btn"):
    if not st.session_state["session_token"]:
        st.error("Login first.")
    else:
        payload = {"session_token": st.session_state["session_token"], "message": st.session_state["msg"]}
        r = requests.post(f"{API}/chat", json=payload)
        st.write("API: POST /chat")

        try:
            data = r.json()
        except Exception:
            st.error("Backend did not return JSON")
            st.code(r.text)
            st.stop()

        # store chat history locally (dev-tool feel)
        st.session_state["chat_log"].append(
            {"user": st.session_state["msg"], "answer": data.get("answer", ""), "raw": data}
        )

        left, right = st.columns(2)
        with left:
            st.markdown("### Answer")
            st.write(data.get("answer", ""))

            st.markdown("### Timings")
            st.write("retrieval_time_ms:", data.get("retrieval_time_ms"))
            st.write("llm_time_ms:", data.get("llm_time_ms"))

        with right:
            st.markdown("### Memory citations")
            st.json(data.get("memory_citations", []))

            st.markdown("### Backend debug trace")
            st.json(data.get("debug_trace", []))

st.divider()
st.subheader("Chat log (this UI session)")
for i, turn in enumerate(st.session_state["chat_log"][-5:], start=1):
    st.markdown(f"**{i}. You:** {turn['user']}")
    st.markdown(f"**Assistant:** {turn['answer']}")