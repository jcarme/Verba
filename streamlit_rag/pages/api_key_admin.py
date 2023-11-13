import logging
import os
import pathlib

import streamlit as st
from verba_utils.api_client import APIClient, test_api_connection

BASE_ST_DIR = pathlib.Path(os.path.dirname(__file__)).parent

log = logging.getLogger(__name__)


st.set_page_config(
    layout="wide",
    initial_sidebar_state="expanded",
    page_title="API key admin",
    page_icon=str(BASE_ST_DIR / "assets/WL_icon.png"),
)

if not "verba_admin" in st.session_state:
    # when streamlit is started and we bypass the home page session_state["verba_admin"] is not set
    # the user has to go to main page and come back
    st.warning(
        '"verba_admin" not found in streamlit session_state. To solve this, good to Home page and reload the page.'
    )
    st.stop()
else:
    api_client = APIClient(
        verba_port=st.session_state["verba_admin"]["verba_port"],
        verba_base_url=st.session_state["verba_admin"]["verba_base_url"],
    )

is_verba_responding = test_api_connection(api_client)

title = "🤖 WL RAG Chatbot"

if not is_verba_responding["is_ok"] and not (
    "upload a key using /api/set_openai_key" in is_verba_responding["error_details"]
):  # verba api not responding
    st.title("⚙️ API key admin 🔴")
    if "upload a key using /api/set_openai_key" in is_verba_responding["error_details"]:
        pass  # normal not to have api keys at first on this page

    else:
        st.error(
            f"Connection to verba backend failed -> details : {is_verba_responding['error_details']}",
            icon="🚨",
        )
    if st.button("🔄 Try again", type="primary"):
        # when the button is clicked, the page will refresh by itself :)
        log.debug("Refresh page")

else:
    st.title("⚙️ API key admin 🟢")
    key_preview = api_client.get_openai_key_preview()
    if len(key_preview) > 0:
        st.header("Current uploaded key :")
        col0, col1, col2, col3, col4 = st.columns([0.17, 0.17, 0.32, 0.17, 0.17])
        with col0:
            if st.button("🔄 Refresh", type="primary"):
                # when the button is clicked, the page will refresh by itself :)
                log.debug("Refresh page")

        with col1:
            show = st.toggle("Show API key preview")

        with col2:
            if show:
                st.markdown(f"`{key_preview}`")
            else:
                toto = "*" * len(key_preview)
                st.markdown(f"`{toto}`")

        with col3:
            if st.button("🧪Test API key"):
                res = api_client.test_openai_api_key()
                if res["status"] == "200":
                    st.balloons()
                    st.success("✅ API key is working")
                else:
                    st.error(
                        f"API key is not working",
                        icon="🚨",
                    )
                    with st.expander("Details error : "):
                        st.write(res["status_msg"])

        with col4:
            if st.checkbox("🗑️ Delete API key"):
                if st.button("⚠️Confirm (irreversible) ⚠️", type="primary"):
                    with st.spinner("Removing your API key..."):
                        success = api_client.unset_openai_key()
                        if success:
                            st.info("Key successfully removed")
                        else:
                            st.error("Something went wrong when deleting your key")

    else:
        st.header("No Open AI API key uploaded yet")
        col0, col1, col2, col3, col4 = st.columns([0.17, 0.17, 0.32, 0.17, 0.17])
        with col0:
            if st.button("🔄 Refresh", type="primary"):
                # when the button is clicked, the page will refresh by itself :)
                log.debug("Refresh page")
    st.divider()
    st.header("Enter your new API key (it overwrites the previous one):")
    api_key = st.text_input("API Key", type="password")

    if st.button("Submit"):
        if api_key:
            with st.spinner("Uploading your secret api key..."):
                res = api_client.set_openai_key(api_key=api_key)
                if res.status == "200":
                    st.success(
                        "✅ API key saved successfully. You can refresh the list and test it!"
                    )
                else:
                    st.error(
                        f"Connection to verba backend failed -> details : {res.status_msg}",
                        icon="🚨",
                    )
        else:
            st.warning("Please enter a valid API key.")
