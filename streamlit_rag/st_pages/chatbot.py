import logging
import os
import pathlib
from typing import List, Tuple

import streamlit as st
from streamlit_option_menu import option_menu
from verba_utils.api_client import APIClient, test_api_connection
from verba_utils.payloads import QueryResponsePayload
from verba_utils.utils import (
    append_documents_in_session_manager,
    get_prompt_history,
    get_retrieved_documents_from_prompt,
    remove_non_utf8_characters,
)


def generate_answer(
    prompt: str,
    api_client: APIClient,
    min_nb_words: int = None,
    max_nb_words: int = None,
    return_documents: bool = False,
) -> str | Tuple[str, List]:
    """
    Generate answers to a list of questions. Uses the previously defined query_verba
    :param prompt: str
    :param api_client: APIClient
    :param min_nb_words: int
    :param max_nb_words: int
    :param return_documents: bool default False. If true returns (text_response, documents_list)
    :returns: str | Tuple(str, List)
    """
    # from verba_utils.constants import QUERY_RANDOM_RESPONSE

    # if return_documents:
    #     return QUERY_RANDOM_RESPONSE.system, QUERY_RANDOM_RESPONSE.documents
    # else:
    #     return QUERY_RANDOM_RESPONSE.system

    if max_nb_words is None and min_nb_words is not None:
        max_nb_words = min_nb_words * 2
    if min_nb_words is None and max_nb_words is not None:
        min_nb_words = max_nb_words // 2

    if min_nb_words is not None:  # so max_nb_words is not None either
        question_appendix = f" Please provide an elaborated answer in {min_nb_words} to {max_nb_words} words."
    else:
        question_appendix = ""

    elaborated_question = remove_non_utf8_characters(
        input_str=str(prompt) + str(question_appendix)
    )
    log.info(f"Cleaned user query : {elaborated_question}")

    if test_api_connection(api_client):
        response = api_client.query(elaborated_question)
    else:
        log.error(
            f"Verba API not available {api_client.build_url(api_client.api_routes.health)}, query not submitted"
        )
        response = QueryResponsePayload(system="Verba API not available")

    if return_documents:
        return response.system, response.documents
    else:
        return response.system


BASE_ST_DIR = pathlib.Path(os.path.dirname(__file__)).parent
log = logging.getLogger(__name__)


st.set_page_config(
    initial_sidebar_state="expanded",
    layout="centered",
    page_title="WL RAG Chatbot",
    page_icon=str(BASE_ST_DIR / "assets/WL_icon.png"),
)
st.sidebar.header("Config")
max_worlds_answers = st.sidebar.slider(
    "Select maximum words in answer:", min_value=40, max_value=500, value=100, step=20
)

if not "verba_admin" in st.session_state:
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

if not is_verba_responding["is_ok"]:  # verba api not responding
    st.title(f"{title} 🔴")
    st.error(
        f"Connection to verba backend failed -> details : {is_verba_responding['error_details']}",
        icon="🚨",
    )
    if st.button("🔄 Try again", type="primary"):
        # when the button is clicked, the page will refresh by itself :)
        log.debug("Refresh page")
else:  # verba api connected
    st.title(f"{title} 🟢")

    selected_panel = option_menu(
        None,
        ["Chatbot", "Retrieved documents"],
        icons=["chat bot", "folder"],
        menu_icon=None,
        default_index=0,
        orientation="horizontal",
    )

    if selected_panel == "Chatbot":  # Display chatbot
        if st.button("Reset conversation", type="primary"):
            # Delete message and document items in session state
            if "messages" in st.session_state:
                del st.session_state["messages"]
            if "retrieved_documents" in st.session_state:
                del st.session_state["retrieved_documents"]

        if "messages" not in st.session_state.keys():
            st.session_state.messages = [
                {"role": "assistant", "content": "Hello 👋 How may I help you?"}
            ]

        # Display chat messages
        for message in st.session_state.messages:
            with st.chat_message(
                message["role"],
                avatar=str(BASE_ST_DIR / "assets/WL.png")
                if message["role"] == "assistant"
                else None,
            ):
                st.markdown(message["content"])

        # User-provided prompt
        if prompt := st.chat_input():
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

        # Generate a new response if last message is not from assistant
        if st.session_state.messages[-1]["role"] != "assistant":
            with st.chat_message(
                "assistant", avatar=str(BASE_ST_DIR / "assets/WL.png")
            ):
                with st.spinner("Thinking..."):
                    log.debug(f"User prompt : {prompt}")
                    if prompt is not None:
                        response, documents = generate_answer(
                            prompt,
                            api_client,
                            max_nb_words=max_worlds_answers,
                            return_documents=True,
                        )
                        st.markdown(response)
                        append_documents_in_session_manager(prompt, documents)
                    message = {"role": "assistant", "content": response}
                    st.session_state.messages.append(message)
    else:  # Display retrieved documents
        if not "retrieved_documents" in st.session_state:
            st.header("Here you will find documents retrieved for your last prompt.")
        else:
            st.header("Retrieved documents sent to the Chatbot:")
            chosen_prompt = st.selectbox(
                "Select the prompt for which you want to see the retrieved documents",
                get_prompt_history(),
                index=0,
            )
            retrieved_documents = get_retrieved_documents_from_prompt(chosen_prompt)
            st.divider()
            for document in retrieved_documents:
                st.text_area(
                    label=f"Document : {document.get('doc_name')} (chunk {document.get('chunk_id')}), retrieval score {document.get('_additional').get('score')}) ",
                    value=f"{document.get('text')}",
                    height=210,
                )
