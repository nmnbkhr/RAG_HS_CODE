import os
import requests
from datetime import datetime
import streamlit as st
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.chains import RetrievalQA
from langchain_community.llms import OpenAI
from langchain.prompts import PromptTemplate
from dotenv import load_dotenv

# Constants
PDF_URL = "https://download1.fbr.gov.pk/Docs/20241021010287106PakistanCustomsTariff-2024-25.pdf"
PDF_PATH = "pct_latest.pdf"
FAISS_INDEX_PATH = "/mnt/e/rag_hs_codedata/faiss_index"
load_dotenv()

# Function to check if PDF needs updating and download if necessary
def check_pdf_update(url, local_path):
    try:
        response = requests.head(url)
        if response.status_code == 200:
            last_modified_str = response.headers.get('Last-Modified')
            if last_modified_str:
                remote_date = datetime.strptime(last_modified_str, '%a, %d %b %Y %H:%M:%S GMT')
                if os.path.exists(local_path):
                    local_date = datetime.fromtimestamp(os.path.getmtime(local_path))
                    if remote_date > local_date:
                        download_latest_pdf(url, local_path)
                        return True, "PDF updated to latest version."
                    else:
                        return False, "Local PDF is up-to-date."
                else:
                    download_latest_pdf(url, local_path)
                    return True, "PDF downloaded (no local file existed)."
            else:
                download_latest_pdf(url, local_path)
                return True, "No Last-Modified header; PDF downloaded."
        else:
            return False, f"Failed to check PDF: HTTP {response.status_code}"
    except Exception as e:
        return False, f"Error checking PDF update: {e}"

def download_latest_pdf(url, save_path):
    response = requests.get(url)
    if response.status_code == 200:
        with open(save_path, 'wb') as f:
            f.write(response.content)
        st.success(f"Downloaded PDF to {save_path}")
    else:
        raise Exception("Failed to download PDF")

# Function to build or load vector store
@st.cache_resource
def get_vectorstore():
    if os.path.exists(FAISS_INDEX_PATH):
        embeddings = OpenAIEmbeddings()
        vectorstore = FAISS.load_local(FAISS_INDEX_PATH, embeddings, allow_dangerous_deserialization=True)
        st.info("Loaded existing FAISS index.")
        return vectorstore
    else:
        if not os.path.exists(PDF_PATH):
            st.error("PDF not found. Triggering download...")
            check_pdf_update(PDF_URL, PDF_PATH)
        
        loader = PyPDFLoader(PDF_PATH)
        documents = loader.load()

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        texts = text_splitter.split_documents(documents)

        embeddings = OpenAIEmbeddings()
        vectorstore = FAISS.from_documents(texts, embeddings)
        vectorstore.save_local(FAISS_INDEX_PATH)
        st.success("Built and saved new FAISS index.")
        return vectorstore

# Set up LLM and QA chain
def setup_qa_chain(vectorstore):
    llm = OpenAI(temperature=0.2)

    prompt_template = """Use the following HS code context to answer the question. Provide the exact HS/PCT code, description, and any duty rates or notes. If classifying an item, match it to the closest heading/subheading based on the description.

    Context: {context}

    Question: {question}

    Answer:"""

    PROMPT = PromptTemplate(
        template=prompt_template, input_variables=["context", "question"]
    )

    qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=vectorstore.as_retriever(search_kwargs={"k": 5}),
        return_source_documents=True,
        chain_type_kwargs={"prompt": PROMPT}
    )
    return qa_chain

# Streamlit App
st.title("HS Code Query and Classification Tool")

# Sidebar for PDF update
with st.sidebar:
    st.header("PDF Management")
    if st.button("Check/Update PDF"):
        with st.spinner("Checking for updates..."):
            updated, message = check_pdf_update(PDF_URL, PDF_PATH)
            st.info(message)
            if updated:
                # Rebuild FAISS if PDF updated
                if os.path.exists(FAISS_INDEX_PATH):
                    import shutil
                    shutil.rmtree(FAISS_INDEX_PATH)
                st.info("PDF updated. Rebuilding FAISS index on next query...")

    st.markdown("---")
    st.info("Using FY 2024-25 Tariff (latest available).")

# Load vectorstore and QA chain
if "OPENAI_API_KEY" not in os.environ:
    st.error("OpenAI API key not set. Set it via environment variable or in code.")
else:
    vectorstore = get_vectorstore()
    qa_chain = setup_qa_chain(vectorstore)

    # Tabs for different functionalities
    tab1, tab2, tab3 = st.tabs(["Query HS Code", "Classify Single Item", "Classify List of Items"])

    with tab1:
        st.subheader("Query HS Code Details")
        hs_code = st.text_input("Enter HS Code (e.g., 0101.21):")
        if st.button("Get Details") and hs_code:
            with st.spinner("Querying..."):
                query = f"What is the detailed classification, description, and duty for HS code {hs_code}?"
                result = qa_chain({"query": query})['result']
                st.write(result)

    with tab2:
        st.subheader("Classify Single Item")
        item_desc = st.text_input("Enter Item Description (e.g., Fresh apples):")
        if st.button("Classify") and item_desc:
            with st.spinner("Classifying..."):
                query = f"Classify the item '{item_desc}' to the correct HS/PCT code. Provide the code, reasoning, and any relevant notes."
                result = qa_chain({"query": query})['result']
                st.write(result)

    with tab3:
        st.subheader("Classify List of Items")
        st.info("Enter items separated by commas or one per line.")
        items_text = st.text_area("Enter Items (e.g., Live horses, Cotton t-shirts, Smartphones):")
        if st.button("Classify List") and items_text:
            items = [item.strip() for item in items_text.replace(",", "\n").split("\n") if item.strip()]
            if items:
                with st.spinner("Classifying..."):
                    classifications = {}
                    progress_bar = st.progress(0)
                    for i, item in enumerate(items):
                        query = f"Classify the item '{item}' to the correct HS/PCT code. Provide the code, reasoning, and any relevant notes."
                        result = qa_chain({"query": query})['result']
                        classifications[item] = result
                        progress_bar.progress((i + 1) / len(items))
                    
                    for item, classification in classifications.items():
                        st.markdown(f"**{item}:**")
                        st.write(classification)
            else:
                st.warning("No items entered.")