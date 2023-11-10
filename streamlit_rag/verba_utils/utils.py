import logging
import pathlib
from typing import Dict, List

import streamlit as st
from verba_utils.payloads import (
    DocumentSearchQueryResponsePayload,
    SearchQueryResponsePayload,
)


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
