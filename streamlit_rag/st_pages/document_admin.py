import base64
import logging
import os
import pathlib

import streamlit as st
from verba_utils.api_client import APIClient, test_api_connection
from verba_utils.payloads import LoadPayload
from verba_utils.utils import (
    doc_id_from_filename,
    get_ordered_all_filenames,
    remove_non_utf8_characters,
)

BASE_ST_DIR = pathlib.Path(os.path.dirname(__file__)).parent

api_client = APIClient(
    verba_port=st.session_state["verba_admin"]["verba_port"],
    verba_base_url=st.session_state["verba_admin"]["verba_base_url"],
)
log = logging.getLogger(__name__)


st.set_page_config(
    layout="wide",
    initial_sidebar_state="expanded",
    page_title="WL RAG Documents",
    page_icon=str(BASE_ST_DIR / "assets/WL_icon.png"),
)

is_verba_responding = test_api_connection(api_client)
TENANT_NAME = os.environ.get("tenant_name")
title = "📕 Document administration panel"
if TENANT_NAME:
    title = f"{title} (instance for {TENANT_NAME})"

if not is_verba_responding["is_ok"]:  # verba api not responding
    st.title(f"{title} 🔴")
    st.error(
        f"Connection to verba backend failed -> details : {is_verba_responding['error_details']}",
        icon="🚨",
    )

else:  # verba api connected
    st.title(f"{title} 🟢")
    inspect_tab, insert_tab, delete_tab = st.tabs(
        [
            "Inspect uploaded documents",
            "Upload new documents",
            "Remove uploaded documents",
        ]
    )

    with inspect_tab:
        col1, col2 = st.columns([0.3, 0.7])

        with col1:  # display all found document as an ordered radio list
            if st.button("🔄 Refresh list", type="primary"):
                # when the button is clicked, the page will refresh by itself :)
                log.debug("Refresh page")

            all_documents = api_client.get_all_documents()
            if len(all_documents.documents) > 0:
                # if some documents are found display radio list
                chosen_doc = st.radio(
                    "Choose the document you want to inspect",
                    get_ordered_all_filenames(all_documents.documents),
                )
            else:
                chosen_doc = None
                st.write("No document found")

        with col2:  # display select document text content
            if chosen_doc is not None:
                document_id = doc_id_from_filename(
                    chosen_doc,
                    all_documents,
                )
                doc_info = api_client.get_document(document_id)
                st.header(chosen_doc)

                st.text_area(
                    label=f"(Document id : {document_id}, chunks count : {doc_info.document.properties.chunk_count})",
                    value=doc_info.document.properties.text,
                    height=700,
                )

    with insert_tab:
        st.header("Document uploader")
        uploaded_files = st.file_uploader(
            label="Upload your .txt or .md documents",
            type=["txt", "md"],
            accept_multiple_files=True,
        )

        if len(uploaded_files) > 0:
            document_type = st.text_input("Kind of documents", value="Documentation")
            if st.button(
                "🔨 Start embedding documents and upload to Weaviate Database",
                type="primary",
            ):
                already_uploaded_files = get_ordered_all_filenames(
                    api_client.get_all_documents().documents
                )
                loadPayload = LoadPayload(
                    reader="SimpleReader",
                    chunker="WordChunker",
                    embedder="ADAEmbedder",
                    document_type=document_type,
                    chunkUnits=100,
                    chunkOverlap=50,
                )
                for file in uploaded_files:
                    if file.name in already_uploaded_files:
                        st.warning(
                            f"`{file.name}` will not be uploaded since it is already in the database.",
                            icon="⚠️",
                        )
                        continue
                    encoded_document = base64.b64encode(file.getvalue()).decode("utf-8")
                    st.write(encoded_document)  # remove this line later
                    loadPayload.fileBytes.append(encoded_document)
                    loadPayload.fileNames.append(file.name)
                st.write(loadPayload)
                if len(loadPayload.fileNames) > 0:
                    with st.spinner(
                        "Uploading `"
                        + "` `".join([e for e in loadPayload.fileNames])
                        + "`..."
                    ):
                        response = api_client.load_data(loadPayload)
                        st.write(response)
                        if str(response.status) == "200":
                            st.info(f"✅ Documents successfully uploaded")
                            st.balloons()
                        else:
                            st.error(
                                f'Something went wrong when submitting documents {loadPayload.fileNames} http response  [{response.status}] -> "{response.status_msg}"'
                            )
                            st.info(
                                "Please try to upload our documents one by one to find out which one can't be sent (probably encoding issue)"
                            )

    with delete_tab:
        st.header("Delete documents")
        all_documents = api_client.get_all_documents()
        if not len(all_documents.documents) > 0:  # no uploaded documents
            st.write("No document uploaded yet")
        else:
            document_to_delete = st.selectbox(
                "Select the document you want to delete",
                get_ordered_all_filenames(all_documents.documents),
                index=None,
            )

            if document_to_delete:  # if user selected a document
                document_to_delete_id = doc_id_from_filename(
                    document_to_delete,
                    all_documents,
                )
                if st.button(
                    "🗑️ Delete document (irreversible)",
                    type="primary",
                ):
                    with st.spinner("Sending delete request..."):
                        is_document_deleted = api_client.delete_document(
                            document_to_delete_id
                        )
                        if is_document_deleted:  # delete ok
                            st.balloons()
                            st.info(f"✅ {document_to_delete} successfully deleted")
                        else:  # delete failed
                            st.warning(
                                f"🚨 Something went wrong when trying to delete {document_to_delete}"
                            )
