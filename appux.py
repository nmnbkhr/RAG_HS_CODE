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
    """Enhanced scraper for WEBOC duty data with UOM extraction and HS code list fetching"""
    
    def __init__(self, base_url: str = None):
        self.base_url = base_url or WEBOC_TARIFF_URL
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.last_error = None
        self.hs_code_cache = None
    
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
    
    def fetch_hs_code_list(self, search_prefix: str = "") -> list:
        """Fetch list of HS codes from WEBOC"""
        try:
            response = self.session.get(self.base_url, timeout=15, allow_redirects=True)
            if response.status_code != 200:
                return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            hs_codes = []
            
            # Find select/dropdown with HS codes
            select_elements = soup.find_all('select')
            for select in select_elements:
                options = select.find_all('option')
                for option in options:
                    code = option.get('value', '').strip()
                    text = option.get_text(strip=True)
                    if code and re.match(r'\d{4}\.\d{4}', code):
                        hs_codes.append({
                            'code': code,
                            'description': text,
                            'unit': self.extract_unit_of_measure(text)
                        })
            
            # Find table with HS codes
            if not hs_codes:
                tables = soup.find_all('table')
                for table in tables:
                    rows = table.find_all('tr')
                    for row in rows:
                        cells = row.find_all(['td', 'th'])
                        if len(cells) >= 2:
                            code_text = cells[0].get_text(strip=True)
                            desc_text = cells[1].get_text(strip=True) if len(cells) > 1 else ''
                            if re.match(r'\d{4}\.\d{4}', code_text):
                                hs_codes.append({
                                    'code': code_text,
                                    'description': desc_text,
                                    'unit': self.extract_unit_of_measure(desc_text)
                                })
            
            if search_prefix:
                search_prefix = search_prefix.replace('.', '')
                hs_codes = [
                    item for item in hs_codes 
                    if item['code'].replace('.', '').startswith(search_prefix)
                ]
            
            seen = set()
            unique_codes = []
            for item in hs_codes:
                if item['code'] not in seen:
                    seen.add(item['code'])
                    unique_codes.append(item)
            
            return unique_codes[:1000]
            
        except Exception as e:
            return []
    
    def search_hs_codes_autocomplete(self, query: str, limit: int = 50) -> list:
        """Search HS codes with autocomplete functionality"""
        if self.hs_code_cache:
            query_clean = query.replace('.', '').lower()
            results = []
            for item in self.hs_code_cache:
                code_clean = item['code'].replace('.', '')
                desc_clean = item['description'].lower()
                if query_clean in code_clean or query_clean in desc_clean:
                    results.append(item)
                    if len(results) >= limit:
                        break
            return results
        
        return self.fetch_hs_code_list(query)[:limit]
    
    def extract_unit_of_measure(self, text: str) -> str:
        """Extract unit of measure from description"""
        uom_patterns = {
            r'\bkg\b|\bkilogram|\bkgs\b': 'kg',
            r'\blitre|\bliter|\blitres|\bliters': 'liters',
            r'\btonne|\bton\b|\btonnes|\btons\b|\bmt\b': 'tonnes',
            r'\bunit|\bunits|\bpiece|\bpieces|\bpcs\b|\bno\b|\bnos\b': 'units',
            r'\bmetre|\bmeter|\bmetres|\bmeters|\bmtr\b': 'meters',
            r'\bpair|\bpairs|\bprs\b': 'pairs',
            r'\bdozen|\bdozens|\bdoz\b': 'dozens',
            r'\bset|\bsets': 'sets',
            r'\bsqm|\bsq\.m|\bsquare meter': 'sqm',
            r'\bcum|\bcu\.m|\bcubic meter': 'cum'
        }
        
        text_lower = text.lower()
        for pattern, uom in uom_patterns.items():
            if re.search(pattern, text_lower):
                return uom
        
        return 'units'
    
    def search_hs_code(self, hs_code: str) -> dict:
        """Search for HS code and extract duty rates, description, and UOM"""
        normalized_code = self.normalize_hs_code(hs_code)
        
        try:
            response = self.session.get(self.base_url, timeout=15, allow_redirects=True)
            if response.status_code != 200:
                return self._error_result(normalized_code, f"HTTP {response.status_code}")
            
            actual_url = response.url
            form_data = self.get_form_data(response.text)
            
            if not form_data.get('__VIEWSTATE'):
                return self._error_result(normalized_code, "Session expired")
            
            soup = BeautifulSoup(response.text, 'html.parser')
            search_box = soup.find('input', {'id': re.compile('txtSearch', re.I)})
            search_button = soup.find('input', {'id': re.compile('btnSearch', re.I)})
            
            if not search_box:
                return self._error_result(normalized_code, "Search controls not found")
            
            search_box_name = search_box.get('name', 'TariffList$txtSearch')
            search_button_name = search_button.get('name', 'TariffList$btnSearch') if search_button else 'TariffList$btnSearch'
            
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
                return self._error_result(normalized_code, f"Search failed")
            
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
        
        desc_selectors = [
            {'id': re.compile('lblDescription|Description', re.I)},
            {'class': re.compile('description', re.I)}
        ]
        
        for selector in desc_selectors:
            desc_element = soup.find('span', selector) or soup.find('div', selector)
            if desc_element:
                result['description'] = desc_element.get_text(strip=True)
                result['unit_of_measure'] = self.extract_unit_of_measure(result['description'])
                break
        
        rows = duty_table.find_all('tr')
        full_table_text = duty_table.get_text()
        
        for row in rows:
            cells = row.find_all(['td', 'th'])
            if len(cells) < 1:
                continue
            
            cell_texts = [cell.get_text(strip=True) for cell in cells]
            row_text = ' '.join(cell_texts)
            
            if 'unit' in row_text.lower() or 'uom' in row_text.lower():
                uom = self.extract_unit_of_measure(row_text)
                if uom != 'units':
                    result['unit_of_measure'] = uom
            
            rate_matches = re.findall(r'(\d+(?:\.\d+)?)\s*%', row_text)
            if not rate_matches:
                rate_matches = re.findall(r'@?\s*(\d+(?:\.\d+)?)', row_text)
            
            if not rate_matches:
                continue
            
            rate_value = float(rate_matches[0])
            row_lower = row_text.lower()
            
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
        
        if result['unit_of_measure'] == 'units':
            result['unit_of_measure'] = self.extract_unit_of_measure(full_table_text)
        
        if any([result['customs_duty'], result['sales_tax'], result['income_tax']]):
            return result
        return None

# Exchange rate functions
def fetch_usd_rate_from_nbp():
    """Scrape USD->PKR rate from NBP"""
    try:
        response = requests.get(NBP_USD_RATE_URL, timeout=10)
        if response.status_code == 200:
            text = response.text
            patterns = [
                r'USD[^\d]*(\d{3}\.\d{2,4})',
                r'US\s*Dollar[^\d]*(\d{3}\.\d{2,4})',
                r'Dollar.*?TT.*?Selling[^\d]*(\d{3}\.\d{2,4})',
                r'US\s*D(?:ollar)?[^0-9]{0,30}([0-9]{2,3}\.\d{2,4})',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    rate = float(match.group(1))
                    if 200 < rate < 400:
                        return rate
        
        try:
            sbp_response = requests.get("https://www.sbp.org.pk/ecodata/rates/m2m/m2m-current.asp", timeout=10)
            if sbp_response.status_code == 200:
                match = re.search(r'USD[^\d]*(\d{3}\.\d{2,4})', sbp_response.text)
                if match:
                    rate = float(match.group(1))
                    if 200 < rate < 400:
                        return rate
        except:
            pass
            
    except:
        pass
    
    return 280.50

def get_exchange_rate(from_currency):
    """Get PKR conversion rate"""
    currency = from_currency.upper()
    
    if currency == "PKR":
        return 1.0, "PKR (no conversion)"
    
    if currency == "USD":
        nbp_rate = fetch_usd_rate_from_nbp()
        if nbp_rate and nbp_rate > 200:
            return nbp_rate, "NBP/SBP Official Rate"
        return 280.50, "Estimated Rate"
    
    try:
        response = requests.get(f"https://api.exchangerate-api.com/v4/latest/{currency}", timeout=10)
        if response.status_code == 200:
            rates = response.json().get("rates", {})
            pkr_rate = rates.get("PKR")
            if pkr_rate:
                return pkr_rate, f"Market Rate"
    except:
        pass
    
    return 1.0, "Default"

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
1. Use FULL 8-digit HS codes (e.g., 0808.1000)
2. Include Customs Duty (CD) percentage
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

# Streamlit App Configuration
st.set_page_config(
    page_title="Pakistan Customs - HS Code & Duty Calculator",
    page_icon="🇵🇰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for production-level UI
st.markdown("""
<style>
    /* Main container */
    .main {
        padding: 1rem 2rem;
    }
    
    /* Header styling */
    .main-header {
        background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%);
        padding: 2rem;
        border-radius: 10px;
        color: white;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    /* Card styling */
    .info-card {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    
    /* Button styling */
    .stButton>button {
        border-radius: 6px;
        font-weight: 600;
        transition: all 0.3s ease;
        border: none;
    }
    
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    
    /* Metric styling */
    [data-testid="stMetricValue"] {
        font-size: 2rem;
        font-weight: 700;
    }
    
    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 2rem;
        background-color: #f9fafb;
        padding: 0.5rem;
        border-radius: 8px;
    }
    
    .stTabs [data-baseweb="tab"] {
        padding: 1rem 2rem;
        border-radius: 6px;
        font-weight: 600;
    }
    
    /* Input styling */
    .stTextInput>div>div>input, .stNumberInput>div>div>input, .stSelectbox>div>div>select {
        border-radius: 6px;
        border: 2px solid #e5e7eb;
        padding: 0.75rem;
    }
    
    .stTextInput>div>div>input:focus, .stNumberInput>div>div>input:focus, .stSelectbox>div>div>select:focus {
        border-color: #3b82f6;
        box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
    }
    
    /* Alert styling */
    .stAlert {
        border-radius: 8px;
        border-left: 4px solid;
        padding: 1rem 1.5rem;
    }
    
    /* Sidebar styling */
    .css-1d391kg {
        background-color: #f9fafb;
    }
    
    /* Success box */
    .success-box {
        background: #d1fae5;
        border-left: 4px solid #10b981;
        padding: 1rem;
        border-radius: 6px;
        margin: 1rem 0;
    }
    
    /* Info box */
    .info-box {
        background: #dbeafe;
        border-left: 4px solid #3b82f6;
        padding: 1rem;
        border-radius: 6px;
        margin: 1rem 0;
    }
    
    /* Section headers */
    .section-header {
        font-size: 1.25rem;
        font-weight: 700;
        color: #1f2937;
        margin: 1.5rem 0 1rem 0;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid #e5e7eb;
    }
    
    /* Result table */
    .stDataFrame {
        border-radius: 8px;
        overflow: hidden;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Responsive design */
    @media (max-width: 768px) {
        .main-header {
            padding: 1rem;
        }
        .stTabs [data-baseweb="tab"] {
            padding: 0.5rem 1rem;
        }
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'weboc_scraper' not in st.session_state:
    st.session_state.weboc_scraper = WEBOCTariffScraper()

if 'last_search_result' not in st.session_state:
    st.session_state.last_search_result = None

if 'hs_code_options' not in st.session_state:
    st.session_state.hs_code_options = []

if 'selected_hs_info' not in st.session_state:
    st.session_state.selected_hs_info = None

# Header
st.markdown("""
<div class="main-header">
    <h1 style="margin:0; font-size: 2.5rem;">🇵🇰 Pakistan Customs System</h1>
    <p style="margin:0.5rem 0 0 0; font-size: 1.1rem; opacity: 0.9;">HS Code Classification & WEBOC Duty Calculator</p>
</div>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.markdown("### ⚙️ System Settings")
    
    with st.expander("🔧 Advanced Settings", expanded=False):
        custom_weboc_url = st.text_input(
            "Custom WEBOC URL",
            placeholder="https://www.weboc.gov.pk/(S(...))/...",
            help="Paste WEBOC URL with session token if needed"
        )
        
        if custom_weboc_url and st.button("Apply URL", use_container_width=True):
            st.session_state.weboc_scraper = WEBOCTariffScraper(custom_weboc_url)
            st.success("✅ URL updated!")
        
        if st.button("🔄 Rebuild Vectorstore", use_container_width=True):
            with st.spinner("Rebuilding..."):
                if os.path.exists(FAISS_INDEX_PATH):
                    shutil.rmtree(FAISS_INDEX_PATH)
                st.cache_resource.clear()
                st.rerun()
    
    st.markdown("---")
    
    # System Status
    st.markdown("### 📊 System Status")
    
    status_col1, status_col2 = st.columns(2)
    with status_col1:
        if os.path.exists(FAISS_INDEX_PATH):
            st.success("✅ Online")
        else:
            st.error("❌ Offline")
        st.caption("Vectorstore")
    
    with status_col2:
        st.info("📅 FY 24-25")
        st.caption("Tariff Year")
    
    # Last search info
    if st.session_state.last_search_result:
        st.markdown("---")
        st.markdown("### 📌 Recent Search")
        result = st.session_state.last_search_result
        st.code(f"{result.get('hs_code', 'N/A')}", language="")
        description = result.get('description')
        if description and description != 'N/A':
            desc_preview = description[:40] if len(description) > 40 else description
            st.caption(desc_preview + "...")
    
    st.markdown("---")
    st.markdown("### 📚 Resources")
    st.markdown("""
    - [FBR Official](https://fbr.gov.pk)
    - [WEBOC Portal](https://weboc.gov.pk)
    - [NBP Exchange Rates](https://nbp.com.pk)
    """)

# Initialize vectorstore and QA chain
if 'vectorstore' not in st.session_state:
    with st.spinner("🔄 Initializing AI system..."):
        vectorstore = get_vectorstore()
        if vectorstore:
            qa_chain = setup_qa_chain(vectorstore)
            if qa_chain:
                st.session_state.vectorstore = vectorstore
                st.session_state.qa_chain = qa_chain

# Tabs
tab1, tab2 = st.tabs(["🔍 HS Code Lookup", "🧮 Duty Calculator"])

with tab1:
    st.markdown('<div class="section-header">HS Code Lookup & Classification</div>', unsafe_allow_html=True)
    st.caption("Search and classify items using Pakistan Customs Tariff FY 2024-25")
    
    # Search interface
    col1, col2 = st.columns([4, 1])
    with col1:
        hs_input = st.text_input(
            "Search HS Code or Item Description",
            placeholder="Enter HS code (e.g., 0808.1000) or item name (e.g., 'fresh apples')",
            key="hs_lookup",
            label_visibility="collapsed"
        )
    with col2:
        st.write("")
        search_btn = st.button("🔍 Search", use_container_width=True, type="primary")
    
    # Quick examples
    st.markdown("**Quick Examples:**")
    ex_cols = st.columns(4)
    examples = [
        ("🍎 Fresh Apples", "0808.10"),
        ("🐴 Live Horses", "0101.21"),
        ("👕 Cotton T-shirts", "6109.10"),
        ("📱 Mobile Phones", "8517.12")
    ]
    
    for idx, (label, code) in enumerate(examples):
        with ex_cols[idx]:
            if st.button(label, use_container_width=True, key=f"ex_{idx}"):
                hs_input = code
                search_btn = True
    
    if search_btn and hs_input:
        if 'qa_chain' not in st.session_state:
            st.error("⚠️ System not initialized. Please refresh the page.")
        else:
            with st.spinner("🔍 Searching Pakistan Customs Tariff..."):
                # Determine search type
                if re.match(r'^\d{2,4}\.?\d{0,4}$', hs_input.replace('.', '')):
                    normalized = normalize_hs_code(hs_input)
                    query = f"What is the classification, description, and Customs Duty for HS code {normalized}?"
                else:
                    query = f"Classify '{hs_input}' to HS code with description and Customs Duty"
                
                result = st.session_state.qa_chain.invoke(query)
                
                # Fetch WEBOC data if HS code
                if re.match(r'^\d{2,4}\.?\d{0,4}$', hs_input.replace('.', '')):
                    weboc_data = st.session_state.weboc_scraper.search_hs_code(hs_input)
                    st.session_state.last_search_result = weboc_data
                
                st.markdown("---")
                
                # Display results
                st.markdown('<div class="success-box">', unsafe_allow_html=True)
                st.markdown("**✅ Search Results**")
                st.markdown(result)
                st.markdown('</div>', unsafe_allow_html=True)
                
                # Show action button
                if st.session_state.last_search_result and st.session_state.last_search_result.get('status') == 'success':
                    if st.button("➡️ Use in Duty Calculator", type="secondary", use_container_width=True):
                        st.session_state.prefill_data = st.session_state.last_search_result
                        st.info("✅ Data saved! Switch to Duty Calculator tab.")

with tab2:
    st.markdown('<div class="section-header">WEBOC Duty Calculator</div>', unsafe_allow_html=True)
    st.caption("Calculate customs duties and taxes based on WEBOC rates")
    
    # Pre-fill notification
    if st.session_state.last_search_result and st.session_state.last_search_result.get('status') == 'success':
        last_result = st.session_state.last_search_result
        description = last_result.get('description') or 'N/A'
        description_display = description[:80] if description != 'N/A' else 'N/A'
        
        st.markdown('<div class="info-box">', unsafe_allow_html=True)
        st.markdown(f"**💡 Data Available:** {last_result.get('hs_code')} - {description_display}...")
        
        prefill_cols = st.columns([1, 1, 2])
        with prefill_cols[0]:
            if st.button("📋 Pre-fill Data", use_container_width=True):
                st.session_state.prefill_data = last_result
                st.rerun()
        with prefill_cols[1]:
            if st.button("🔄 Clear", use_container_width=True):
                if 'prefill_data' in st.session_state:
                    del st.session_state.prefill_data
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    
    prefill = st.session_state.get('prefill_data', {})
    
    # HS Code Selection
    st.markdown('<div class="section-header">1️⃣ Select HS Code</div>', unsafe_allow_html=True)
    
    input_method = st.radio(
        "Input Method",
        ["🔢 Manual Entry", "📋 Search Database"],
        horizontal=True,
        key="hs_input_method",
        label_visibility="collapsed"
    )
    
    calc_hs_code = ""
    auto_detected_unit = "kg"
    auto_detected_description = ""
    
    if input_method == "🔢 Manual Entry":
        man_col1, man_col2 = st.columns([3, 1])
        with man_col1:
            calc_hs_code = st.text_input(
                "HS Code",
                value=prefill.get('hs_code', ''),
                placeholder="e.g., 0808.1000",
                key="calc_hs_manual",
                label_visibility="collapsed"
            )
        with man_col2:
            if calc_hs_code and st.button("🔍 Fetch", use_container_width=True):
                with st.spinner("Fetching..."):
                    weboc_data = st.session_state.weboc_scraper.search_hs_code(calc_hs_code)
                    if weboc_data.get('status') == 'success':
                        st.session_state.selected_hs_info = weboc_data
                        st.success("✅ Loaded!")
                        st.rerun()
                    else:
                        st.error("❌ Not found in WEBOC")
    
    else:  # Search Database
        search_col1, search_col2 = st.columns([4, 1])
        with search_col1:
            search_query = st.text_input(
                "Search",
                placeholder="Enter HS code or description (e.g., '0808' or 'apples')",
                key="hs_search_query",
                label_visibility="collapsed"
            )
        with search_col2:
            search_btn = st.button("🔍 Search", use_container_width=True, type="secondary")
        
        if search_btn and search_query:
            with st.spinner("Searching WEBOC..."):
                results = st.session_state.weboc_scraper.search_hs_codes_autocomplete(search_query, limit=100)
                st.session_state.hs_code_options = results
        
        if st.session_state.hs_code_options:
            st.success(f"✅ Found {len(st.session_state.hs_code_options)} results")
            
            options_display = [
                f"{item['code']} - {item['description'][:70]}... [{item['unit']}]"
                for item in st.session_state.hs_code_options
            ]
            
            selected_option = st.selectbox(
                "Select HS Code",
                range(len(options_display)),
                format_func=lambda x: options_display[x],
                key="hs_code_selector",
                label_visibility="collapsed"
            )
            
            if selected_option is not None:
                selected_item = st.session_state.hs_code_options[selected_option]
                calc_hs_code = selected_item['code']
                auto_detected_unit = selected_item['unit']
                auto_detected_description = selected_item['description']
                
                if st.button("✅ Confirm Selection", use_container_width=True, type="primary"):
                    with st.spinner("Loading details..."):
                        weboc_data = st.session_state.weboc_scraper.search_hs_code(calc_hs_code)
                        if weboc_data.get('status') == 'success':
                            st.session_state.selected_hs_info = weboc_data
                            st.success(f"✅ {calc_hs_code} selected")
                            st.rerun()
        else:
            st.info("💡 Enter search term to browse HS codes")
    
    # Selected HS Info Display
    if st.session_state.selected_hs_info:
        info = st.session_state.selected_hs_info
        if info.get('status') == 'success':
            calc_hs_code = info.get('hs_code', calc_hs_code)
            auto_detected_unit = info.get('unit_of_measure', auto_detected_unit)
            auto_detected_description = info.get('description', auto_detected_description)
            
            st.markdown('<div class="success-box">', unsafe_allow_html=True)
            st.markdown(f"**✅ Selected HS Code:** `{calc_hs_code}`")
            if auto_detected_description and auto_detected_description != 'N/A':
                st.markdown(f"**Description:** {auto_detected_description}")
            
            duty_cols = st.columns(4)
            metrics_data = [
                ("CD", info.get('customs_duty', 0)),
                ("ST", info.get('sales_tax', 0)),
                ("IT", info.get('income_tax', 0)),
                ("Unit", auto_detected_unit)
            ]
            
            for idx, (label, value) in enumerate(metrics_data):
                with duty_cols[idx]:
                    if label != "Unit":
                        st.metric(label, f"{value}%" if value else "N/A")
                    else:
                        st.metric(label, value)
            st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Calculation Inputs
    st.markdown('<div class="section-header">2️⃣ Enter Values</div>', unsafe_allow_html=True)
    
    val_col1, val_col2 = st.columns(2)
    
    with val_col1:
        calc_quantity = st.number_input(
            "Quantity",
            min_value=0.0,
            step=1.0,
            value=1.0,
            key="calc_qty"
        )
        
        if st.session_state.selected_hs_info:
            default_unit = st.session_state.selected_hs_info.get('unit_of_measure', 'kg')
        elif auto_detected_unit:
            default_unit = auto_detected_unit
        else:
            default_unit = prefill.get('unit_of_measure', 'kg')
        
        unit_options = ["kg", "units", "liters", "tonnes", "meters", "pairs", "dozens", "sets", "sqm", "cum"]
        
        if default_unit not in unit_options:
            unit_options.insert(0, default_unit)
        
        default_index = unit_options.index(default_unit) if default_unit in unit_options else 0
        
        calc_unit = st.selectbox(
            f"Unit ({default_unit} detected)",
            unit_options,
            index=default_index,
            key="calc_unit"
        )
    
    with val_col2:
        calc_currency = st.selectbox(
            "Currency",
            ["USD", "PKR", "EUR", "GBP", "AED", "SAR", "CNY"],
            key="calc_curr"
        )
        
        calc_value = st.number_input(
            f"Value per {calc_unit}",
            min_value=0.0,
            step=0.01,
            key="calc_val"
        )
        
        manual_rate = st.number_input(
            "Custom Exchange Rate (optional)",
            min_value=0.0,
            step=0.01,
            value=0.0,
            help="Leave 0 for auto NBP rate",
            key="calc_rate"
        )
    
    st.markdown('<div class="section-header">3️⃣ CIF Components</div>', unsafe_allow_html=True)
    
    cif_cols = st.columns(3)
    with cif_cols[0]:
        freight = st.number_input("Freight", min_value=0.0, step=0.01, value=0.0, key="calc_freight")
    with cif_cols[1]:
        insurance = st.number_input("Insurance", min_value=0.0, step=0.01, value=0.0, key="calc_insurance")
    with cif_cols[2]:
        other_charges = st.number_input("Other Charges", min_value=0.0, step=0.01, value=0.0, key="calc_other")
    
    st.markdown("---")
    
    # Calculate button
    if st.button("💰 Calculate Duties & Taxes", type="primary", use_container_width=True):
        if not calc_hs_code or calc_quantity <= 0 or calc_value <= 0:
            st.error("⚠️ Please provide valid HS code, quantity, and value")
        else:
            with st.spinner("📊 Calculating duties and taxes..."):
                # Use cached or fetch new
                if st.session_state.selected_hs_info and st.session_state.selected_hs_info.get('hs_code') == calc_hs_code:
                    duty_data = st.session_state.selected_hs_info
                else:
                    duty_data = st.session_state.weboc_scraper.search_hs_code(calc_hs_code)
                
                if duty_data.get('status') == 'success':
                    # Exchange rate
                    if manual_rate > 0:
                        exchange_rate = manual_rate
                        rate_source = "Custom Rate"
                    else:
                        exchange_rate, rate_source = get_exchange_rate(calc_currency)
                    
                    # Calculate values
                    fob_value = calc_value * calc_quantity
                    cif_value_foreign = fob_value + freight + insurance + other_charges
                    cif_value_pkr = cif_value_foreign * exchange_rate
                    
                    # Duty rates
                    cd_rate = duty_data.get('customs_duty', 0) or 0
                    st_rate = duty_data.get('sales_tax', 0) or 0
                    it_rate = duty_data.get('income_tax', 0) or 0
                    ad_rate = duty_data.get('additional_duty', 0) or 0
                    rd_rate = duty_data.get('regulatory_duty', 0) or 0
                    
                    # Calculate duties
                    customs_duty = cif_value_pkr * (cd_rate / 100)
                    additional_duty = cif_value_pkr * (ad_rate / 100)
                    regulatory_duty = cif_value_pkr * (rd_rate / 100)
                    sales_tax_base = cif_value_pkr + customs_duty + additional_duty + regulatory_duty
                    sales_tax = sales_tax_base * (st_rate / 100)
                    income_tax = cif_value_pkr * (it_rate / 100)
                    
                    total_duties = customs_duty + additional_duty + regulatory_duty + sales_tax + income_tax
                    total_landed_cost = cif_value_pkr + total_duties
                    
                    # Display results
                    st.markdown("---")
                    st.markdown('<div class="section-header">📊 Calculation Results</div>', unsafe_allow_html=True)
                    
                    # Key metrics
                    result_cols = st.columns(4)
                    with result_cols[0]:
                        st.metric("CIF Value", f"PKR {cif_value_pkr:,.0f}")
                    with result_cols[1]:
                        st.metric("Total Duties", f"PKR {total_duties:,.0f}")
                    with result_cols[2]:
                        st.metric("Landed Cost", f"PKR {total_landed_cost:,.0f}")
                    with result_cols[3]:
                        st.metric("FX Rate", f"{exchange_rate:.2f}")
                    
                    st.markdown("---")
                    
                    # Detailed breakdown
                    import pandas as pd
                    
                    breakdown_data = {
                        "Component": [
                            "FOB Value",
                            "Freight",
                            "Insurance",
                            "Other Charges",
                            "CIF Value (Foreign)",
                            "CIF Value (PKR)",
                            "",
                            f"Customs Duty ({cd_rate}%)",
                        ],
                        "Amount": [
                            f"{fob_value:,.2f} {calc_currency}",
                            f"{freight:,.2f} {calc_currency}",
                            f"{insurance:,.2f} {calc_currency}",
                            f"{other_charges:,.2f} {calc_currency}",
                            f"{cif_value_foreign:,.2f} {calc_currency}",
                            f"{cif_value_pkr:,.2f} PKR",
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
                        "Total Duties & Taxes",
                        "Total Landed Cost"
                    ])
                    breakdown_data["Amount"].extend([
                        f"{sales_tax:,.2f} PKR",
                        f"{income_tax:,.2f} PKR",
                        "",
                        f"{total_duties:,.2f} PKR",
                        f"{total_landed_cost:,.2f} PKR"
                    ])
                    
                    df = pd.DataFrame(breakdown_data)
                    st.dataframe(df, use_container_width=True, hide_index=True)
                    
                    # Summary info
                    st.markdown("---")
                    st.caption(f"📍 Exchange Rate: {rate_source} • HS Code: {calc_hs_code} • Unit: {calc_unit}")
                    if duty_data.get('description') and duty_data['description'] != 'N/A':
                        st.caption(f"📝 {duty_data['description']}")
                    
                else:
                    st.error("❌ Could not fetch duty rates from WEBOC")
                    st.info(f"Error: {duty_data.get('error', 'Unknown error')}")

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #6b7280; padding: 2rem 0;'>
    <p><strong>Pakistan Customs - HS Code & Duty Calculator</strong></p>
    <p>Data Sources: Pakistan Customs Tariff FY 2024-25 | WEBOC | NBP/SBP Exchange Rates</p>
    <p style='font-size: 0.875rem;'>⚠️ For official use, please verify with FBR and WEBOC</p>
</div>
""", unsafe_allow_html=True)