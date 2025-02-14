import streamlit as st

st.set_page_config(page_title="AgentManager Chat", layout="wide")
import yaml
from yaml.loader import SafeLoader
import streamlit_authenticator as stauth
from streamlit_authenticator import LoginError
import json
from langchain_community.callbacks.streamlit import StreamlitCallbackHandler
from search import AgentManager
import os

try:
    config = st.secrets.to_dict()
except Exception as e:
    st.error(f"Error loading config file: {e}")
    st.stop()

authenticator = stauth.Authenticate(
    credentials=config["credentials"],
    cookie_name=config["cookie"]["name"],
    key=config["cookie"]["key"],
    cookie_expiry_days=config["cookie"]["expiry_days"],
)

try:
    authenticator.login(location="sidebar", key="login-demo-app-home")
except LoginError as e:
    st.error(e)

if st.session_state.get("authentication_status"):
    authenticator.logout(location="sidebar", key="logout-demo-app-home")
elif st.session_state.get("authentication_status") is False:
    st.error("Username/password is incorrect")
elif st.session_state.get("authentication_status") is None:
    st.warning("Please enter your username and password")

if st.session_state.get("authentication_status"):

    def format_summary(response_data):
        if isinstance(response_data, dict):
            summary = response_data.get("output", "Summary not found.")
        elif isinstance(response_data, str):
            try:
                parsed_json = json.loads(response_data)
                summary = parsed_json.get("output", "Summary not found.")
            except json.JSONDecodeError:
                return response_data
        else:
            return str(response_data)
        return f"### 📌 Summary\n\n{summary}"


    def main():
        st.title("Deep-Search-Wiser")
        if "agent_manager" not in st.session_state:
            st.session_state.agent_manager = AgentManager()
        if "chats" not in st.session_state:
            if os.path.exists("chat_history.json"):
                try:
                    with open("chat_history.json", "r") as f:
                        st.session_state.chats = json.load(f)
                    if not isinstance(st.session_state.chats, list):
                        st.session_state.chats = []
                except Exception:
                    st.session_state.chats = []
            else:
                st.session_state.chats = []

        with st.sidebar:
            st.header("💬 Chat History")

            search_query = st.text_input("Search Chats", key="chat_search")

            for i, chat in enumerate(st.session_state.chats):
                if search_query and search_query.lower() not in chat["prompt"].lower():
                    continue

                cols = st.columns([3, 1])
                with cols[0]:
                    display_text = chat["prompt"] if len(chat["prompt"]) <= 20 else chat["prompt"][:20] + "..."
                    if st.button(display_text, key=f"chat_{i}"):
                        st.session_state.current_chat = chat
                with cols[1]:
                    if st.button("🗑️", key=f"delete_{i}"):
                        st.session_state.chats.pop(i)
                        with open("chat_history.json", "w") as f:
                            json.dump(st.session_state.chats, f)
                        if st.session_state.get("current_chat") == chat:
                            st.session_state.current_chat = None
                        # st.rerun()

            if st.button("New Chat", key="new_chat"):
                st.session_state.current_chat = None

        if st.session_state.get("current_chat"):
            chat = st.session_state.current_chat
            st.chat_message("user").write(chat["prompt"])
            st.chat_message("assistant").markdown(format_summary(chat["response"]), unsafe_allow_html=True)

        user_input = st.chat_input("Type something...")
        if user_input:
            st.session_state.current_chat = None
            st.chat_message("user").write(user_input)
            with st.chat_message("assistant"):
                st_callback = StreamlitCallbackHandler(st.container())
                response_text = st.session_state.agent_manager.execute(
                    user_prompt=user_input, st_callback=st_callback
                )
                st.markdown(format_summary(response_text), unsafe_allow_html=True)
            st.session_state.chats.append({"prompt": user_input, "response": response_text})
            with open("chat_history.json", "w") as f:
                json.dump(st.session_state.chats, f)


    main()
