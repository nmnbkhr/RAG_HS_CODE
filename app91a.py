import os
import re
import subprocess
import shutil
import requests
import html
from datetime import datetime
import streamlit as st
from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_core.output_parsers import StrOutputParser
from langchain_core.tools import Tool
from langchain_classic.agents import AgentExecutor, create_react_agent
from langchain_classic.base_memory import BaseMemory
from pydantic import Field
# ConversationBufferMemory is not available in LangChain 1.2.0+
# Using a simple memory wrapper compatible with AgentExecutor
from typing import Dict, List, Any, Optional

class SimpleMemory(BaseMemory):
    """Simple memory wrapper compatible with AgentExecutor"""
    chat_memory_key: str = "history"
    input_key: str = "input"
    chat_memory: List[str] = Field(default_factory=list)

    @property
    def memory_variables(self) -> List[str]:
        """Keys this memory will inject into the chain inputs"""
        return [self.chat_memory_key]
    
    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, Any]):
        """Save conversation context"""
        if self.input_key in inputs:
            self.chat_memory.append(f"Human: {inputs[self.input_key]}")
        if "output" in outputs:
            self.chat_memory.append(f"Assistant: {outputs['output']}")
    
    def load_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, str]:
        """Load memory variables for the agent"""
        history = "\n".join(self.chat_memory[-10:])  # Last 10 exchanges
        return {self.chat_memory_key: history}
    
    def clear(self):
        """Clear memory"""
        self.chat_memory = []

# Load environment variables from .env file
load_dotenv()

# Get and validate API key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if OPENAI_API_KEY:
    OPENAI_API_KEY = OPENAI_API_KEY.strip()  # Remove any whitespace
    os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY  # Update environment

# Constants
PDF_URL = "https://download1.fbr.gov.pk/Docs/20241021010287106PakistanCustomsTariff-2024-25.pdf"
PDF_PATH = "pct_latest.pdf"
FAISS_INDEX_PATH = "faiss_index"
EXCHANGE_RATE_API = "https://api.exchangerate-api.com/v4/latest/PKR"
NBP_USD_RATE_URL = "https://www.nbp.com.pk/RateSheet/index.aspx?view=ExternalLink"
WEBOC_TARIFF_URL = "https://www.weboc.gov.pk/Shared/TariffList.aspx"

# Function to fetch exchange rate
def get_exchange_rate(from_currency):
    """Return PKR conversion rate and source label."""
    currency = from_currency.upper()

    # PKR doesn't need conversion
    if currency == "PKR":
        return 1.0, "PKR (no conversion)"

    # Prefer official NBP board rate for USD
    if currency == "USD":
        nbp_rate = fetch_usd_rate_from_nbp()
        if nbp_rate:
            return nbp_rate, "NBP USD Board Rate"
        st.info("NBP USD rate unavailable, falling back to open exchange API.")

    # Fallback to open rates API for other currencies
    try:
        response = requests.get(f"https://api.exchangerate-api.com/v4/latest/{currency}", timeout=10)
        if response.status_code == 200:
            rates = response.json().get("rates", {})
            pkr_rate = rates.get("PKR")
            if pkr_rate:
                return pkr_rate, "Open exchange API"
        st.warning("Failed to fetch exchange rates. Using 1.0 as default.")
        return 1.0, "Default 1.0 (fallback)"
    except Exception as e:
        st.warning(f"Error fetching exchange rates: {e}. Using PKR as default.")
        return 1.0, "Default 1.0 (error fallback)"

def fetch_usd_rate_from_nbp():
    """Scrape USD->PKR board rate from NBP rate sheet."""
    try:
        response = requests.get(NBP_USD_RATE_URL, timeout=10)
        if response.status_code == 200:
            html = response.text
            # Try common patterns like "USD 280.50" or "US Dollar 280.50"
            match = re.search(r"US\s*D(?:ollar)?[^0-9]{0,10}([0-9]{2,3}\.?[0-9]{0,4})", html, re.IGNORECASE)
            if match:
                return float(match.group(1))
    except Exception as e:
        st.warning(f"Error fetching USD rate from NBP: {e}")
    return None

def fetch_weboc_taxes(hs_code: str, override_url: str = None):
    """Fetch Customs Duty, Sales Tax, and Income Tax from WEBOC Tariff page for a given HS code."""
    try:
        code_digits = re.sub(r"\D", "", hs_code)
        code_dotted = hs_code
        if len(code_digits) == 8:
            code_dotted = f"{code_digits[:4]}.{code_digits[4:]}"

        session = requests.Session()
        session.headers.update({"User-Agent": "Mozilla/5.0 (duty-calculator-bot)"})
        base_url = (override_url or WEBOC_TARIFF_URL).strip()

        initial = session.get(base_url, timeout=15)
        if initial.status_code != 200:
            return None

        page = initial.text
        session_id = session.cookies.get("ASP.NET_SessionId")

        def hidden(name):
            match = re.search(rf'name="{re.escape(name)}".*?value="(.*?)"', page, re.S)
            return html.unescape(match.group(1)) if match else ""

        payload = {
            "__VIEWSTATE": hidden("__VIEWSTATE"),
            "__VIEWSTATEGENERATOR": hidden("__VIEWSTATEGENERATOR"),
            "__VIEWSTATEENCRYPTED": hidden("__VIEWSTATEENCRYPTED"),
            "__EVENTVALIDATION": hidden("__EVENTVALIDATION"),
            "TariffList$txtSearch": code_dotted,
            "TariffList$btnSearch": "Search",
        }

        headers = {"Content-Type": "application/x-www-form-urlencoded", "Referer": WEBOC_TARIFF_URL}

        # If we have an ASP.NET session id and the URL is not already cookieless, use it
        post_url = base_url
        if session_id and "(S(" not in post_url:
            post_url = base_url.replace("/Shared/", f"/(S({session_id}))/Shared/")

        result = session.post(post_url, data=payload, headers=headers, timeout=20)
        if result.status_code != 200:
            return None

        taxes = parse_weboc_duty_table(result.text)
        if taxes:
            taxes["_source_url"] = post_url
            taxes["_status"] = "ok"
        else:
            taxes = {"_status": "parsed_empty", "_source_url": post_url}
        return taxes
    except Exception:
        return None

def parse_weboc_duty_table(html_text: str):
    """Parse duty details table from WEBOC HTML."""
    table_match = re.search(r'id="TariffList_dgDutyDetail".*?>(.*?)</table>', html_text, re.S | re.I)
    if not table_match:
        return None

    table_html = table_match.group(1)
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', table_html, re.S | re.I)
    taxes = {"Customs Duty": None, "Sales Tax": None, "Income Tax": None}

    for row in rows:
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.S | re.I)
        if len(cells) < 1:
            continue
        label_raw = re.sub(r"<.*?>", "", cells[0])
        label = html.unescape(label_raw).strip()
        value_match = re.search(r'@?\s*([0-9]+(?:\.[0-9]+)?)', label)
        if value_match:
            rate = float(value_match.group(1))
            if "Customs Duty" in label and taxes["Customs Duty"] is None:
                taxes["Customs Duty"] = rate
            elif "Sales Tax" in label and taxes["Sales Tax"] is None:
                taxes["Sales Tax"] = rate
            elif "Income Tax" in label and taxes["Income Tax"] is None:
                taxes["Income Tax"] = rate

    if any(v is not None for v in taxes.values()):
        return taxes
    return None

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
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        st.error("OPENAI_API_KEY not found in environment variables.")
        return None
    
    if os.path.exists(FAISS_INDEX_PATH):
        embeddings = OpenAIEmbeddings(openai_api_key=api_key)
        vectorstore = FAISS.load_local(FAISS_INDEX_PATH, embeddings, allow_dangerous_deserialization=True)
        st.info("Loaded existing FAISS index.")
        return vectorstore
    else:
        if not os.path.exists(PDF_PATH):
            st.error("PDF not found. Triggering download...")
            check_pdf_update(PDF_URL, PDF_PATH)
        
        loader = PyPDFLoader(PDF_PATH)
        documents = loader.load()
        
        # Add metadata to documents and extract HS codes
        import re
        processed_documents = []
        for doc in documents:
            # Extract page number from metadata if available
            page_num = doc.metadata.get('page', 0)
            
            # Extract HS codes from the document content (format: XXXX.XXXX - full 8-digit format)
            # Match patterns like 0808.1000, 0101.2100, etc.
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

        embeddings = OpenAIEmbeddings(openai_api_key=api_key)
        vectorstore = FAISS.from_documents(texts, embeddings)
        vectorstore.save_local(FAISS_INDEX_PATH)
        st.success("Built and saved new FAISS index with metadata.")
        return vectorstore

# Set up RAG chain
def setup_qa_chain(vectorstore):
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        st.error("OPENAI_API_KEY not found in environment variables.")
        return None
    llm = ChatOpenAI(temperature=0.5, openai_api_key=api_key)  # Increased for fuzzy matching

    prompt_template = """You are an expert in Pakistan Customs Tariff (PCT) classification. Use the following context from the PCT FY 2024-25 document to answer the question accurately.

CRITICAL REQUIREMENTS:
1. HS/PCT CODE FORMAT: Always use the FULL 8-digit format (e.g., 0808.1000, 0101.2100, NOT 0808.10 or 0101.21)
   - Format: XXXX.XXXX where XXXX.XXXX is the complete code
   - If you see 0808.10 in the context, it means 0808.1000 (add trailing zeros)
   - NEVER shorten codes - always provide the full 8-digit format

2. CD (%) VALUE: You MUST ALWAYS include the Customs Duty percentage - THIS IS CRITICAL
   - Look for "CD (%)" or "CD" column in tables - it may appear as just a number (e.g., 3, 20)
   - Extract the number from the CD column even if it doesn't have % sign
   - If CD is 3, write "Customs Duty (CD): 3%" or "CD: 3%"
   - If CD is 20, write "Customs Duty (CD): 20%" or "CD: 20%"
   - If CD column shows empty or "-", write "CD: 0%" or "CD: Not applicable"
   - ALWAYS include CD in your response - never omit it
   - Format: "Customs Duty (CD): [number]%" or "CD: [number]%"

3. EXTRACTION RULES:
   - Extract information in the exact format: PCT CODE | DESCRIPTION | CD (%)
   - The context contains table data with columns: PCT CODE, DESCRIPTION, and CD (%)
   - Include the full description exactly as it appears in the tariff
   - If multiple codes match, provide all relevant options in a table format

OUTPUT FORMAT (MANDATORY - CD IS REQUIRED):
- For specific HS code queries: 
  HS/PCT Code: [FULL 8-digit code, e.g., 0808.1000]
  Description: [complete description]
  Customs Duty (CD): [percentage]% (e.g., 3%, 20%, 0%)
  
  IMPORTANT: If you cannot find CD in the context, search more carefully. CD is usually in the same row as the HS code.

- For item classification: Same format as above - MUST include CD

- For ambiguous items: Markdown table with FULL codes - EVERY ROW MUST HAVE CD:
  | HS Code | Description | CD (%) |
  |---------|-------------|--------|
  | 0808.1000 | [desc] | 3% |
  | 0808.2000 | [desc] | 20% |
  
  If CD is not found for a code, write "CD: Not found" but still include the row.

EXAMPLES:
- If context shows "0808.10" with CD "3", output: "HS/PCT Code: 0808.1000, Description: ..., Customs Duty (CD): 3%"
- If context shows "0101.21" with CD "3", output: "HS/PCT Code: 0101.2100, Description: ..., Customs Duty (CD): 3%"

Context from PCT FY 2024-25:
{context}

Question: {question}

Answer (MUST include: full 8-digit PCT code, description, and CD %):"""

    PROMPT = PromptTemplate(
        template=prompt_template, input_variables=["context", "question"]
    )

    # Create retriever with more results and better search
    # Increased k to get more chunks that might contain CD information
    retriever = vectorstore.as_retriever(
        search_kwargs={"k": 12},  # Increased to get more relevant chunks with CD data
        search_type="similarity"  # Use similarity search for better matching
    )
    
    # Use LCEL approach with source documents support (compatible with LangChain 1.2.0+)
    def format_docs(docs):
        return "\n\n".join(doc.page_content for doc in docs)
    
    def create_qa_chain_with_sources(input_dict):
        """Create a QA chain that returns both answer and source documents"""
        query = input_dict.get("input", input_dict.get("query", ""))
        # Retrieve documents
        docs = retriever.invoke(query)
        # Format context
        context = format_docs(docs)
        # Use PROMPT template to format the prompt
        formatted_prompt = PROMPT.format(context=context, question=query)
        # For ChatOpenAI, we need to pass as a human message
        from langchain_core.messages import HumanMessage
        messages = [HumanMessage(content=formatted_prompt)]
        # Invoke LLM with messages
        answer = llm.invoke(messages)
        # Extract text from message (ChatOpenAI returns AIMessage)
        if hasattr(answer, 'content'):
            answer_text = answer.content
        elif isinstance(answer, str):
            answer_text = answer
        else:
            answer_text = str(answer)
        # Return in format compatible with old RetrievalQA
        return {
            "answer": answer_text,
            "result": answer_text,
            "context": docs,
            "source_documents": docs
        }
    
    # Create a runnable that mimics RetrievalQA behavior
    qa_chain = RunnableLambda(create_qa_chain_with_sources)
    return qa_chain

# Helper function to normalize HS code to full 8-digit format
def normalize_hs_code(code):
    """Normalize HS code to full 8-digit format (XXXX.XXXX)"""
    if not code:
        return code
    # Remove any whitespace
    code = code.strip()
    # Remove any non-digit/dot characters
    code = re.sub(r'[^\d.]', '', code)
    # Check if it's already in full format
    if re.match(r'^\d{4}\.\d{4}$', code):
        return code
    # Try to normalize formats like 0808.10 to 0808.1000
    match = re.match(r'^(\d{4})\.(\d+)$', code)
    if match:
        prefix = match.group(1)
        suffix = match.group(2)
        # Pad suffix to 4 digits
        suffix = suffix.ljust(4, '0')
        return f"{prefix}.{suffix}"
    # Try to normalize formats like 01.01 to 0101.0100
    match = re.match(r'^(\d{2})\.(\d{2})$', code)
    if match:
        prefix = match.group(1).ljust(4, '0')
        suffix = match.group(2).ljust(4, '0')
        return f"{prefix}.{suffix}"
    return code

# Tools for the agent
def get_hs_code_details(code):
    """Get HS code details - with error handling"""
    try:
        qa_chain = st.session_state.qa_chain
        if qa_chain is None:
            return "Error: QA chain not initialized. Please check the vectorstore."
        
        # Normalize input code to full format
        normalized_code = normalize_hs_code(code)
        if not normalized_code:
            return "Error: Invalid HS code format. Please provide a code like 0808.1000 or 0808.10"
        
        query = f"What is the detailed classification, description, and Customs Duty (CD %) for HS/PCT code {normalized_code}? CRITICAL: You MUST include the CD percentage from the table. Look in the CD (%) column for this code. Provide the full 8-digit code format, complete description, and CD percentage in this exact format: HS/PCT Code: [code], Description: [desc], Customs Duty (CD): [number]%"
        result = qa_chain.invoke({"input": query})
        result_text = result.get('answer', result.get('result', ''))
        
        # Also get source documents to extract CD if missing
        # create_retrieval_chain returns documents in "context" key
        source_docs = result.get("context", [])
        if not source_docs and "source_documents" in result:
            source_docs = result.get("source_documents", [])
        
        # Post-process to ensure full format and CD is present
        # Normalize any codes in the result
        lines = result_text.split("\n")
        processed_lines = []
        has_cd = False
        cd_value = None
        
        for line in lines:
            # Check if CD is mentioned
            if "Customs Duty" in line or "CD:" in line or "CD (%)" in line:
                has_cd = True
                # Extract CD value
                cd_match = re.search(r'(\d+)\s*%', line)
                if cd_match:
                    cd_value = cd_match.group(1)
            
            # Normalize codes in the line
            code_matches = re.findall(r'\b\d{2,4}\.\d{2,4}\b', line)
            for match in code_matches:
                normalized = normalize_hs_code(match)
                if normalized != match:
                    line = line.replace(match, normalized)
            processed_lines.append(line)
        
        # If CD is missing, try to extract from source documents
        if not has_cd and source_docs:
            for doc in source_docs[:5]:
                doc_text = doc.page_content
                # Look for the HS code in the document (use simple string matching, not regex)
                if normalized_code in doc_text or normalized_code[:4] in doc_text:
                    # Find CD value near the HS code (within 200 chars)
                    code_pos = doc_text.find(normalized_code)
                    if code_pos == -1:
                        # Try without dots
                        code_pos = doc_text.find(normalized_code.replace(".", ""))
                    if code_pos != -1:
                        context = doc_text[max(0, code_pos-100):code_pos+300]
                        # Look for CD patterns
                        cd_patterns = [
                            r'CD\s*[\(\)%:]*\s*(\d+)',
                            r'Customs\s+Duty[^:]*:\s*(\d+)',
                            r'(\d+)\s*%',
                        ]
                        for pattern in cd_patterns:
                            matches = re.findall(pattern, context, re.IGNORECASE)
                            if matches:
                                cd_value = matches[0]
                                processed_lines.append(f"\n**Customs Duty (CD)**: {cd_value}% (extracted from source)")
                                has_cd = True
                                break
                    if has_cd:
                        break
        
        # If still no CD, add a note
        if not has_cd:
            processed_lines.append("\n⚠️ **Customs Duty (CD)**: Not found in retrieved documents. Please check the tariff manually.")
        
        result = "\n".join(processed_lines)
        return result
    except Exception as e:
        return f"Error getting HS code details: {str(e)}. Please check the code format and try again."

def classify_item(item_description):
    """Classify a single item - with error handling"""
    try:
        qa_chain = st.session_state.qa_chain
        if qa_chain is None:
            return "Error: QA chain not initialized. Please check the vectorstore."
        
        if not item_description or not item_description.strip():
            return "Error: Item description is required."
        
        query = f"Classify the item '{item_description}' to the correct HS/PCT code. Provide the FULL 8-digit code format (e.g., 0808.1000), complete description, Customs Duty (CD %), and any relevant notes."
        result = qa_chain.invoke({"input": query})
        result = result.get('answer', result.get('result', ''))
        
        # Post-process to normalize codes
        lines = result.split("\n")
        processed_lines = []
        for line in lines:
            code_matches = re.findall(r'\b\d{2,4}\.\d{2,4}\b', line)
            for match in code_matches:
                normalized = normalize_hs_code(match)
                if normalized != match:
                    line = line.replace(match, normalized)
            processed_lines.append(line)
        
        return "\n".join(processed_lines)
    except Exception as e:
        return f"Error classifying item: {str(e)}. Please try again with a clearer description."

def classify_item_list(items_str):
    """Classify multiple items - with error handling"""
    try:
        qa_chain = st.session_state.qa_chain
        if qa_chain is None:
            return "Error: QA chain not initialized. Please check the vectorstore."
        
        items = [item.strip() for item in items_str.replace(",", "\n").split("\n") if item.strip()]
        if not items:
            return "No valid items provided. Please provide a list of items."
        
        classifications = []
        for item in items:
            query = f"Classify the item '{item}' to the correct HS/PCT code. Provide the FULL 8-digit code format (e.g., 0808.1000), complete description, Customs Duty (CD %), and any relevant notes."
            result = qa_chain.invoke({"input": query})
            result = result.get('answer', result.get('result', ''))
            # Format as markdown table
            lines = result.split("\n")
            hs_code = description = duty = reasoning = "Not found"
            for line in lines:
                if "HS/PCT Code:" in line or "HS Code:" in line:
                    hs_code = line.split(":")[1].strip()
                    # Normalize to full 8-digit format if needed
                    hs_code = normalize_hs_code(hs_code)
                elif "Description:" in line:
                    description = line.split(":")[1].strip()
                elif "Customs Duty" in line or "CD:" in line or "Duty:" in line:
                    # Extract CD percentage
                    duty_text = line.split(":")[1].strip() if ":" in line else line
                    # Extract number and % sign
                    duty_match = re.search(r'(\d+(?:\.\d+)?)\s*%', duty_text)
                    if duty_match:
                        duty = f"{duty_match.group(1)}%"
                    else:
                        # Try to find just a number
                        num_match = re.search(r'(\d+(?:\.\d+)?)', duty_text)
                        if num_match:
                            duty = f"{num_match.group(1)}%"
                        else:
                            duty = duty_text if duty_text else "Not found"
                elif "Reasoning:" in line:
                    reasoning = line.split(":")[1].strip()
            classifications.append((item, hs_code, description, duty, reasoning))
        
        # Create markdown table
        table = "| Item | HS Code | Description | Duty | Reasoning |\n"
        table += "|------|---------|-------------|------|-----------|\n"

        for item, hs_code, desc, duty, reason in classifications:
            table += f"| {item} | {hs_code} | {desc} | {duty} | {reason} |\n"

        return table
    except Exception as e:
        return f"Error classifying items: {str(e)}. Please try again with clearer descriptions."

def suggest_possible_hs_codes(item_description):
    """Suggest possible HS codes for an item - with error handling"""
    try:
        qa_chain = st.session_state.qa_chain
        if qa_chain is None:
            return "Error: QA chain not initialized. Please check the vectorstore."
        
        if not item_description or not item_description.strip():
            return "Error: Item description is required."
        
        query = f"Provide a markdown table of possible HS/PCT codes for '{item_description}' using fuzzy matching. Include FULL 8-digit HS codes (e.g., 0808.1000), descriptions, and Customs Duty (CD %) for each possibility, followed by a clarification request. Format as:\n| HS Code | Description | CD (%) |\n|---------|-------------|--------|\n| 0808.1000 | [desc] | 3% |\nPlease specify the type of {item_description}."
        result = qa_chain.invoke({"input": query})
        result = result.get('answer', result.get('result', ''))
        
        # Post-process to normalize codes in the result
        lines = result.split("\n")
        processed_lines = []
        for line in lines:
            code_matches = re.findall(r'\b\d{2,4}\.\d{2,4}\b', line)
            for match in code_matches:
                normalized = normalize_hs_code(match)
                if normalized != match:
                    line = line.replace(match, normalized)
            processed_lines.append(line)
        
        return "\n".join(processed_lines)
    except Exception as e:
        return f"Error suggesting HS codes: {str(e)}. Please try again with a clearer description."

tools = [
    Tool(
        name="HS_Code_Details",
        func=get_hs_code_details,
        description="Use to get detailed information about a specific HS code (e.g., '0101.21'), including classification, description, and duties."
    ),
    Tool(
        name="Classify_Item",
        func=classify_item,
        description="Use to classify a single item (e.g., 'Fresh apples') to its HS/PCT code, providing code, reasoning, and any relevant notes."
    ),
    Tool(
        name="Classify_Item_List",
        func=classify_item_list,
        description="Use to classify a list of items (comma-separated or one per line, e.g., 'Live horses, Cotton t-shirts') to their HS/PCT codes, returning a markdown table."
    ),
    Tool(
        name="Suggest_Possible_HS_Codes",
        func=suggest_possible_hs_codes,
        description="Use to get a markdown table of possible HS/PCT codes, descriptions, and duties for a vague or ambiguous item description, using fuzzy matching, followed by a clarification request."
    ),
]

# Agent prompt with tools and tool_names
# Simplified prompt to reduce parsing errors
agent_prompt = ChatPromptTemplate.from_template("""
You are an HS Code expert assistant. Use the provided tools to answer questions about HS codes and item classifications based on Pakistan's Customs Tariff.

Available tools: {tools}
Tool names: {tool_names}

IMPORTANT: Follow this format exactly:
Thought: [Your reasoning about what tool to use]
Action: [Tool name]
Action Input: [Input for the tool - use exact format: "item description" or "code"]
Observation: [Tool result]
... (repeat if needed)
Final Answer: [Your final response to the user]

Instructions:
1. For specific HS code queries (e.g., "What is 0808.1000?" or "What is HS code 0101.21?"):
   - Use HS_Code_Details tool with the code (normalize to 8 digits if needed)
   - Return the result in Final Answer

2. For single item classification (e.g., "Classify fresh apples" or "What is the HS code for apples?"):
   - Use Classify_Item tool with the item description
   - Return the result in Final Answer

3. For multiple items (e.g., "Classify live horses, cotton t-shirts"):
   - Use Classify_Item_List tool with comma-separated items
   - Return the result in Final Answer

4. For vague/ambiguous items (e.g., just "coal" or "apples" without context):
   - Use Suggest_Possible_HS_Codes tool
   - Return the table with clarification request in Final Answer

5. Always provide Final Answer after using tools. Do not loop unnecessarily.

Previous conversation:
{history}

Question: {input}

{agent_scratchpad}
""")

# Streamlit App Configuration
st.set_page_config(
    page_title="HS Code RAG Assistant",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better UI
st.markdown("""
    <style>
    .main {
        padding: 1rem 2rem;
    }
    .stChatMessage {
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 1rem;
    }
    .stChatMessage[data-testid="user"] {
        background-color: #f0f2f6;
    }
    .stChatMessage[data-testid="assistant"] {
        background-color: #e8f4f8;
    }
    .chat-container {
        max-height: 600px;
        overflow-y: auto;
        padding: 1rem;
    }
    .sidebar .sidebar-content {
        background-color: #f8f9fa;
    }
    h1 {
        color: #1f77b4;
        border-bottom: 3px solid #1f77b4;
        padding-bottom: 0.5rem;
    }
    .stButton>button {
        width: 100%;
        border-radius: 5px;
        border: none;
        padding: 0.5rem 1rem;
        font-weight: 600;
        transition: all 0.3s;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    </style>
""", unsafe_allow_html=True)

# Streamlit App - Chat Interface and Calculator
st.title("📋 Interactive HS Code Chat Agent & Duty Calculator")

# Function to run RAG file
def run_rag_file():
    """Run rag_hs_code.py to rebuild vectorstore"""
    try:
        rag_file_path = os.path.join(os.getcwd(), "rag_hs_code.py")
        if not os.path.exists(rag_file_path):
            return False, f"File not found: {rag_file_path}"
        
        # Run the RAG file
        result = subprocess.run(
            ["python", rag_file_path],
            capture_output=True,
            text=True,
            timeout=600  # 10 minutes timeout
        )
        
        if result.returncode == 0:
            return True, f"RAG file executed successfully!\n{result.stdout}"
        else:
            return False, f"Error executing RAG file:\n{result.stderr}"
    except subprocess.TimeoutExpired:
        return False, "RAG file execution timed out (exceeded 10 minutes)"
    except Exception as e:
        return False, f"Error running RAG file: {str(e)}"

# Sidebar for PDF management
with st.sidebar:
    st.header("⚙️ System Management")
    
    st.subheader("PDF Management")
    if st.button("🔄 Check/Update PDF", use_container_width=True):
        with st.spinner("Checking for updates..."):
            updated, message = check_pdf_update(PDF_URL, PDF_PATH)
            if updated:
                st.success(message)
                if os.path.exists(FAISS_INDEX_PATH):
                    shutil.rmtree(FAISS_INDEX_PATH)
                    st.info("Old vectorstore removed. Please rebuild below.")
            else:
                st.info(message)
    
    st.markdown("---")
    
    st.subheader("Vectorstore Management")
    
    # Option 1: Regular rebuild
    if st.button("🔄 Rebuild Vectorstore (Run RAG)", use_container_width=True, type="primary"):
        with st.spinner("Running RAG file and rebuilding vectorstore... This may take several minutes."):
            success, message = run_rag_file()
            if success:
                st.success("✅ Vectorstore rebuilt successfully!")
                st.code(message, language="text")
                # Clear cache to force reload
                st.cache_resource.clear()
                st.rerun()
            else:
                st.error("❌ Failed to rebuild vectorstore")
                st.code(message, language="text")
    
    # Option 2: Force rebuild (delete and rebuild)
    if st.button("🗑️ Force Rebuild (Delete & Rebuild)", use_container_width=True):
        if st.session_state.get("confirm_force_rebuild", False):
            with st.spinner("Deleting old vectorstore and rebuilding..."):
                try:
                    # Delete old vectorstore
                    if os.path.exists(FAISS_INDEX_PATH):
                        shutil.rmtree(FAISS_INDEX_PATH)
                        st.info("✅ Old vectorstore deleted.")
                    
                    # Rebuild
                    success, message = run_rag_file()
                    if success:
                        st.success("✅ Vectorstore force rebuilt successfully!")
                        st.cache_resource.clear()
                        st.session_state.confirm_force_rebuild = False
                        st.rerun()
                    else:
                        st.error(f"❌ Failed to rebuild: {message}")
                except Exception as e:
                    st.error(f"Error: {str(e)}")
        else:
            st.session_state.confirm_force_rebuild = True
            st.warning("⚠️ Click again to confirm force rebuild (will delete existing index)")
    
    # Option 3: Check PDF and update vectorstore
    if st.button("📥 Check PDF & Update Vectorstore", use_container_width=True):
        with st.spinner("Checking for PDF updates..."):
            updated, message = check_pdf_update(PDF_URL, PDF_PATH)
            if updated:
                st.success(f"✅ {message}")
                st.info("📋 PDF updated. Vectorstore needs to be rebuilt.")
                if st.button("🔄 Rebuild Vectorstore Now", use_container_width=True, key="rebuild_after_pdf"):
                    with st.spinner("Rebuilding vectorstore with new PDF..."):
                        try:
                            if os.path.exists(FAISS_INDEX_PATH):
                                shutil.rmtree(FAISS_INDEX_PATH)
                            success, rebuild_msg = run_rag_file()
                            if success:
                                st.success("✅ Vectorstore rebuilt with new PDF!")
                                st.cache_resource.clear()
                                st.rerun()
                            else:
                                st.error(f"❌ {rebuild_msg}")
                        except Exception as e:
                            st.error(f"Error: {str(e)}")
            else:
                st.info(message)
    
    st.markdown("---")
    
    st.subheader("Information")
    st.info("📅 Using FY 2024-25 Tariff\n\nCheck FBR for FY 2025-26 updates.")
    
    # Show vectorstore status
    if os.path.exists(FAISS_INDEX_PATH):
        st.success("✅ Vectorstore exists")
        try:
            index_size = sum(
                os.path.getsize(os.path.join(FAISS_INDEX_PATH, f))
                for f in os.listdir(FAISS_INDEX_PATH)
                if os.path.isfile(os.path.join(FAISS_INDEX_PATH, f))
            )
            st.caption(f"Index size: {index_size / (1024*1024):.2f} MB")
        except:
            pass
    else:
        st.warning("⚠️ Vectorstore not found. Please rebuild.")
    
    if os.path.exists(PDF_PATH):
        pdf_size = os.path.getsize(PDF_PATH) / (1024*1024)
        pdf_date = datetime.fromtimestamp(os.path.getmtime(PDF_PATH))
        st.caption(f"📄 PDF: {pdf_size:.2f} MB")
        st.caption(f"📅 Last updated: {pdf_date.strftime('%Y-%m-%d %H:%M')}")

# Initialize session state
api_key = os.getenv("OPENAI_API_KEY", "").strip()
if not api_key:
    st.error("OpenAI API key not set. Please check your .env file at E:\\RAG_HS_Code\\.env or set it manually.")
    st.stop()
else:
    vectorstore = get_vectorstore()
    if vectorstore is None:
        st.error("Failed to initialize vectorstore. Please check your API key and try again.")
        st.stop()
    qa_chain = setup_qa_chain(vectorstore)
    if qa_chain is None:
        st.error("Failed to initialize QA chain. Please check your API key and try again.")
        st.stop()
    st.session_state.qa_chain = qa_chain

    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "memory" not in st.session_state:
        # Use 'history' as the key to match what AgentExecutor provides
        st.session_state.memory = SimpleMemory(chat_memory_key="history", input_key="input")

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    llm = ChatOpenAI(temperature=0.5, openai_api_key=api_key)
    agent = create_react_agent(llm, tools, agent_prompt)
    # Better error handling function
    def handle_parsing_error(error):
        """Handle parsing errors gracefully"""
        return f"I encountered an error processing your request. Please try rephrasing your question. For example: 'What is HS code 0808.1000?' or 'Classify fresh apples'."
    
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        memory=st.session_state.memory,
        verbose=True,
        handle_parsing_errors=handle_parsing_error,
        max_iterations=15,  # Increased to allow more tool calls
        max_execution_time=300,  # 5 minutes for complex queries
        return_intermediate_steps=False  # Don't return intermediate steps to avoid clutter
    )

    # Tabs for Chat and Calculator
    tab1, tab2 = st.tabs(["💬 Chat Interface", "🧮 Duty Calculator"])

    with tab1:
        st.header("💬 Chat with HS Code Agent")
        st.caption("Ask questions about HS codes, classify items, or get detailed tariff information")
        
        # Quick action buttons
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if st.button("📋 Example: HS Code Query", use_container_width=True):
                example_query = "What is HS code 0808.1000?"
                st.session_state.example_query = example_query
        with col2:
            if st.button("🍎 Example: Classify Item", use_container_width=True):
                example_query = "Classify fresh apples"
                st.session_state.example_query = example_query
        with col3:
            if st.button("📊 Example: Multiple Items", use_container_width=True):
                example_query = "Classify live horses, cotton t-shirts"
                st.session_state.example_query = example_query
        with col4:
            if st.button("🗑️ Clear Chat", use_container_width=True):
                st.session_state.messages = []
                st.session_state.memory = SimpleMemory(chat_memory_key="history", input_key="input")
                st.rerun()
        
        st.markdown("---")
        
        # Chat container with scrollable area
        chat_container = st.container()
        with chat_container:
            # Display chat history
            if st.session_state.messages:
                for message in st.session_state.messages:
                    with st.chat_message(message["role"]):
                        st.markdown(message["content"])
            else:
                # Welcome message
                with st.chat_message("assistant"):
                    st.markdown("""
                    👋 **Welcome to the HS Code Assistant!**
                    
                    I can help you with:
                    - 🔍 **HS Code Lookup**: Get details for specific codes (e.g., "What is HS code 0808.1000?")
                    - 📦 **Item Classification**: Classify items to HS codes (e.g., "Classify fresh apples")
                    - 📋 **Batch Classification**: Classify multiple items at once
                    - 💡 **Suggestions**: Get possible codes for ambiguous items
                    
                    Try asking a question or use the example buttons above!
                    """)
        
        # Handle example query
        prompt = None
        if hasattr(st.session_state, 'example_query'):
            prompt = st.session_state.example_query
            delattr(st.session_state, 'example_query')
        
        # User input
        user_input = st.chat_input(
            "Ask about HS codes or item classifications...",
            key="chat_input"
        )
        
        if user_input:
            prompt = user_input
        
        if prompt:
            # Add user message
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            # Get assistant response
            with st.chat_message("assistant"):
                with st.spinner("🤔 Thinking..."):
                    try:
                        response = agent_executor.invoke({"input": prompt})
                        output = response.get("output", "No output generated")
                        
                        # Check if agent stopped due to limits
                        if "Agent stopped due to iteration limit" in output or "Agent stopped due to time limit" in output:
                            st.warning("⚠️ The query took too long or required too many steps. Try simplifying your question.")
                            # Try to extract any useful information from intermediate steps
                            if "intermediate_steps" in response:
                                st.info("Partial results may be available above.")
                        
                        # Check if there are multiple possible responses (tables with multiple rows)
                        # Extract multiple HS codes from the response
                        multiple_responses = []
                        if "| HS Code |" in output or "| HS/PCT Code |" in output:
                            # Parse table to extract multiple options
                            lines = output.split("\n")
                            in_table = False
                            current_table = []
                            for line in lines:
                                if "|" in line and ("HS Code" in line or "HS/PCT Code" in line):
                                    in_table = True
                                    current_table = [line]  # Header
                                elif in_table and "|" in line:
                                    current_table.append(line)
                                    # Check if this is a data row (not separator)
                                    if "---" not in line and line.strip().startswith("|"):
                                        parts = [p.strip() for p in line.split("|") if p.strip()]
                                        if len(parts) >= 3:  # Has code, description, CD
                                            multiple_responses.append({
                                                "code": parts[0] if len(parts) > 0 else "",
                                                "description": parts[1] if len(parts) > 1 else "",
                                                "cd": parts[2] if len(parts) > 2 else "Not found"
                                            })
                                elif in_table and "|" not in line and line.strip():
                                    in_table = False
                        
                        # If multiple responses found, show selection UI
                        if len(multiple_responses) > 1:
                            st.info(f"📋 Found {len(multiple_responses)} possible HS codes. Select one to view details:")
                            
                            # Create selection interface
                            selected_idx = st.selectbox(
                                "Select HS Code:",
                                range(len(multiple_responses)),
                                format_func=lambda x: f"{multiple_responses[x]['code']} - {multiple_responses[x]['description'][:50]}... (CD: {multiple_responses[x]['cd']})",
                                key=f"select_response_{len(st.session_state.messages)}"
                            )
                            
                            # Show selected response details
                            selected = multiple_responses[selected_idx]
                            
                            # Get more details for selected code with CD if missing
                            if selected['cd'] == "Not found" or not selected['cd'] or selected['cd'].strip() == "":
                                detail_query = f"What is HS code {selected['code']}? CRITICAL: Include Customs Duty (CD %) from the table."
                                try:
                                    detail_result = qa_chain.invoke({"input": detail_query})
                                    detail_output = detail_result.get('answer', detail_result.get('result', ''))
                                    
                                    # Extract CD from detail output
                                    cd_match = re.search(r'Customs\s+Duty\s*\(?CD\)?:?\s*(\d+)\s*%', detail_output, re.IGNORECASE)
                                    if not cd_match:
                                        cd_match = re.search(r'CD[:\s]*(\d+)\s*%', detail_output, re.IGNORECASE)
                                    if cd_match:
                                        selected['cd'] = f"{cd_match.group(1)}%"
                                    else:
                                        # Try to extract from source documents
                                        # create_retrieval_chain returns documents in "context" key
                                        detail_docs = detail_result.get("context", [])
                                        if not detail_docs and "source_documents" in detail_result:
                                            detail_docs = detail_result.get("source_documents", [])
                                        if detail_docs:
                                            for doc in detail_docs[:5]:
                                                doc_text = doc.page_content
                                                code_to_find = selected['code']
                                                if code_to_find in doc_text or code_to_find.replace(".", "") in doc_text:
                                                    # Find CD near the code
                                                    code_pos = doc_text.find(code_to_find)
                                                    if code_pos == -1:
                                                        code_pos = doc_text.find(code_to_find.replace(".", ""))
                                                    if code_pos != -1:
                                                        context = doc_text[max(0, code_pos-150):code_pos+400]
                                                        cd_match = re.search(r'CD\s*[\(\)%:]*\s*(\d+)', context, re.IGNORECASE)
                                                        if cd_match:
                                                            selected['cd'] = f"{cd_match.group(1)}%"
                                                            break
                                except Exception as e:
                                    pass
                            
                            # Display selected response with CD
                            st.markdown(f"""
                            **✅ Selected HS Code Details:**
                            
                            - **HS/PCT Code**: `{selected['code']}`
                            - **Description**: {selected['description']}
                            - **Customs Duty (CD)**: **{selected['cd']}**
                            """)
                            
                            # Option to get full details
                            if st.button("📋 Get Full Details", key=f"full_details_{selected_idx}_{len(st.session_state.messages)}"):
                                with st.spinner("Fetching full details..."):
                                    full_details = get_hs_code_details(selected['code'])
                                    st.markdown("**Full Details:**")
                                    st.markdown(full_details)
                            
                            # Show full table for reference
                            with st.expander("📊 View All Options", expanded=False):
                                st.markdown(output)
                        else:
                            # Single response - check if CD is missing and try to extract it
                            if "Customs Duty" not in output and "CD:" not in output and "CD (%)" not in output:
                                st.warning("⚠️ Customs Duty (CD) not found in response. Trying to extract from source documents...")
                                # Try to get CD from source documents
                                # create_retrieval_chain returns documents in "context" key
                                if "context" in response or "source_documents" in response or hasattr(qa_chain, 'retriever'):
                                    try:
                                        # Get source documents
                                        source_query = f"HS code {prompt} Customs Duty CD percentage"
                                        source_results = qa_chain.invoke({"input": source_query})
                                        # create_retrieval_chain returns documents in "context" key
                                        source_docs_list = source_results.get("context", [])
                                        if not source_docs_list and "source_documents" in source_results:
                                            source_docs_list = source_results.get("source_documents", [])
                                        if source_docs_list:
                                            for doc in source_docs_list[:3]:
                                                # Look for CD in document content
                                                doc_text = doc.page_content
                                                cd_match = re.search(r'CD\s*[\(\)%:]*\s*(\d+)', doc_text, re.IGNORECASE)
                                                if cd_match:
                                                    cd_value = cd_match.group(1)
                                                    st.info(f"💡 Found CD: {cd_value}% in source document")
                                                    output += f"\n\n**Customs Duty (CD)**: {cd_value}% (extracted from source)"
                                                    break
                                    except:
                                        pass
                            
                            st.markdown(output)
                        
                        st.session_state.messages.append({"role": "assistant", "content": output})
                    except Exception as e:
                        error_msg = str(e)
                        
                        # Provide helpful error messages
                        if "OUTPUT_PARSING_FAILURE" in error_msg or "parsing" in error_msg.lower():
                            output = f"""❌ **Parsing Error**: The agent had trouble understanding the response format.

**Suggestions:**
- Try rephrasing your question more simply
- For HS codes, use format: "What is HS code 0808.1000?"
- For classification, use: "Classify fresh apples"
- For multiple items, use: "Classify item1, item2, item3"

**Original error**: {error_msg[:200]}"""
                        elif "iteration limit" in error_msg.lower() or "time limit" in error_msg.lower():
                            output = f"""⚠️ **Query Timeout**: The query took too long to process.

**Suggestions:**
- Break down complex queries into simpler ones
- Try one item at a time instead of multiple items
- Check if the vectorstore is properly initialized

**Original error**: {error_msg[:200]}"""
                        else:
                            output = f"""❌ **Error**: {error_msg}

**Troubleshooting:**
1. Check if the vectorstore is properly initialized
2. Verify your OpenAI API key is valid
3. Try a simpler query
4. Rebuild the vectorstore if needed"""
                        
                        st.error(output)
                        st.session_state.messages.append({"role": "assistant", "content": output})
            
            # Auto-scroll to bottom (rerun to show new message)
            st.rerun()


    with tab2:
        st.header("🧮 Duty Calculator")
        st.caption("WEBOC-style CIF calculator with USD board rate pulled from NBP.")
        st.markdown("---")
        
        # Quick KPIs for the last calculation
        summary = st.session_state.get("duty_calc_summary")
        if summary:
            st.markdown("#### Latest Calculation Snapshot")
            kpi1, kpi2, kpi3 = st.columns(3)
            kpi1.metric(
                "Assessable Value (PKR)",
                f"{summary['assessable_pkr']:,.0f}",
                help="CIF-style value converted to PKR"
            )
            kpi2.metric(
                "Duty (PKR)",
                f"{summary['duty_pkr']:,.0f}",
                help="Calculated duty in PKR"
            )
            kpi3.metric(
                "Rate Source",
                summary["rate_source"],
                help="Exchange rate source used in the calculation"
            )
            # Show WEBOC taxes if available
            if summary.get("weboc_sales_tax") is not None or summary.get("weboc_income_tax") is not None:
                st.caption(
                    f"WEBOC Taxes — Sales Tax: {summary.get('weboc_sales_tax', 'N/A')}% | Income Tax: {summary.get('weboc_income_tax', 'N/A')}%"
                )
            if summary.get("weboc_status") not in (None, "ok"):
                st.caption(f"WEBOC fetch status: {summary.get('weboc_status')}, source: {summary.get('weboc_source')}")
            st.markdown("---")
        
        # Input form in columns for better layout
        col1, col2 = st.columns(2)
        
        with col1:
            hs_code = st.text_input(
                "📦 HS Code", 
                placeholder="e.g., 0808.1000",
                help="Enter the full 8-digit HS/PCT code",
                key="calc_hs_code"
            )
            quantity = st.number_input(
                "🔢 Quantity", 
                min_value=0.0, 
                step=0.1,
                help="Enter the quantity of items",
                key="calc_quantity"
            )
            value_per_unit = st.number_input(
                "💰 Invoice/FOB Value per Unit", 
                min_value=0.0, 
                step=0.1,
                help="Enter the invoice value per unit in the selected currency",
                key="calc_value"
            )
        
        with col2:
            unit = st.selectbox(
                "⚖️ Unit of Measurement", 
                ["kg", "liters", "units", "tonnes"],
                help="Select the unit of measurement",
                key="calc_unit"
            )
            currency = st.selectbox(
                "💱 Currency", 
                ["USD", "PKR", "EUR"],
                help="Select the currency for invoice value (USD uses NBP board rate by default)",
                key="calc_currency"
            )
        
        weboc_url_override = st.text_input(
            "WEBOC URL override (optional)",
            value=st.session_state.get("weboc_url_override", ""),
            placeholder="https://www.weboc.gov.pk/(S(...))/Shared/TariffList.aspx",
            help="Paste a working WEBOC TariffList URL with session token if automatic lookup fails.",
            key="weboc_url_override"
        )
        
        st.markdown("#### CIF / Customs Value Inputs (WEBOC approach)")
        cif_col1, cif_col2 = st.columns(2)
        with cif_col1:
            freight = st.number_input(
                "✈️ Freight / Carriage", 
                min_value=0.0, 
                step=0.1,
                value=0.0,
                help="Freight or carriage charges in the same currency as the invoice",
                key="calc_freight"
            )
            insurance = st.number_input(
                "🛡️ Insurance", 
                min_value=0.0, 
                step=0.1,
                value=0.0,
                help="Insurance charges in the same currency",
                key="calc_insurance"
            )
        with cif_col2:
            other_charges = st.number_input(
                "📦 Other Charges", 
                min_value=0.0, 
                step=0.1,
                value=0.0,
                help="Packing/landing/agency or other additions",
                key="calc_other_charges"
            )
            manual_usd_rate = st.number_input(
                "📈 Override USD Board Rate (PKR)", 
                min_value=0.0, 
                step=0.01,
                value=0.0,
                help="Leave at 0 to auto-use NBP rate. Set a value to override.",
                key="calc_manual_usd_rate"
            )
        
        st.markdown("---")
        
        if st.button("Calculate Duty"):
            if not hs_code or quantity <= 0 or value_per_unit <= 0:
                st.error("Please provide a valid HS code, quantity, and value per unit.")
            else:
                with st.spinner("Fetching duty rate..."):
                    try:
                        # Normalize input HS code
                        normalized_code = normalize_hs_code(hs_code)
                        duty_info = get_hs_code_details(normalized_code)
                        duty_rate = None
                        duty_type = None
                        duty_text = "N/A"
                        lines = duty_info.split("\n")
                        for line in lines:
                            # Look for CD in various formats
                            if "Customs Duty" in line or "CD:" in line or "Duty:" in line:
                                # Extract the value after colon
                                if ":" in line:
                                    duty_text = line.split(":")[1].strip()
                                else:
                                    duty_text = line
                                # Extract percentage value
                                if "%" in duty_text:
                                    # Extract number before %
                                    match = re.search(r"(\d+(?:\.\d+)?)\s*%", duty_text)
                                    if match:
                                        duty_rate = float(match.group(1)) / 100
                                        duty_type = "ad_valorem"
                                elif "PKR" in duty_text:
                                    duty_rate = float(duty_text.replace("PKR", "").split("/")[0].strip())
                                    duty_type = f"specific_{duty_text.split('/')[-1].strip()}"
                                elif re.search(r"\d+", duty_text):
                                    # Try to extract just a number
                                    match = re.search(r"(\d+(?:\.\d+)?)", duty_text)
                                    if match:
                                        duty_rate = float(match.group(1)) / 100
                                        duty_type = "ad_valorem"
                                if duty_rate is not None:
                                    break
                        
                        if duty_rate is None:
                            st.error(f"Could not parse duty rate from: {duty_info}")
                        else:
                            exchange_rate, rate_source = get_exchange_rate(currency)
                            if currency == "USD" and manual_usd_rate > 0:
                                exchange_rate = manual_usd_rate
                                rate_source = "Manual override"
                            
                            # CIF-style assessable value (FOB + freight + insurance + other) in selected currency
                            base_value_currency = value_per_unit * quantity
                            assessable_value_currency = base_value_currency + freight + insurance + other_charges
                            total_value_pkr = assessable_value_currency * exchange_rate
                            
                            if duty_type == "ad_valorem":
                                duty_pkr = total_value_pkr * duty_rate
                            else:
                                if unit == duty_type.split("_")[1]:
                                    duty_pkr = quantity * duty_rate
                                else:
                                    st.error(f"Unit mismatch: Tariff uses {duty_type.split('_')[1]}, but you selected {unit}.")
                                    duty_pkr = None
                            
                            if duty_pkr is not None:
                                st.success(f"""
                                **Duty Calculation Result**  
                                - HS Code: {hs_code}  
                                - Quantity: {quantity} {unit}  
                                - Invoice Value per Unit: {value_per_unit} {currency}  
                                - Freight/Insurance/Other: {freight + insurance + other_charges:.2f} {currency}  
                                - Assessable (CIF-style) Value: {assessable_value_currency:.2f} {currency}  
                                - Exchange Rate Used: {exchange_rate:.4f} PKR per {currency} ({rate_source})  
                                - Total Value (PKR): {total_value_pkr:.2f} PKR  
                                - Duty Rate: {duty_text}  
                                - Total Duty: {duty_pkr:.2f} PKR
                                """)
                                st.session_state.messages.append({
                                    "role": "assistant",
                                    "content": f"Duty calculated for HS code {hs_code}: {quantity} {unit} at {value_per_unit} {currency}, total duty {duty_pkr:.2f} PKR (exchange source: {rate_source})."
                                })
                                # Fetch WEBOC taxes (Sales Tax / Income Tax) for reference
                                weboc_taxes = fetch_weboc_taxes(normalized_code, st.session_state.get("weboc_url_override", ""))
                                if weboc_taxes:
                                    if weboc_taxes.get("_status") == "ok":
                                        st.info(f"Sales Tax: {weboc_taxes.get('Sales Tax', 'N/A')}% | Income Tax: {weboc_taxes.get('Income Tax', 'N/A')}% | Customs Duty (WEBOC): {weboc_taxes.get('Customs Duty', 'N/A')}%")
                                    else:
                                        st.caption("WEBOC responded but duty table was empty; try refreshing/pasting your session URL.")
                                else:
                                    st.caption("Could not retrieve Sales Tax/Income Tax from WEBOC right now.")

                                st.session_state["duty_calc_summary"] = {
                                    "hs_code": hs_code,
                                    "assessable_currency": assessable_value_currency,
                                    "assessable_pkr": total_value_pkr,
                                    "duty_pkr": duty_pkr,
                                    "rate_source": rate_source,
                                    "exchange_rate": exchange_rate,
                                    "currency": currency,
                                    "duty_text": duty_text,
                                    "weboc_sales_tax": weboc_taxes.get('Sales Tax') if weboc_taxes else None,
                                    "weboc_income_tax": weboc_taxes.get('Income Tax') if weboc_taxes else None,
                                    "weboc_source": weboc_taxes.get("_source_url") if weboc_taxes else None,
                                    "weboc_status": weboc_taxes.get("_status") if weboc_taxes else None,
                                }
                    except Exception as e:
                        st.error(f"Error calculating duty: {str(e)}")
                        st.session_state.messages.append({"role": "assistant", "content": f"Error calculating duty for HS code {hs_code}: {str(e)}"})
