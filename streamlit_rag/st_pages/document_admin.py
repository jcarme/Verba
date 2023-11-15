import base64
import logging
import os
import pathlib

import streamlit as st
from verba_utils.api_client import APIClient, test_api_connection
from verba_utils.payloads import LoadPayload
from verba_utils.utils import doc_id_from_filename, get_ordered_all_filenames

BASE_ST_DIR = pathlib.Path(os.path.dirname(__file__)).parent

log = logging.getLogger(__name__)


st.set_page_config(
    layout="wide",
    initial_sidebar_state="expanded",
    page_title="WL RAG Documents",
    page_icon=str(BASE_ST_DIR / "assets/WL_icon.png"),
)


st.sidebar.header("Config")
chuck_size = st.sidebar.slider(
    "Select chunk size",
    min_value=50,
    max_value=1000,
    value=100,
    step=50,
)

chunk_overlap = st.sidebar.slider(
    "Select chunk overlap",
    min_value=10,
    max_value=500,
    value=50,
    step=10,
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


if not is_verba_responding["is_ok"]:  # verba api not responding
    st.title("📕 Document administration panel🔴")
    if "upload a key using /api/set_openai_key" in is_verba_responding["error_details"]:
        st.error(
            f"Your openapi key is not set yet. Go set it in **API Key administration** page",
            icon="🚨",
        )

    else:
        st.error(
            f"Connection to verba backend failed -> details : {is_verba_responding['error_details']}",
            icon="🚨",
        )
    if st.button("🔄 Try again", type="primary"):
        # when the button is clicked, the page will refresh by itself :)
        log.debug("Refresh page")

else:
    test_open_ai_token = api_client.test_openai_api_key()
    if test_open_ai_token["status"] != "200":  # token set but not working
        st.title("📕 Document administration panel 🔴")
        st.error(
            f"OpenAI API token set but is not working. Go fix it in **API Key administration** page",
            icon="🚨",
        )


if (
    is_verba_responding["is_ok"] and test_open_ai_token["status"] == "200"
):  # verba api connected and token is working
    st.title("📕 Document administration panel 🟢")

    # define 3 document sections
    inspect_tab, insert_tab, delete_tab = st.tabs(
        [
            "Inspect uploaded documents",
            "Upload new documents",
            "Remove uploaded documents",
        ]
    )

    with inspect_tab:
        doc_list, doc_preview = st.columns([0.3, 0.7])

        with doc_list:  # display all found document as an ordered radio list
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

        with doc_preview:  # display select document text content
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
                    chunkUnits=chuck_size,
                    chunkOverlap=chunk_overlap,
                )
                for file in uploaded_files:
                    if file.name in already_uploaded_files:
                        st.warning(
                            f"`{file.name}` will not be uploaded since it is already in the database.",
                            icon="⚠️",
                        )
                        continue
                    encoded_document = base64.b64encode(file.getvalue()).decode("utf-8")
                    loadPayload.fileBytes.append(encoded_document)
                    loadPayload.fileNames.append(file.name)
                if len(loadPayload.fileNames) > 0:
                    with st.spinner(
                        "Uploading `"
                        + "` `".join([e for e in loadPayload.fileNames])
                        + "`. Please wait. Expect about 1 second per KB of text."
                    ):
                        response = api_client.load_data(loadPayload)
                        if str(response.status) == "200":
                            st.info(f"✅ Documents successfully uploaded")
                            st.balloons()
                        else:
                            st.error(
                                f'Something went wrong when submitting documents {loadPayload.fileNames} http response  [{response.status}] -> "{response.status_msg}"'
                            )
                            st.info(
                                "Please check the error message above. If it is an Error 429 it means that the API is overloaded. Please try again later. If it is an encoding related error you might try to upload files one by one to check which one is causing the error."
                            )
                            st.title("Debug info :")
                            st.write("Sent POST payload :")
                            st.write(loadPayload)
                            st.write("Received response :")
                            st.write(response)

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
