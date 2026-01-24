import os
import re
import shutil
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import streamlit as st
from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

# Load environment variables
load_dotenv()

# Get and validate API key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if OPENAI_API_KEY:
    OPENAI_API_KEY = OPENAI_API_KEY.strip()
    os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY

# Constants
PDF_URL = "https://download1.fbr.gov.pk/Docs/20241021010287106PakistanCustomsTariff-2024-25.pdf"
PDF_PATH = "pct_latest.pdf"
FAISS_INDEX_PATH = "faiss_index"
WEBOC_TARIFF_URL = "https://www.weboc.gov.pk/Shared/TariffList.aspx"
NBP_USD_RATE_URL = "https://www.nbp.com.pk/RateSheet/index.aspx?view=ExternalLink"

# WEBOC Scraper Class
class WEBOCTariffScraper:
    """Enhanced scraper for WEBOC duty data with UOM extraction"""
    
    def __init__(self, base_url: str = None):
        self.base_url = base_url or WEBOC_TARIFF_URL
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.last_error = None
    
    def normalize_hs_code(self, hs_code: str) -> str:
        """Normalize HS code to XXXX.XXXX format"""
        digits = re.sub(r'\D', '', hs_code)
        if len(digits) < 8:
            digits = digits.ljust(8, '0')
        elif len(digits) > 8:
            digits = digits[:8]
        return f"{digits[:4]}.{digits[4:]}"
    
    def get_form_data(self, html: str) -> dict:
        """Extract ASP.NET form data"""
        soup = BeautifulSoup(html, 'html.parser')
        hidden_fields = soup.find_all('input', type='hidden')
        data = {}
        for field in hidden_fields:
            name = field.get('name')
            value = field.get('value', '')
            if name:
                data[name] = value
        return data
    
    def extract_unit_of_measure(self, text: str) -> str:
        """Extract unit of measure from description or table"""
        # Common UOM patterns in WEBOC
        uom_patterns = {
            r'\bkg\b|\bkilogram': 'kg',
            r'\blitre|\bliter': 'liters',
            r'\btonne|\bton\b': 'tonnes',
            r'\bunit|\bunits|\bpiece|\bpieces|\bpcs': 'units',
            r'\bmetre|\bmeter': 'meters',
            r'\bpair': 'pairs',
            r'\bdozen': 'dozens',
            r'\bset': 'sets'
        }
        
        text_lower = text.lower()
        for pattern, uom in uom_patterns.items():
            if re.search(pattern, text_lower):
                return uom
        
        return 'units'  # Default
    
    def search_hs_code(self, hs_code: str) -> dict:
        """Search for HS code and extract duty rates, description, and UOM"""
        normalized_code = self.normalize_hs_code(hs_code)
        
        try:
            # Get initial page
            response = self.session.get(self.base_url, timeout=15, allow_redirects=True)
            if response.status_code != 200:
                return self._error_result(normalized_code, f"HTTP {response.status_code}")
            
            actual_url = response.url
            form_data = self.get_form_data(response.text)
            
            if not form_data.get('__VIEWSTATE'):
                return self._error_result(normalized_code, "Session expired - ViewState not found")
            
            # Find search controls
            soup = BeautifulSoup(response.text, 'html.parser')
            search_box = soup.find('input', {'id': re.compile('txtSearch', re.I)})
            search_button = soup.find('input', {'id': re.compile('btnSearch', re.I)})
            
            if not search_box:
                return self._error_result(normalized_code, "Search controls not found")
            
            search_box_name = search_box.get('name', 'TariffList$txtSearch')
            search_button_name = search_button.get('name', 'TariffList$btnSearch') if search_button else 'TariffList$btnSearch'
            
            # Submit search
            payload = {
                **form_data,
                search_box_name: normalized_code,
                search_button_name: 'Search'
            }
            
            post_response = self.session.post(
                actual_url,
                data=payload,
                headers={
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Referer': actual_url
                },
                timeout=20
            )
            
            if post_response.status_code != 200:
                return self._error_result(normalized_code, f"Search failed: HTTP {post_response.status_code}")
            
            # Parse results
            result = self.parse_duty_table(post_response.text, normalized_code)
            if result:
                result['status'] = 'success'
                result['search_code'] = normalized_code
                return result
            else:
                return self._error_result(normalized_code, "No duty data found")
                
        except Exception as e:
            return self._error_result(normalized_code, str(e))
    
    def _error_result(self, code: str, error: str) -> dict:
        """Create error result"""
        self.last_error = error
        return {
            'search_code': code,
            'status': 'failed',
            'error': error,
            'customs_duty': None,
            'sales_tax': None,
            'income_tax': None,
            'additional_duty': None,
            'regulatory_duty': None,
            'description': None,
            'unit_of_measure': 'units'
        }
    
    def parse_duty_table(self, html: str, hs_code: str) -> dict:
        """Parse duty details table with UOM extraction"""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Find duty table
        duty_table = soup.find('table', {'id': re.compile('dgDutyDetail', re.I)})
        if not duty_table:
            duty_table = soup.find('table', class_=re.compile('duty', re.I))
        if not duty_table:
            tables = soup.find_all('table')
            for table in tables:
                text = table.get_text().lower()
                if 'customs duty' in text or 'sales tax' in text:
                    duty_table = table
                    break
        
        if not duty_table:
            return None
        
        result = {
            'hs_code': hs_code,
            'customs_duty': None,
            'sales_tax': None,
            'income_tax': None,
            'additional_duty': None,
            'regulatory_duty': None,
            'description': None,
            'unit_of_measure': 'units'
        }
        
        # Find description
        desc_selectors = [
            {'id': re.compile('lblDescription|Description', re.I)},
            {'class': re.compile('description', re.I)}
        ]
        
        for selector in desc_selectors:
            desc_element = soup.find('span', selector) or soup.find('div', selector)
            if desc_element:
                result['description'] = desc_element.get_text(strip=True)
                # Extract UOM from description
                result['unit_of_measure'] = self.extract_unit_of_measure(result['description'])
                break
        
        # Parse table rows
        rows = duty_table.find_all('tr')
        full_table_text = duty_table.get_text()
        
        for row in rows:
            cells = row.find_all(['td', 'th'])
            if len(cells) < 1:
                continue
            
            cell_texts = [cell.get_text(strip=True) for cell in cells]
            row_text = ' '.join(cell_texts)
            
            # Check for UOM in row text
            if 'unit' in row_text.lower() or 'uom' in row_text.lower():
                uom = self.extract_unit_of_measure(row_text)
                if uom != 'units':
                    result['unit_of_measure'] = uom
            
            # Extract rate
            rate_matches = re.findall(r'(\d+(?:\.\d+)?)\s*%', row_text)
            if not rate_matches:
                rate_matches = re.findall(r'@?\s*(\d+(?:\.\d+)?)', row_text)
            
            if not rate_matches:
                continue
            
            rate_value = float(rate_matches[0])
            row_lower = row_text.lower()
            
            # Classify duty type
            if ('customs duty' in row_lower or 'cd' in row_lower) and result['customs_duty'] is None:
                result['customs_duty'] = rate_value
            elif ('sales tax' in row_lower or 'st' in row_lower or 'gst' in row_lower) and result['sales_tax'] is None:
                result['sales_tax'] = rate_value
            elif ('income tax' in row_lower or 'it' in row_lower or 'wht' in row_lower) and result['income_tax'] is None:
                result['income_tax'] = rate_value
            elif ('additional' in row_lower and 'duty' in row_lower) and result['additional_duty'] is None:
                result['additional_duty'] = rate_value
            elif ('regulatory' in row_lower and 'duty' in row_lower) and result['regulatory_duty'] is None:
                result['regulatory_duty'] = rate_value
        
        # Final UOM extraction from full table
        if result['unit_of_measure'] == 'units':
            result['unit_of_measure'] = self.extract_unit_of_measure(full_table_text)
        
        if any([result['customs_duty'], result['sales_tax'], result['income_tax']]):
            return result
        return None

# Exchange rate functions
def fetch_usd_rate_from_nbp():
    """Scrape USD->PKR rate from NBP - For Customs Use SBP/NBP Official Rate"""
    try:
        # Try NBP rate sheet first
        response = requests.get(NBP_USD_RATE_URL, timeout=10)
        if response.status_code == 200:
            text = response.text
            
            # Multiple regex patterns to catch USD rate
            patterns = [
                r'USD[^\d]*(\d{3}\.\d{2,4})',  # USD 280.55
                r'US\s*Dollar[^\d]*(\d{3}\.\d{2,4})',  # US Dollar 280.55
                r'Dollar.*?TT.*?Selling[^\d]*(\d{3}\.\d{2,4})',  # TT Selling rate
                r'US\s*D(?:ollar)?[^0-9]{0,30}([0-9]{2,3}\.\d{2,4})',  # Flexible pattern
            ]
            
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    rate = float(match.group(1))
                    # Sanity check: USD should be between 200-400 PKR as of 2026
                    if 200 < rate < 400:
                        return rate
        
        # Fallback to SBP exchange rate API if available
        try:
            sbp_response = requests.get("https://www.sbp.org.pk/ecodata/rates/m2m/m2m-current.asp", timeout=10)
            if sbp_response.status_code == 200:
                # Try to extract from SBP page
                match = re.search(r'USD[^\d]*(\d{3}\.\d{2,4})', sbp_response.text)
                if match:
                    rate = float(match.group(1))
                    if 200 < rate < 400:
                        return rate
        except:
            pass
            
    except Exception as e:
        st.warning(f"Error fetching NBP/SBP rate: {e}")
    
    # Return hardcoded fallback based on current market rate (Jan 2026: ~280-281)
    # This should be updated periodically or fetched from a reliable API
    return 280.50  # Default fallback as of January 2026

def get_exchange_rate(from_currency):
    """Get PKR conversion rate - Uses NBP/SBP official rates for customs compliance"""
    currency = from_currency.upper()
    
    if currency == "PKR":
        return 1.0, "PKR (no conversion)"
    
    # For USD, use NBP official rate (required for Pakistan Customs)
    if currency == "USD":
        nbp_rate = fetch_usd_rate_from_nbp()
        if nbp_rate and nbp_rate > 200:  # Sanity check
            return nbp_rate, "NBP/SBP Official Rate (For Customs)"
        # If NBP fails, use current market rate
        st.warning("⚠️ Could not fetch live NBP rate. Using estimated market rate.")
        return 280.50, "Estimated Market Rate (NBP unavailable)"
    
    # For other currencies, use exchange rate API
    try:
        response = requests.get(f"https://api.exchangerate-api.com/v4/latest/{currency}", timeout=10)
        if response.status_code == 200:
            rates = response.json().get("rates", {})
            pkr_rate = rates.get("PKR")
            if pkr_rate:
                return pkr_rate, f"Open Exchange API ({currency} to PKR)"
    except:
        pass
    
    st.warning(f"⚠️ Could not fetch exchange rate for {currency}. Using 1.0 as fallback.")
    return 1.0, "Default 1.0 (fallback)"

# PDF and vectorstore functions
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
                        return True, "PDF updated"
                    else:
                        return False, "PDF up-to-date"
                else:
                    download_latest_pdf(url, local_path)
                    return True, "PDF downloaded"
        return False, f"Failed: HTTP {response.status_code}"
    except Exception as e:
        return False, f"Error: {e}"

def download_latest_pdf(url, save_path):
    response = requests.get(url)
    if response.status_code == 200:
        with open(save_path, 'wb') as f:
            f.write(response.content)

@st.cache_resource
def get_vectorstore():
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None
    
    if os.path.exists(FAISS_INDEX_PATH):
        embeddings = OpenAIEmbeddings(openai_api_key=api_key)
        vectorstore = FAISS.load_local(FAISS_INDEX_PATH, embeddings, allow_dangerous_deserialization=True)
        return vectorstore
    else:
        if not os.path.exists(PDF_PATH):
            check_pdf_update(PDF_URL, PDF_PATH)
        
        loader = PyPDFLoader(PDF_PATH)
        documents = loader.load()
        
        processed_documents = []
        for doc in documents:
            page_num = doc.metadata.get('page', 0)
            hs_codes = re.findall(r'\b\d{4}\.\d{4}\b', doc.page_content)
            
            metadata = {
                'source': PDF_PATH,
                'page': page_num,
                'hs_codes': ', '.join(hs_codes[:5]) if hs_codes else '',
                'document_type': 'Pakistan Customs Tariff FY 2024-25'
            }
            
            processed_doc = Document(page_content=doc.page_content, metadata=metadata)
            processed_documents.append(processed_doc)

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=800,
            chunk_overlap=200,
            separators=["\n\n", "\n", "|", " ", ""]
        )
        texts = text_splitter.split_documents(processed_documents)

        embeddings = OpenAIEmbeddings(openai_api_key=api_key)
        vectorstore = FAISS.from_documents(texts, embeddings)
        vectorstore.save_local(FAISS_INDEX_PATH)
        return vectorstore

def setup_qa_chain(vectorstore):
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None
    
    llm = ChatOpenAI(temperature=0.3, model="gpt-4", openai_api_key=api_key)

    prompt_template = """You are an expert in Pakistan Customs Tariff (PCT) classification.

REQUIREMENTS:
1. Use FULL 8-digit HS codes (e.g., 0808.1000, NOT 0808.10)
2. MUST include Customs Duty (CD) percentage
3. Extract: PCT CODE | DESCRIPTION | CD (%)

OUTPUT FORMAT:
HS/PCT Code: [FULL 8-digit code]
Description: [complete description]
Customs Duty (CD): [percentage]%

Context: {context}
Question: {question}

Answer:"""

    prompt = ChatPromptTemplate.from_template(prompt_template)
    retriever = vectorstore.as_retriever(search_kwargs={"k": 8})
    
    def format_docs(docs):
        return "\n\n".join(doc.page_content for doc in docs)
    
    rag_chain = (
        {"context": retriever | format_docs, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )
    
    return rag_chain

def normalize_hs_code(code):
    """Normalize HS code to full 8-digit format"""
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

# Streamlit App
st.set_page_config(
    page_title="HS Code System & WEBOC Calculator",
    page_icon="📋",
    layout="wide"
)

st.title("📋 HS Code Classification & WEBOC Duty Calculator")

# Initialize session state
if 'weboc_scraper' not in st.session_state:
    st.session_state.weboc_scraper = WEBOCTariffScraper()

if 'last_search_result' not in st.session_state:
    st.session_state.last_search_result = None

# Sidebar
with st.sidebar:
    st.header("⚙️ Settings")
    
    custom_weboc_url = st.text_input(
        "Custom WEBOC URL",
        placeholder="https://www.weboc.gov.pk/(S(...))/Shared/TariffList.aspx",
        help="Paste WEBOC URL with session token if needed"
    )
    
    if custom_weboc_url:
        st.session_state.weboc_scraper = WEBOCTariffScraper(custom_weboc_url)
    
    st.markdown("---")
    
    if st.button("🔄 Rebuild Vectorstore", use_container_width=True):
        with st.spinner("Rebuilding..."):
            if os.path.exists(FAISS_INDEX_PATH):
                shutil.rmtree(FAISS_INDEX_PATH)
            st.cache_resource.clear()
            st.rerun()
    
    st.markdown("---")
    st.info("📅 FY 2024-25 Tariff")
    
    # Show last search info
    if st.session_state.last_search_result:
        st.markdown("---")
        st.subheader("📌 Last Search")
        result = st.session_state.last_search_result
        st.caption(f"**Code:** {result.get('hs_code', 'N/A')}")
        if result.get('description'):
            st.caption(f"**Item:** {result['description'][:50]}...")

# Initialize vectorstore and QA chain
if 'vectorstore' not in st.session_state:
    with st.spinner("Initializing system..."):
        vectorstore = get_vectorstore()
        if vectorstore:
            qa_chain = setup_qa_chain(vectorstore)
            if qa_chain:
                st.session_state.vectorstore = vectorstore
                st.session_state.qa_chain = qa_chain

# Tabs
tab1, tab2 = st.tabs(["🔍 HS Code Lookup", "🧮 WEBOC Duty Calculator"])

with tab1:
    st.header("🔍 HS Code Lookup & Classification")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        hs_input = st.text_input(
            "Enter HS Code or Item Description",
            placeholder="e.g., 0808.1000 or 'fresh apples'",
            key="hs_lookup"
        )
    with col2:
        st.write("")
        st.write("")
        search_btn = st.button("🔍 Search", use_container_width=True, type="primary")
    
    # Examples
    ex_col1, ex_col2, ex_col3 = st.columns(3)
    with ex_col1:
        if st.button("🍎 Apples (0808.10)", use_container_width=True):
            hs_input = "0808.10"
            search_btn = True
    with ex_col2:
        if st.button("🐴 Horses (0101.21)", use_container_width=True):
            hs_input = "0101.21"
            search_btn = True
    with ex_col3:
        if st.button("👕 T-shirts (6109.10)", use_container_width=True):
            hs_input = "6109.10"
            search_btn = True
    
    if search_btn and hs_input:
        if 'qa_chain' not in st.session_state:
            st.error("System not initialized. Please refresh the page.")
        else:
            with st.spinner("🔍 Searching..."):
                # Check if input looks like HS code or description
                if re.match(r'^\d{2,4}\.?\d{0,4}$', hs_input.replace('.', '')):
                    # HS code lookup
                    normalized = normalize_hs_code(hs_input)
                    query = f"What is the classification, description, and Customs Duty for HS code {normalized}?"
                else:
                    # Item classification
                    query = f"Classify '{hs_input}' to HS code with description and Customs Duty"
                
                result = st.session_state.qa_chain.invoke(query)
                
                # Also fetch WEBOC data
                if re.match(r'^\d{2,4}\.?\d{0,4}$', hs_input.replace('.', '')):
                    weboc_data = st.session_state.weboc_scraper.search_hs_code(hs_input)
                    st.session_state.last_search_result = weboc_data
                
                st.markdown("---")
                st.subheader("📋 Results")
                st.markdown(result)
                
                # Show quick action button to use in calculator
                if st.session_state.last_search_result and st.session_state.last_search_result.get('status') == 'success':
                    if st.button("➡️ Use in Duty Calculator", type="secondary"):
                        st.session_state.selected_tab = 1
                        st.rerun()

with tab2:
    st.header("🧮 WEBOC-Style Duty Calculator")
    st.caption("Calculate duties and taxes like WEBOC Item General Duty Calculator")
    
    # Check if we have data from Tab 1
    if st.session_state.last_search_result and st.session_state.last_search_result.get('status') == 'success':
        last_result = st.session_state.last_search_result
        # Safe description extraction with fallback
        description = last_result.get('description') or 'N/A'
        description_display = description[:100] if description != 'N/A' else 'N/A'
        st.info(f"💡 Using data from search: **{last_result.get('hs_code')}** - {description_display}...")
        
        # Pre-fill button
        col_prefill1, col_prefill2 = st.columns([1, 3])
        with col_prefill1:
            if st.button("📋 Pre-fill Calculator", use_container_width=True):
                st.session_state.prefill_data = last_result
                st.rerun()
        with col_prefill2:
            if st.button("🔄 Clear Pre-fill", use_container_width=True):
                if 'prefill_data' in st.session_state:
                    del st.session_state.prefill_data
                st.rerun()
    
    # Get pre-filled data if available
    prefill = st.session_state.get('prefill_data', {})
    
    # Input Section
    st.subheader("📦 Item Details")
    col1, col2 = st.columns(2)
    
    with col1:
        calc_hs_code = st.text_input(
            "HS Code",
            value=prefill.get('hs_code', ''),
            placeholder="e.g., 0808.1000",
            key="calc_hs"
        )
        calc_quantity = st.number_input(
            "Quantity",
            min_value=0.0,
            step=1.0,
            value=1.0,
            key="calc_qty"
        )
        
        # Smart unit selection based on WEBOC data
        default_unit = prefill.get('unit_of_measure', 'kg')
        unit_options = ["kg", "units", "liters", "tonnes", "meters", "pairs", "dozens", "sets"]
        
        # Ensure default unit is in options
        if default_unit not in unit_options:
            unit_options.insert(0, default_unit)
        
        default_index = unit_options.index(default_unit) if default_unit in unit_options else 0
        
        calc_unit = st.selectbox(
            "Unit of Measurement",
            unit_options,
            index=default_index,
            help=f"Auto-detected: {default_unit}" if prefill.get('unit_of_measure') else "Select unit",
            key="calc_unit"
        )
    
    with col2:
        calc_currency = st.selectbox(
            "Currency",
            ["USD", "PKR", "EUR", "GBP", "AED"],
            key="calc_curr"
        )
        calc_value = st.number_input(
            "Value per Unit",
            min_value=0.0,
            step=0.01,
            key="calc_val"
        )
        manual_rate = st.number_input(
            "Override Exchange Rate (optional)",
            min_value=0.0,
            step=0.01,
            value=0.0,
            help="Leave 0 to use automatic NBP rate",
            key="calc_rate"
        )
    
    # Show description if available
    if prefill.get('description'):
        st.info(f"**Item Description:** {prefill['description']}")
    
    st.subheader("🚢 CIF Components")
    cif_col1, cif_col2, cif_col3 = st.columns(3)
    
    with cif_col1:
        freight = st.number_input(
            "Freight",
            min_value=0.0,
            step=0.01,
            value=0.0,
            key="calc_freight"
        )
    with cif_col2:
        insurance = st.number_input(
            "Insurance",
            min_value=0.0,
            step=0.01,
            value=0.0,
            key="calc_insurance"
        )
    with cif_col3:
        other_charges = st.number_input(
            "Other Charges",
            min_value=0.0,
            step=0.01,
            value=0.0,
            key="calc_other"
        )
    
    st.markdown("---")
    
    if st.button("💰 Calculate Duties & Taxes", type="primary", use_container_width=True):
        if not calc_hs_code or calc_quantity <= 0 or calc_value <= 0:
            st.error("Please provide valid HS code, quantity, and value")
        else:
            with st.spinner("📊 Calculating..."):
                # Fetch duty rates from WEBOC
                duty_data = st.session_state.weboc_scraper.search_hs_code(calc_hs_code)
                
                if duty_data.get('status') == 'success':
                    # Get exchange rate
                    if manual_rate > 0:
                        exchange_rate = manual_rate
                        rate_source = "Manual Override"
                    else:
                        exchange_rate, rate_source = get_exchange_rate(calc_currency)
                    
                    # Calculate CIF value in foreign currency
                    fob_value = calc_value * calc_quantity
                    cif_value_foreign = fob_value + freight + insurance + other_charges
                    
                    # Convert to PKR
                    cif_value_pkr = cif_value_foreign * exchange_rate
                    
                    # Extract duty rates
                    cd_rate = duty_data.get('customs_duty', 0) or 0
                    st_rate = duty_data.get('sales_tax', 0) or 0
                    it_rate = duty_data.get('income_tax', 0) or 0
                    ad_rate = duty_data.get('additional_duty', 0) or 0
                    rd_rate = duty_data.get('regulatory_duty', 0) or 0
                    
                    # WEBOC-style calculation
                    customs_duty = cif_value_pkr * (cd_rate / 100)
                    additional_duty = cif_value_pkr * (ad_rate / 100)
                    regulatory_duty = cif_value_pkr * (rd_rate / 100)
                    sales_tax_base = cif_value_pkr + customs_duty + additional_duty + regulatory_duty
                    sales_tax = sales_tax_base * (st_rate / 100)
                    income_tax = cif_value_pkr * (it_rate / 100)
                    
                    # Total
                    total_duties = customs_duty + additional_duty + regulatory_duty + sales_tax + income_tax
                    total_landed_cost = cif_value_pkr + total_duties
                    
                    # Display Results
                    st.success("✅ Calculation Complete")
                    
                    # Summary metrics
                    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
                    with metric_col1:
                        st.metric("CIF Value (PKR)", f"{cif_value_pkr:,.2f}")
                    with metric_col2:
                        st.metric("Total Duties", f"{total_duties:,.2f}")
                    with metric_col3:
                        st.metric("Landed Cost", f"{total_landed_cost:,.2f}")
                    with metric_col4:
                        st.metric("Exchange Rate", f"{exchange_rate:.4f}")
                    
                    st.markdown("---")
                    
                    # Detailed breakdown
                    st.subheader("📊 Detailed Breakdown")
                    
                    breakdown_data = {
                        "Component": [
                            "FOB Value",
                            "Freight",
                            "Insurance",
                            "Other Charges",
                            "**CIF Value (Foreign)**",
                            "**CIF Value (PKR)**",
                            "",
                            f"Customs Duty ({cd_rate}%)",
                        ],
                        "Amount": [
                            f"{fob_value:,.2f} {calc_currency}",
                            f"{freight:,.2f} {calc_currency}",
                            f"{insurance:,.2f} {calc_currency}",
                            f"{other_charges:,.2f} {calc_currency}",
                            f"**{cif_value_foreign:,.2f} {calc_currency}**",
                            f"**{cif_value_pkr:,.2f} PKR**",
                            "",
                            f"{customs_duty:,.2f} PKR",
                        ]
                    }
                    
                    if ad_rate > 0:
                        breakdown_data["Component"].append(f"Additional Duty ({ad_rate}%)")
                        breakdown_data["Amount"].append(f"{additional_duty:,.2f} PKR")
                    
                    if rd_rate > 0:
                        breakdown_data["Component"].append(f"Regulatory Duty ({rd_rate}%)")
                        breakdown_data["Amount"].append(f"{regulatory_duty:,.2f} PKR")
                    
                    breakdown_data["Component"].extend([
                        f"Sales Tax ({st_rate}%)",
                        f"Income Tax ({it_rate}%)",
                        "",
                        "**Total Duties & Taxes**",
                        "**Total Landed Cost**"
                    ])
                    breakdown_data["Amount"].extend([
                        f"{sales_tax:,.2f} PKR",
                        f"{income_tax:,.2f} PKR",
                        "",
                        f"**{total_duties:,.2f} PKR**",
                        f"**{total_landed_cost:,.2f} PKR**"
                    ])
                    
                    import pandas as pd
                    df = pd.DataFrame(breakdown_data)
                    st.table(df)
                    
                    st.caption(f"📍 Exchange Rate Source: {rate_source}")
                    st.caption(f"📦 HS Code: {calc_hs_code} | Unit: {calc_unit}")
                    if duty_data.get('description'):
                        st.caption(f"📝 Description: {duty_data['description']}")
                    
                else:
                    st.error(f"❌ Failed to fetch duty rates: {duty_data.get('error', 'Unknown error')}")
                    st.info("""
                    **Troubleshooting:**
                    - Verify the HS code is valid
                    - Try using a custom WEBOC URL in the sidebar
                    - Check if WEBOC website is accessible
                    """)

st.markdown("---")
st.caption("💡 Data sources: Pakistan Customs Tariff FY 2024-25 | WEBOC | NBP/SBP Exchange Rates")