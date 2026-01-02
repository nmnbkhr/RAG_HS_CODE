import os
import requests
from langchain.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import FAISS
from langchain.chains import RetrievalQA
from langchain.llms import OpenAI
from langchain.prompts import PromptTemplate
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
if not os.getenv("OPENAI_API_KEY"):
    raise ValueError("OPENAI_API_KEY not found in environment variables or .env file")

# Step 1: Download the latest PDF
def download_latest_pdf(url, save_path):
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            with open(save_path, 'wb') as f:
                f.write(response.content)
            print(f"Downloaded PDF to {save_path}")
        else:
            raise Exception(f"Failed to download PDF: HTTP {response.status_code}")
    except requests.RequestException as e:
        raise Exception(f"Download error: {str(e)}")

# Latest available URL for FY 2024-25; update to FY 2025-26 when available
pdf_url = "https://download1.fbr.gov.pk/Docs/20241021010287106PakistanCustomsTariff-2024-25.pdf"
pdf_path = "pct_latest.pdf"
if not os.path.exists(pdf_path):
    download_latest_pdf(pdf_url, pdf_path)
else:
    print(f"Using existing PDF at {pdf_path}")

# Step 2: Load and split the PDF
try:
    loader = PyPDFLoader(pdf_path, extract_images=False)
    documents = loader.load()
    if not documents:
        raise ValueError("No documents loaded from PDF")
except Exception as e:
    raise Exception(f"Error loading PDF: {str(e)}")

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200
)
texts = text_splitter.split_documents(documents)
if not texts:
    raise ValueError("No text extracted from PDF")

# Step 3: Create embeddings and vector store
try:
    embeddings = OpenAIEmbeddings()
    vectorstore = FAISS.from_documents(texts, embeddings)
except Exception as e:
    raise Exception(f"Error creating vector store: {str(e)}")

# Step 4: Set up the LLM and RAG chain
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

# Function to query a specific HS code
def get_hs_code_details(code):
    query = f"What is the detailed classification, description, and duty for HS code {code}?"
    result = qa_chain({"query": query})
    return result['result']

# Function to classify a single item to HS code
def classify_item(item_description):
    query = f"Classify the item '{item_description}' to the correct HS/PCT code. Provide the code, reasoning, and any relevant notes."
    result = qa_chain({"query": query})
    return result['result']

# Function to classify a list of items
def classify_item_list(items):
    classifications = {}
    for item in items:
        classifications[item] = classify_item(item)
    return classifications

# Example usage
if __name__ == "__main__":
    try:
        print("HS Code Details Example:")
        print(get_hs_code_details("0101.21"))

        print("\nSingle Item Classification Example:")
        print(classify_item("Fresh apples"))

        print("\nList Classification Example:")
        item_list = ["Live horses", "Cotton t-shirts", "Smartphones"]
        classifications = classify_item_list(item_list)
        for item, classification in classifications.items():
            print(f"{item}: {classification}")
    except Exception as e:
        print(f"Error during execution: {str(e)}")