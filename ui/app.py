import streamlit as st
import requests

API = "http://localhost:8000"

st.set_page_config(page_title="GraphMind Dev Tool", layout="wide")
st.title("GraphMind — Interview Prep Memory Engine (Dev Tool)")

if "session_token" not in st.session_state:
    st.session_state.session_token = None
    st.session_state.user_id = None

col1, col2 = st.columns(2)

with col1:
    st.subheader("Auth")
    tab1, tab2 = st.tabs(["Signup", "Login"])

    with tab1:
        su_user = st.text_input("Username (signup)", key="su_user")
        su_pass = st.text_input("Password (signup)", type="password", key="su_pass")
        if st.button("Create account"):
            r = requests.post(f"{API}/auth/signup", json={"username": su_user, "password": su_pass})
            st.write("API: POST /auth/signup")
            st.json(r.json())

    with tab2:
        li_user = st.text_input("Username (login)", key="li_user")
        li_pass = st.text_input("Password (login)", type="password", key="li_pass")
        if st.button("Login"):
            r = requests.post(f"{API}/auth/login", json={"username": li_user, "password": li_pass})
            st.write("API: POST /auth/login")
            data = r.json()
            st.json(data)
            if "session_token" in data:
                st.session_state.session_token = data["session_token"]
                st.session_state.user_id = data["user_id"]

with col2:
    st.subheader("Session")
    st.write("Logged in user_id:", st.session_state.user_id)
    st.write("session_token:", st.session_state.session_token)

st.divider()
st.subheader("Chat")

msg = st.text_area("Message", height=120, placeholder="Tell me what role you’re preparing for, your weaknesses, goals, etc.")

if st.button("Send to /chat"):
    if not st.session_state.session_token:
        st.error("Login first.")
    else:
        r = requests.post(f"{API}/chat", json={"session_token": st.session_state.session_token, "message": msg})
        st.write("API: POST /chat")
        data = r.json()

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