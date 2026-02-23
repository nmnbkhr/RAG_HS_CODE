import os
import re
import shutil
import requests
from datetime import datetime
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.documents import Document
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
if not os.getenv("OPENAI_API_KEY"):
    raise ValueError("OPENAI_API_KEY not found in environment variables or .env file")

# Constants
PDF_URL = "https://download1.fbr.gov.pk/Docs/20241021010287106PakistanCustomsTariff-2024-25.pdf"
PDF_PATH = "pct_latest.pdf"
PDF_OLD_PATH = "pct_old.pdf"
FAISS_INDEX_PATH = "/mnt/e/rag_hs_codedata/faiss_index"

# Step 1: Check if PDF needs updating and download if necessary
def check_pdf_update(url, local_path, old_path):
    """Check if a new PDF is available and download it, backing up the old one."""
    try:
        response = requests.head(url, timeout=10)
        if response.status_code == 200:
            last_modified_str = response.headers.get('Last-Modified')
            if last_modified_str:
                remote_date = datetime.strptime(last_modified_str, '%a, %d %b %Y %H:%M:%S GMT')
                if os.path.exists(local_path):
                    local_date = datetime.fromtimestamp(os.path.getmtime(local_path))
                    if remote_date > local_date:
                        # Backup current PDF to old file
                        if os.path.exists(local_path):
                            shutil.copy2(local_path, old_path)
                            print(f"Backed up current PDF to {old_path}")
                        # Download new PDF
                        download_latest_pdf(url, local_path)
                        return True, "PDF updated to latest version."
                    else:
                        return False, "Local PDF is up-to-date."
                else:
                    download_latest_pdf(url, local_path)
                    return True, "PDF downloaded (no local file existed)."
            else:
                # No Last-Modified header, check by file size or download anyway
                if os.path.exists(local_path):
                    # Backup current PDF
                    shutil.copy2(local_path, old_path)
                    print(f"Backed up current PDF to {old_path}")
                download_latest_pdf(url, local_path)
                return True, "No Last-Modified header; PDF downloaded."
        else:
            return False, f"Failed to check PDF: HTTP {response.status_code}"
    except Exception as e:
        return False, f"Error checking PDF update: {e}"

def download_latest_pdf(url, save_path):
    """Download PDF from URL and save to path."""
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            with open(save_path, 'wb') as f:
                f.write(response.content)
            print(f"Downloaded PDF to {save_path}")
            return True
        else:
            raise Exception(f"Failed to download PDF: HTTP {response.status_code}")
    except requests.RequestException as e:
        raise Exception(f"Download error: {str(e)}")

# Check for PDF updates
print("Checking for PDF updates...")
updated, message = check_pdf_update(PDF_URL, PDF_PATH, PDF_OLD_PATH)
print(f"PDF Status: {message}")

# Determine if vectorstore needs to be rebuilt
rebuild_vectorstore = updated or not os.path.exists(FAISS_INDEX_PATH)

# Step 2: Load and split the PDF with metadata
def build_vectorstore():
    """Build or rebuild the vectorstore from the PDF."""
    print("Loading PDF...")
    try:
        loader = PyPDFLoader(PDF_PATH, extract_images=False)
        documents = loader.load()
        if not documents:
            raise ValueError("No documents loaded from PDF")
    except Exception as e:
        raise Exception(f"Error loading PDF: {str(e)}")
    
    # Add metadata to documents and extract HS codes
    print("Processing documents and extracting metadata...")
    processed_documents = []
    for doc in documents:
        # Extract page number from metadata if available
        page_num = doc.metadata.get('page', 0)
        
        # Extract HS codes from the document content (format: XXXX.XXXX - full 8-digit format)
        hs_codes = re.findall(r'\b\d{4}\.\d{4}\b', doc.page_content)
        
        # Create enhanced metadata
        metadata = {
            'source': PDF_PATH,
            'page': page_num,
            'hs_codes': ', '.join(hs_codes[:5]) if hs_codes else '',  # Store first 5 HS codes found
            'document_type': 'Pakistan Customs Tariff FY 2024-25'
        }
        
        # Create new document with enhanced metadata
        processed_doc = Document(
            page_content=doc.page_content,
            metadata=metadata
        )
        processed_documents.append(processed_doc)
    
    # Use smaller chunk size to preserve table structure (HS code, description, duty relationships)
    print("Splitting documents into chunks...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,  # Reduced to preserve table row relationships
        chunk_overlap=100,  # Reduced overlap proportionally
        separators=["\n\n", "\n", "|", " ", ""]  # Split on table separators first
    )
    texts = text_splitter.split_documents(processed_documents)
    
    # Add HS code metadata to each chunk if not already present
    for text in texts:
        if not text.metadata.get('hs_codes'):
            # Try to extract HS codes from this chunk (full 8-digit format)
            chunk_hs_codes = re.findall(r'\b\d{4}\.\d{4}\b', text.page_content)
            if chunk_hs_codes:
                text.metadata['hs_codes'] = ', '.join(chunk_hs_codes[:3])  # Store first 3 for this chunk
    
    if not texts:
        raise ValueError("No text extracted from PDF")
    
    # Step 3: Create embeddings and vector store
    print("Creating embeddings and vector store...")
    try:
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        
        embeddings = OpenAIEmbeddings(openai_api_key=api_key)
        
        # Remove old index if rebuilding
        if os.path.exists(FAISS_INDEX_PATH):
            shutil.rmtree(FAISS_INDEX_PATH)
            print(f"Removed old vectorstore at {FAISS_INDEX_PATH}")
        
        vectorstore = FAISS.from_documents(texts, embeddings)
        vectorstore.save_local(FAISS_INDEX_PATH)
        print(f"Vectorstore created and saved to {FAISS_INDEX_PATH}")
        return vectorstore
    except Exception as e:
        raise Exception(f"Error creating vector store: {str(e)}")

# Build or load vectorstore
if rebuild_vectorstore:
    print("Rebuilding vectorstore...")
    vectorstore = build_vectorstore()
else:
    print("Loading existing vectorstore...")
    try:
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        
        embeddings = OpenAIEmbeddings(openai_api_key=api_key)
        vectorstore = FAISS.load_local(FAISS_INDEX_PATH, embeddings, allow_dangerous_deserialization=True)
        print(f"Loaded existing vectorstore from {FAISS_INDEX_PATH}")
    except Exception as e:
        print(f"Error loading vectorstore: {e}. Rebuilding...")
        vectorstore = build_vectorstore()

# Step 4: Set up the LLM and RAG chain
api_key = os.getenv("OPENAI_API_KEY", "").strip()
llm = ChatOpenAI(temperature=0.5, openai_api_key=api_key)

prompt_template = """You are an expert in Pakistan Customs Tariff (PCT) classification. Use the following context from the PCT FY 2024-25 document to answer the question accurately.

CRITICAL REQUIREMENTS:
1. HS/PCT CODE FORMAT: Always use the FULL 8-digit format (e.g., 0808.1000, 0101.2100, NOT 0808.10 or 0101.21)
2. CD (%) VALUE: You MUST ALWAYS include the Customs Duty percentage (e.g., 3%, 20%)
3. Extract information in the exact format: PCT CODE | DESCRIPTION | CD (%)

OUTPUT FORMAT:
- HS/PCT Code: [FULL 8-digit code, e.g., 0808.1000]
- Description: [complete description]
- Customs Duty (CD): [percentage]% (e.g., 3%, 20%)

Context from PCT FY 2024-25:
{context}

Question: {question}

Answer (MUST include: full 8-digit PCT code, description, and CD %):"""

PROMPT = PromptTemplate(
    template=prompt_template, input_variables=["context", "question"]
)

# Create retriever with more results and better search
retriever = vectorstore.as_retriever(
    search_kwargs={"k": 8},  # Increased to get more relevant chunks
    search_type="similarity"  # Use similarity search for better matching
)

# Create QA chain using LCEL (LangChain Expression Language)
def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

qa_chain = (
    {
        "context": retriever | format_docs,
        "question": RunnablePassthrough()
    }
    | PROMPT
    | llm
    | StrOutputParser()
)

# Helper function to normalize HS code to full 8-digit format
def normalize_hs_code(code):
    """Normalize HS code to full 8-digit format (XXXX.XXXX)"""
    if not code:
        return code
    code = code.strip()
    code = re.sub(r'[^\d.]', '', code)
    if re.match(r'^\d{4}\.\d{4}$', code):
        return code
    match = re.match(r'^(\d{4})\.(\d+)$', code)
    if match:
        prefix = match.group(1)
        suffix = match.group(2).ljust(4, '0')
        return f"{prefix}.{suffix}"
    match = re.match(r'^(\d{2})\.(\d{2})$', code)
    if match:
        prefix = match.group(1).ljust(4, '0')
        suffix = match.group(2).ljust(4, '0')
        return f"{prefix}.{suffix}"
    return code

# Function to query a specific HS code
def get_hs_code_details(code):
    normalized_code = normalize_hs_code(code)
    query = f"What is the detailed classification, description, and Customs Duty (CD %) for HS/PCT code {normalized_code}? Provide the full 8-digit code format, complete description, and CD percentage."
    result = qa_chain.invoke(query)
    return result

# Function to classify a single item to HS code
def classify_item(item_description):
    query = f"Classify the item '{item_description}' to the correct HS/PCT code. Provide the FULL 8-digit code format (e.g., 0808.1000), complete description, Customs Duty (CD %), and any relevant notes."
    result = qa_chain.invoke(query)
    return result

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