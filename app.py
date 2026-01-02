import os
import requests
import streamlit as st
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.chains import RetrievalQA
from langchain_community.llms import OpenAI
from langchain.prompts import PromptTemplate
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
if not os.getenv("OPENAI_API_KEY"):
    st.error("OPENAI_API_KEY not found. Please add it to a .env file.")
    st.stop()

# Initialize session state for vector store
if 'vectorstore' not in st.session_state:
    st.session_state.vectorstore = None
    st.session_state.qa_chain = None

# Step 1: Download the latest PDF
def download_latest_pdf(url, save_path):
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            with open(save_path, 'wb') as f:
                f.write(response.content)
            return True
        else:
            raise Exception(f"Failed to download PDF: HTTP {response.status_code}")
    except requests.RequestException as e:
        raise Exception(f"Download error: {str(e)}")

# Step 2: Initialize RAG system
@st.cache_resource
def initialize_rag():
    pdf_url = "https://download1.fbr.gov.pk/Docs/20241021010287106PakistanCustomsTariff-2024-25.pdf"
    pdf_path = "pct_latest.pdf"
    if not os.path.exists(pdf_path):
        with st.spinner("Downloading Pakistan Customs Tariff PDF..."):
            download_latest_pdf(pdf_url, pdf_path)
    else:
        st.info(f"Using existing PDF at {pdf_path}")

    with st.spinner("Loading and processing PDF..."):
        try:
            loader = PyPDFLoader(pdf_path, extract_images=False)
            documents = loader.load()
            if not documents:
                raise ValueError("No documents loaded from PDF")
        except Exception as e:
            st.error(f"Error loading PDF: {str(e)}")
            st.stop()

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        texts = text_splitter.split_documents(documents)
        if not texts:
            raise ValueError("No text extracted from PDF")

        try:
            embeddings = OpenAIEmbeddings()
            vectorstore = FAISS.from_documents(texts, embeddings)
        except Exception as e:
            st.error(f"Error creating vector store: {str(e)}")
            st.stop()

        llm = OpenAI(temperature=0.2)
        prompt_template = """Use the following HS code context to answer the question. Provide the exact HS/PCT code, description, and any duty rates or notes. If classifying an item, match it to the closest heading/subheading based on the description. If the query is ambiguous, suggest a more specific description.

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
        return vectorstore, qa_chain

# Step 3: Query functions
def get_hs_code_details(code):
    if not code.strip():
        return "Please enter a valid HS code."
    query = f"What is the detailed classification, description, and duty for HS code {code}?"
    try:
        result = st.session_state.qa_chain({"query": query})
        return result['result']
    except Exception as e:
        return f"Error querying HS code: {str(e)}"

def classify_item(item_description):
    if not item_description.strip():
        return "Please enter a valid item description."
    if len(item_description.split()) < 2 or item_description.lower() in ['phone', 'computer', 'food', 'clothing']:
        return "Query is too broad. Please provide a more specific description (e.g., 'smartphone' instead of 'phone')."
    query = f"Classify the item '{item_description}' to the correct HS/PCT code. Provide the code, reasoning, and any relevant notes."
    try:
        result = st.session_state.qa_chain({"query": query})
        return result['result']
    except Exception as e:
        return f"Error classifying item: {str(e)}"

def classify_item_list(items):
    classifications = {}
    for item in items:
        classifications[item] = classify_item(item)
    return classifications

# Streamlit UI
st.title("HS Code Lookup and Classification")
st.write("Query HS codes or classify items based on the Pakistan Customs Tariff (FY 2024-25).")

# Initialize RAG system
if st.session_state.vectorstore is None:
    st.session_state.vectorstore, st.session_state.qa_chain = initialize_rag()

# Tabbed interface
tab1, tab2, tab3 = st.tabs(["Query HS Code", "Classify Single Item", "Classify Item List"])

with tab1:
    st.header("Query HS Code")
    hs_code = st.text_input("Enter HS Code (e.g., 0101.21):")
    if st.button("Get HS Code Details"):
        if hs_code:
            with st.spinner("Fetching HS code details..."):
                result = get_hs_code_details(hs_code)
                st.markdown(result)
        else:
            st.warning("Please enter an HS code.")

with tab2:
    st.header("Classify a Single Item")
    item_description = st.text_input("Enter item description (e.g., Fresh apples):")
    if st.button("Classify Item"):
        if item_description:
            with st.spinner("Classifying item..."):
                result = classify_item(item_description)
                st.markdown(result)
        else:
            st.warning("Please enter an item description.")

with tab3:
    st.header("Classify a List of Items")
    st.write("Enter items (one per line) or upload a text file.")
    item_list_text = st.text_area("Enter items (e.g., Live horses\\nCotton t-shirts\\nSmartphones):")
    uploaded_file = st.file_uploader("Or upload a text file", type=["txt"])
    
    items = []
    if uploaded_file:
        items = uploaded_file.read().decode("utf-8").splitlines()
    elif item_list_text:
        items = [item.strip() for item in item_list_text.splitlines() if item.strip()]

    if st.button("Classify List"):
        if items:
            with st.spinner("Classifying items..."):
                classifications = classify_item_list(items)
                for item, classification in classifications.items():
                    st.subheader(f"Item: {item}")
                    st.markdown(classification)
        else:
            st.warning("Please enter or upload a list of items.")