import os
import pathlib

import click
import streamlit as st
from st_pages import Page, show_pages
from verba_utils.utils import display_centered_image, setup_logging, write_centered_text

BASE_ST_DIR = pathlib.Path(os.path.dirname(__file__))


@click.command()
@click.option(
    "--verba_port",
    "-vp",
    type=str,
    help="Verba backend api port, usually in our case 8000 + tenant number ",
)
@click.option(
    "--verba_base_url",
    type=str,
    help="Verba base api url usually in our case http://localhost)",
)
def main(verba_port, verba_base_url):
    if not (verba_port and verba_base_url):
        st.error(
            f"""
            Streamlit app not properly started, make sure to provide the following cli arguments 
            `verba_port` (current value : {verba_port}) and 
            `verba_base_url` (current value :  {verba_base_url}). 
            Hint : you may need to look at https://docs.streamlit.io/library/get-started/main-concepts
            """
        )

    # write verba connection settings to session_state for other pages
    st.session_state["verba_admin"] = {
        "verba_port": verba_port,
        "verba_base_url": verba_base_url,
    }

    st.header("LLM and RAG in a nutshell", divider="grey")

    write_centered_text(
        """
1 - \"Large Language Model\" refers to a highly advanced AI program capable of comprehending and producing human-like text.
        """
    )

    write_centered_text(
        """
2 - \"Retrieval-Augmented\" component extends the LLM's abilities by allowing it to search and extract information from extensive databases. RAG models are better at avoiding hallucinations because they can fact-check their responses using external knowledge. This prevents them from making up information or providing inaccurate answers. 
        """
    )
    write_centered_text(
        """
In essence, the integration of RAG with LLM enhances the LLM's information retrieval and synthesis prowess, resulting in a sophisticated AI system that not only comprehends and communicates in human language but also leverages a vast reservoir of knowledge to provide enriched and contextually relevant responses. It's akin to an erudite digital assistant with access to an expansive library, capable of delivering insightful and well-informed explanations.
        """
    )

    display_centered_image(
        BASE_ST_DIR / "assets/rag.png", caption="Retrieval Augmented Generation"
    )

    st.header("Data privacy", divider="grey")
    write_centered_text(
        """
We want to assure you that your privacy and data security are of utmost importance to us. When using Chat GPT 4, hosted on our private Worldline instance on Azure, you can be confident that your interactions and data are kept secure and not exposed to third parties.
        """
    )
    write_centered_text(
        """
Our private Worldline instance does not send chat prompts to the OpenAI API. This means that your conversations, questions, or interactions with the model are not shared with external servers or third parties. Everything remains within the controlled environment of our private instance.
    """
    )
    write_centered_text(
        """
Additionally, we take measures to safeguard the privacy of any documents you may upload while using the application. Your uploaded documents are not shared between different instances of the application. Each user's data and documents are kept separate and are not accessible or viewable by other instances.
This ensures that your information remains confidential.
        """
    )

    st.header("Chat with LLM", divider="grey")

    st.write("This is what the chatbot should look like:")

    display_centered_image(
        BASE_ST_DIR / "assets/chatbot.png", caption="Chatbot snapshot"
    )

    write_centered_text(
        'Once you ask a question, you can go to the "Retrieved documents" tab, where you will find every chunk of document retrieved and sent to the LLM to generate your answer.'
    )

    write_centered_text(
        "Beware, unlike OpenAI ChatGPT instance (that you may have already played with), once you asked a question, the chat bot have no prior knowledge of your previous prompt. We encourage you to make detailed prompts to get more accurate answers."
    )

    st.header("Document administration", divider="grey")

    write_centered_text(
        'Currently only .txt files are supported. You can consult, upload or delete your uploaded documents from the "Document administration" section.'
    )


if __name__ == "__main__":
    setup_logging()

    st.set_page_config(
        page_title="WL RAG Home",
        page_icon=str(BASE_ST_DIR / "assets/WL_icon.png"),
        layout="centered",
        initial_sidebar_state="expanded",
    )
    show_pages(
        [
            Page(BASE_ST_DIR / "app.py", "Home"),
            Page(BASE_ST_DIR / "st_pages/chatbot.py", "RAG Chatbot"),
            Page(
                BASE_ST_DIR / "st_pages/document_admin.py",
                "Document administration",
            ),
            Page(BASE_ST_DIR / "st_pages/api_key_admin.py", "API key administration"),
        ]
    )
    display_centered_image(str(BASE_ST_DIR / "assets/WL-Horizontal.png"))
    st.title("Worldline Retrieval-Augmented Generation")
    main()
