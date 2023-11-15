import logging
import pathlib
from typing import Dict, List, Tuple

import streamlit as st
from verba_utils.api_client import APIClient, test_api_connection
from verba_utils.payloads import (
    DocumentSearchQueryResponsePayload,
    QueryResponsePayload,
    SearchQueryResponsePayload,
)

log = logging.getLogger(__name__)


def setup_logging(
    logging_level=logging.INFO,
    log_format: str = "[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s",
):
    """
    Simple function to set up proper python logging
    :param logging_level: Value in [logging.ERROR, logging.WARNING, logging.INFO, logging.DEBUG]
    :param log_format: str by default -> "[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s"
    :return: nothing
    """
    logging.basicConfig(level=logging_level, format=log_format)


def write_centered_text(text: str):
    st.markdown(
        f"""<div style=\"text-align: justify;\">{text}</div>""",
        unsafe_allow_html=True,
    )
    st.write("\n")


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


def display_centered_image(
    image,
    caption=None,
    width=None,
    use_column_width=None,
    clamp=False,
    channels="RGB",
    output_format="auto",
):
    if isinstance(image, pathlib.PosixPath):
        image = str(image)
    # trick to center the image (make 3 columns and display the image in the middle column which is big)
    with st.columns([0.1, 0.98, 0.1])[1]:
        st.image(
            image,
            caption=caption,
            width=width,
            use_column_width=use_column_width,
            clamp=clamp,
            channels=channels,
            output_format=output_format,
        )


def remove_non_utf8_characters(input_str, encoding="latin-1"):
    """
    This is mainly for question number 19 that has '“' in the body.
    Verba API can't handle this character and returns an error.
    """
    try:
        # Try to encode the string to the specified encoding with error='strict'
        cleaned_str = input_str.encode(encoding, "strict")
        return cleaned_str
    except UnicodeEncodeError:
        # If encoding fails, use 'replace' to replace invalid characters with a placeholder
        cleaned_str = input_str.encode(encoding, "replace").decode(encoding)
        return cleaned_str


def append_documents_in_session_manager(prompt: str, documents: List[Dict]):
    """Append retrieved document in streamlit session_manager
    :param str prompt:
    :param List[Dict] documents:
    """
    if not "retrieved_documents" in st.session_state:
        # init empty list
        st.session_state["retrieved_documents"] = []

    st.session_state["retrieved_documents"].append(
        {"prompt": prompt, "documents": documents}
    )


def get_prompt_history() -> List[str]:
    """Get a list of sent prompts (last one being on top)

    :return List[str]:
    """
    if not "retrieved_documents" in st.session_state:
        return []
    else:
        return [e["prompt"] for e in reversed(st.session_state["retrieved_documents"])]


def get_retrieved_documents_from_prompt(prompt: str) -> List[Dict]:
    """Get the documents retrieved to generate answer to the given prompt
    :param str prompt:
    :return List[Dict]:
    """
    for e in reversed(st.session_state["retrieved_documents"]):
        if e["prompt"] == prompt:
            return e["documents"]
    return []


def doc_id_from_filename(
    filename: str, search_query_response: SearchQueryResponsePayload
) -> str | None:
    """Returns doc id from a given filename (that must be in the provided search_query_response)
    :param str filename:
    :param SearchQueryResponsePayload search_query_response:
    :return str | None: doc id if document found else None
    """
    for e in dict(search_query_response).get("documents", []):
        if e.doc_name == filename:
            return e.additional.id
    return None


def get_ordered_all_filenames(
    documents: List[DocumentSearchQueryResponsePayload],
) -> List[str]:
    """Get all filenames from a SearchQueryResponsePayload alphabetically sorted
    :param SearchQueryResponsePayload search_query_response:
    :return List[str]:
    """
    return sorted([e.doc_name for e in documents])
