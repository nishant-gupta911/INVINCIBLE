"""
Streamlit interface for the INVINCIBLE student RAG application. It handles
file uploads, persistent chat sessions, answer generation, source display,
feedback capture, and document management on top of InvincibleRAG.

Key classes/methods:
- get_rag(): cached InvincibleRAG loader
- main(): builds the UI and wires all interactions

How to run:
# 1. Install dependencies:
#    pip install google-generativeai chromadb langchain langchain-google-genai
#        langchain-community langchain-chroma sentence-transformers streamlit
#        python-docx python-pptx pymupdf Pillow pytesseract pandas
#        python-dotenv tiktoken numpy
#
# 2. Install tesseract OCR engine:
#    Ubuntu/Debian: sudo apt-get install tesseract-ocr
#    macOS:         brew install tesseract
#    Windows:       download installer from github.com/tesseract-ocr/tesseract
#
# 3. Fill in your GEMINI_API_KEY in the .env file
#
# 4. Run:
#    streamlit run app.py
#
# Get your free Gemini API key at: https://aistudio.google.com/app/apikey
"""

from __future__ import annotations

import os
from uuid import uuid4

import streamlit as st
from dotenv import load_dotenv

from rag import InvincibleRAG


load_dotenv()

st.set_page_config(
    page_title="INVINCIBLE",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .stApp {
        font-size: clamp(14px, 1.8vw, 16px);
    }
    section[data-testid="stSidebar"] h1, section[data-testid="stSidebar"] h2 {
        border-left: 4px solid #0f172a;
        padding-left: 0.6rem;
    }
    div[data-testid="stChatMessage"] {
        border-radius: 16px;
        padding: 0.35rem;
    }
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) {
        background: rgba(37, 99, 235, 0.12);
        margin-left: 14%;
    }
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarAssistant"]) {
        background: rgba(148, 163, 184, 0.15);
        margin-right: 14%;
    }
    div[data-testid="stExpander"] {
        border: 1px solid rgba(148, 163, 184, 0.35);
        border-radius: 12px;
    }
    .stButton > button {
        transition: all 0.2s ease;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 6px 18px rgba(15, 23, 42, 0.12);
    }
    @media (max-width: 768px) {
        div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) {
            margin-left: 4%;
        }
        div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarAssistant"]) {
            margin-right: 4%;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def get_rag() -> InvincibleRAG:
    return InvincibleRAG()


def init_session_state() -> None:
    if "rag" not in st.session_state:
        st.session_state.rag = get_rag()
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid4())
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "last_answer" not in st.session_state:
        st.session_state.last_answer = ""
    if "last_query" not in st.session_state:
        st.session_state.last_query = ""
    if "feedback_mode" not in st.session_state:
        st.session_state.feedback_mode = False


def render_sidebar() -> None:
    rag = st.session_state.rag
    with st.sidebar:
        st.title("⚡ INVINCIBLE")
        st.caption("Your AI Study Companion")

        st.subheader("Upload Study Materials")
        uploaded_files = st.file_uploader(
            "Upload files",
            accept_multiple_files=True,
            type=["pdf", "pptx", "docx", "txt", "md", "csv", "png", "jpg", "jpeg", "bmp", "webp"],
        )
        if uploaded_files:
            for uploaded_file in uploaded_files:
                file_key = f"ingested_{uploaded_file.name}_{uploaded_file.size}"
                if st.session_state.get(file_key):
                    continue
                try:
                    with st.spinner(f"Processing {uploaded_file.name}..."):
                        chunk_count = rag.ingest_file(uploaded_file.name, uploaded_file.getvalue())
                    st.success(f"✅ Ingested {chunk_count} chunks from {uploaded_file.name}")
                    st.session_state[file_key] = True
                except Exception as exc:
                    st.error(f"Something went wrong: {exc}")

        st.subheader("Your Documents")
        try:
            documents = rag.list_ingested_files()
            if documents:
                for filename in documents:
                    col1, col2 = st.columns([4, 1])
                    col1.write(filename)
                    if col2.button("🗑", key=f"delete_{filename}", use_container_width=True):
                        try:
                            rag.delete_file(filename)
                            st.success(f"Deleted {filename}")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Something went wrong: {exc}")
            else:
                st.caption("No documents uploaded yet.")
        except Exception as exc:
            st.error(f"Something went wrong: {exc}")

        st.subheader("Stats")
        try:
            stats = rag.get_stats()
            st.write(f"📄 Total Chunks: {stats['total_chunks']}")
            st.write(f"📁 Total Files: {stats['total_files']}")
            st.write(f"🔄 Feedback Corrections: {stats['total_feedback']}")
        except Exception as exc:
            st.error(f"Something went wrong: {exc}")

        st.subheader("New Conversation")
        if st.button("Start Fresh Chat", use_container_width=True):
            st.session_state.session_id = str(uuid4())
            st.session_state.messages = []
            st.session_state.last_answer = ""
            st.session_state.last_query = ""
            st.session_state.feedback_mode = False
            st.rerun()


def render_feedback_ui() -> None:
    rag = st.session_state.rag
    if not st.session_state.last_answer or not st.session_state.last_query:
        return

    st.markdown("**Was this answer correct?**")
    col1, col2 = st.columns(2)
    if col1.button("👍 Yes, it's correct", use_container_width=True):
        st.success("Thanks for confirming.")
        st.session_state.feedback_mode = False
    if col2.button("👎 No, correct me", use_container_width=True):
        st.session_state.feedback_mode = True

    if st.session_state.feedback_mode:
        correction = st.text_area("Enter the correct answer:", key="correction_text")
        if st.button("Submit Correction", use_container_width=True):
            if correction.strip():
                try:
                    rag.record_feedback(
                        query=st.session_state.last_query,
                        bad_answer=st.session_state.last_answer,
                        correction=correction.strip(),
                        session_id=st.session_state.session_id,
                    )
                    st.success("✅ Thank you! I'll remember this correction.")
                    st.session_state.feedback_mode = False
                except Exception as exc:
                    st.error(f"Something went wrong: {exc}")
            else:
                st.warning("Please enter the correct answer before submitting.")


def main() -> None:
    if not os.getenv("GEMINI_API_KEY", "").strip():
        st.error("❌ GEMINI_API_KEY not found in .env file!")
        st.stop()

    init_session_state()
    render_sidebar()

    st.title("💬 Ask Anything About Your Materials")

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    query = st.chat_input("Ask a question about your documents...")
    if query:
        try:
            if not st.session_state.rag.list_ingested_files():
                st.warning("⚠️ Please upload at least one document first!")
                return

            st.session_state.messages.append({"role": "user", "content": query})
            with st.chat_message("user"):
                st.markdown(query)

            with st.chat_message("assistant"):
                with st.spinner("🔍 Searching your documents..."):
                    result = st.session_state.rag.generate_answer(
                        query=query,
                        session_id=st.session_state.session_id,
                    )
                st.markdown(result["answer"])

                with st.expander("📌 Sources Used", expanded=False):
                    for metadata, score in zip(result["sources"], result["scores"]):
                        filename = metadata.get("source", "Unknown")
                        page_or_slide = metadata.get("page_or_slide", "N/A")
                        st.write(
                            f"📄 {filename} | Page/Slide {page_or_slide} | Relevance: {score:.4f}"
                        )

                st.session_state.messages.append(
                    {"role": "assistant", "content": result["answer"]}
                )
                st.session_state.last_answer = result["answer"]
                st.session_state.last_query = query

            render_feedback_ui()
        except Exception as exc:
            st.error(f"Something went wrong: {exc}")

    elif st.session_state.messages:
        render_feedback_ui()


if __name__ == "__main__":
    main()
