import streamlit as st
import requests
import re
from bs4 import BeautifulSoup
from typing import Dict, Optional
import time

class WEBOCTariffScraper:
    """Enhanced scraper with detailed debugging"""
    
    def __init__(self, base_url: str = None, debug: bool = False):
        self.base_url = base_url or "https://www.weboc.gov.pk/Shared/TariffList.aspx"
        self.debug = debug
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        self.last_error = None
    
    def log(self, message: str):
        """Debug logging"""
        if self.debug:
            print(f"[DEBUG] {message}")
    
    def normalize_hs_code(self, hs_code: str) -> str:
        """Normalize HS code to XXXX.XXXX format"""
        digits = re.sub(r'\D', '', hs_code)
        if len(digits) < 8:
            digits = digits.ljust(8, '0')
        elif len(digits) > 8:
            digits = digits[:8]
        return f"{digits[:4]}.{digits[4:]}"
    
    def extract_hidden_field(self, soup: BeautifulSoup, field_name: str) -> str:
        """Extract hidden form field value"""
        element = soup.find('input', {'name': field_name})
        if element and element.get('value'):
            return element['value']
        return ''
    
    def get_form_data(self, html: str) -> Dict[str, str]:
        """Extract all ASP.NET form data"""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Get all hidden fields
        hidden_fields = soup.find_all('input', type='hidden')
        
        data = {}
        for field in hidden_fields:
            name = field.get('name')
            value = field.get('value', '')
            if name:
                data[name] = value
        
        self.log(f"Extracted {len(data)} hidden fields")
        return data
    
    def search_hs_code(self, hs_code: str) -> Dict:
        """Search for HS code with detailed error tracking"""
        normalized_code = self.normalize_hs_code(hs_code)
        self.log(f"Normalized code: {normalized_code}")
        
        try:
            # Step 1: Initial GET request
            self.log(f"GET request to: {self.base_url}")
            response = self.session.get(self.base_url, timeout=15, allow_redirects=True)
            
            self.log(f"Response status: {response.status_code}")
            self.log(f"Response URL: {response.url}")
            
            if response.status_code != 200:
                self.last_error = f"HTTP {response.status_code} on initial request"
                return self._error_result(normalized_code, self.last_error)
            
            # Save the actual URL (in case of redirects)
            actual_url = response.url
            
            # Step 2: Extract form data
            form_data = self.get_form_data(response.text)
            
            if not form_data.get('__VIEWSTATE'):
                # Try to find the form manually
                soup = BeautifulSoup(response.text, 'html.parser')
                form = soup.find('form')
                
                if form:
                    self.log("Form found, but no __VIEWSTATE")
                else:
                    self.log("No form found on page")
                
                self.last_error = "Could not find __VIEWSTATE (page structure changed or session expired)"
                return self._error_result(normalized_code, self.last_error)
            
            self.log(f"ViewState length: {len(form_data.get('__VIEWSTATE', ''))}")
            
            # Step 3: Prepare POST payload
            # Find the correct control names
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for search textbox
            search_box = soup.find('input', {'id': re.compile('txtSearch', re.I)})
            search_button = soup.find('input', {'id': re.compile('btnSearch', re.I)})
            
            if not search_box:
                self.last_error = "Search textbox not found on page"
                return self._error_result(normalized_code, self.last_error)
            
            search_box_name = search_box.get('name', 'TariffList$txtSearch')
            search_button_name = search_button.get('name', 'TariffList$btnSearch') if search_button else 'TariffList$btnSearch'
            
            self.log(f"Search box name: {search_box_name}")
            self.log(f"Search button name: {search_button_name}")
            
            # Build payload
            payload = {
                **form_data,
                search_box_name: normalized_code,
                search_button_name: 'Search'
            }
            
            # Step 4: Submit POST request
            self.log(f"POST request to: {actual_url}")
            
            post_response = self.session.post(
                actual_url,
                data=payload,
                headers={
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Referer': actual_url,
                    'Origin': 'https://www.weboc.gov.pk'
                },
                timeout=20,
                allow_redirects=True
            )
            
            self.log(f"POST response status: {post_response.status_code}")
            
            if post_response.status_code != 200:
                self.last_error = f"HTTP {post_response.status_code} on search request"
                return self._error_result(normalized_code, self.last_error)
            
            # Step 5: Parse results
            result = self.parse_duty_table(post_response.text, normalized_code)
            
            if result:
                self.log("Successfully parsed duty table")
                result['status'] = 'success'
                result['search_code'] = normalized_code
                return result
            else:
                # Check if there's an error message on the page
                soup = BeautifulSoup(post_response.text, 'html.parser')
                error_msg = soup.find('span', {'id': re.compile('lblError|lblMessage', re.I)})
                
                if error_msg:
                    self.last_error = f"WEBOC message: {error_msg.get_text(strip=True)}"
                else:
                    self.last_error = "No duty data found in response (HS code may not exist or page structure changed)"
                
                return self._error_result(normalized_code, self.last_error)
                
        except requests.Timeout:
            self.last_error = "Request timeout - WEBOC server not responding"
            return self._error_result(normalized_code, self.last_error)
        except requests.ConnectionError:
            self.last_error = "Connection error - check internet connection"
            return self._error_result(normalized_code, self.last_error)
        except Exception as e:
            self.last_error = f"Unexpected error: {str(e)}"
            self.log(f"Exception: {e}")
            import traceback
            self.log(traceback.format_exc())
            return self._error_result(normalized_code, self.last_error)
    
    def _error_result(self, code: str, error: str) -> Dict:
        """Create error result dictionary"""
        return {
            'search_code': code,
            'status': 'failed',
            'error': error,
            'customs_duty': None,
            'sales_tax': None,
            'income_tax': None
        }
    
    def parse_duty_table(self, html: str, hs_code: str) -> Optional[Dict]:
        """Parse duty details table with enhanced detection"""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Try multiple table selectors
        duty_table = None
        
        # Method 1: By ID
        duty_table = soup.find('table', {'id': re.compile('dgDutyDetail|DutyDetail', re.I)})
        
        # Method 2: By class
        if not duty_table:
            duty_table = soup.find('table', {'class': re.compile('duty|detail', re.I)})
        
        # Method 3: Find any table with duty-related content
        if not duty_table:
            tables = soup.find_all('table')
            for table in tables:
                text = table.get_text().lower()
                if 'customs duty' in text or 'sales tax' in text:
                    duty_table = table
                    break
        
        if not duty_table:
            self.log("No duty table found")
            return None
        
        self.log("Duty table found")
        
        result = {
            'hs_code': hs_code,
            'customs_duty': None,
            'sales_tax': None,
            'income_tax': None,
            'description': None,
            'raw_data': []
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
                self.log(f"Description: {result['description'][:50]}...")
                break
        
        # Parse table rows
        rows = duty_table.find_all('tr')
        self.log(f"Found {len(rows)} rows in table")
        
        for idx, row in enumerate(rows):
            cells = row.find_all(['td', 'th'])
            if len(cells) < 1:
                continue
            
            # Get all cell text
            cell_texts = [cell.get_text(strip=True) for cell in cells]
            row_text = ' '.join(cell_texts)
            
            result['raw_data'].append(row_text)
            self.log(f"Row {idx}: {row_text}")
            
            # Look for rates
            rate_matches = re.findall(r'(\d+(?:\.\d+)?)\s*%', row_text)
            if not rate_matches:
                # Try without % sign
                rate_matches = re.findall(r'@?\s*(\d+(?:\.\d+)?)', row_text)
            
            if not rate_matches:
                continue
            
            rate_value = float(rate_matches[0])
            row_lower = row_text.lower()
            
            # Classify duty type
            if ('customs duty' in row_lower or 'cd' in row_lower) and result['customs_duty'] is None:
                result['customs_duty'] = rate_value
                self.log(f"Customs Duty found: {rate_value}%")
            elif ('sales tax' in row_lower or 'st' in row_lower or 'gst' in row_lower) and result['sales_tax'] is None:
                result['sales_tax'] = rate_value
                self.log(f"Sales Tax found: {rate_value}%")
            elif ('income tax' in row_lower or 'it' in row_lower or 'wht' in row_lower) and result['income_tax'] is None:
                result['income_tax'] = rate_value
                self.log(f"Income Tax found: {rate_value}%")
        
        # Check if we found at least one duty
        if any([result['customs_duty'], result['sales_tax'], result['income_tax']]):
            self.log(f"Parse successful - CD: {result['customs_duty']}, ST: {result['sales_tax']}, IT: {result['income_tax']}")
            return result
        
        self.log("No duties extracted from table")
        return None


# Streamlit App
st.set_page_config(
    page_title="WEBOC HS Code Lookup",
    page_icon="📋",
    layout="wide"
)

st.title("📋 WEBOC Pakistan Customs Tariff Lookup")
st.markdown("Get real-time Customs Duty, Sales Tax, and Income Tax rates from WEBOC")

# Sidebar
with st.sidebar:
    st.header("⚙️ Settings")
    
    debug_mode = st.checkbox("🐛 Debug Mode", value=False, help="Show detailed logs")
    
    custom_url = st.text_input(
        "Custom WEBOC URL (optional)",
        placeholder="https://www.weboc.gov.pk/(S(...))/Shared/TariffList.aspx",
        help="Paste WEBOC URL with session token if default fails"
    )
    
    st.markdown("---")
    
    if st.button("🔄 Reset Session", use_container_width=True):
        if 'scraper' in st.session_state:
            del st.session_state.scraper
        st.success("Session reset!")
        st.rerun()
    
    if st.button("🗑️ Clear History", use_container_width=True):
        st.session_state.search_history = []
        st.rerun()
    
    st.markdown("---")
    st.info("""
    **Troubleshooting:**
    - Enable Debug Mode to see detailed logs
    - Try using a custom URL with session token
    - Check if WEBOC website is accessible
    """)

# Initialize scraper
if 'scraper' not in st.session_state or debug_mode != getattr(st.session_state.get('scraper'), 'debug', False):
    url = custom_url if custom_url else None
    st.session_state.scraper = WEBOCTariffScraper(base_url=url, debug=debug_mode)

if 'search_history' not in st.session_state:
    st.session_state.search_history = []

# Main interface
col1, col2 = st.columns([3, 1])

with col1:
    hs_input = st.text_input(
        "Enter HS Code",
        placeholder="e.g., 0808.1000, 0808.10, or 08081000",
        help="Enter HS code in any format"
    )

with col2:
    st.write("")
    st.write("")
    search_btn = st.button("🔍 Search WEBOC", use_container_width=True, type="primary")

# Quick examples
st.markdown("**Quick Examples:**")
ex_col1, ex_col2, ex_col3, ex_col4 = st.columns(4)

example_codes = {
    "🍎 Apples": "0808.10",
    "🐴 Horses": "0101.21",
    "👕 T-shirts": "6109.10",
    "📱 Phones": "8517.12"
}

for i, (label, code) in enumerate(example_codes.items()):
    with [ex_col1, ex_col2, ex_col3, ex_col4][i]:
        if st.button(label, use_container_width=True, key=f"ex_{i}"):
            hs_input = code
            search_btn = True

# Handle search
if search_btn and hs_input:
    # Debug output container
    if debug_mode:
        debug_container = st.expander("🐛 Debug Output", expanded=True)
    
    with st.spinner(f"🔍 Searching WEBOC for {hs_input}..."):
        result = st.session_state.scraper.search_hs_code(hs_input)
        
        # Add to history
        st.session_state.search_history.insert(0, {
            'input': hs_input,
            'result': result,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        })
        st.session_state.search_history = st.session_state.search_history[:10]
    
    st.markdown("---")
    
    if result.get('status') == 'success':
        st.success("✅ Data Retrieved Successfully!")
        
        # Display metrics
        metric_col1, metric_col2, metric_col3 = st.columns(3)
        
        with metric_col1:
            cd_value = result.get('customs_duty')
            st.metric(
                "Customs Duty (CD)",
                f"{cd_value}%" if cd_value is not None else "N/A"
            )
        
        with metric_col2:
            st_value = result.get('sales_tax')
            st.metric(
                "Sales Tax (ST)",
                f"{st_value}%" if st_value is not None else "N/A"
            )
        
        with metric_col3:
            it_value = result.get('income_tax')
            st.metric(
                "Income Tax (IT)",
                f"{it_value}%" if it_value is not None else "N/A"
            )
        
        # Detailed info
        with st.expander("📋 Detailed Information", expanded=True):
            st.markdown(f"**HS Code:** `{result.get('hs_code', 'N/A')}`")
            
            if result.get('description'):
                st.markdown(f"**Description:** {result['description']}")
            
            st.markdown("---")
            
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown(f"- **Customs Duty:** {result.get('customs_duty', 'N/A')}%")
                st.markdown(f"- **Sales Tax:** {result.get('sales_tax', 'N/A')}%")
            with col_b:
                st.markdown(f"- **Income Tax:** {result.get('income_tax', 'N/A')}%")
            
            # Show raw data in debug mode
            if debug_mode and result.get('raw_data'):
                st.markdown("---")
                st.markdown("**Raw Table Data:**")
                for i, row in enumerate(result['raw_data']):
                    st.text(f"{i+1}. {row}")
    
    else:
        st.error("❌ Failed to retrieve data from WEBOC")
        
        error_msg = result.get('error', 'Unknown error')
        st.markdown(f"**Error Details:** {error_msg}")
        
        # Show last error from scraper
        if st.session_state.scraper.last_error:
            st.code(st.session_state.scraper.last_error)
        
        st.markdown("---")
        st.info("""
        **Common Issues:**
        
        1. **Session Expired**: WEBOC uses session tokens that expire
           - Go to WEBOC website manually
           - Search for any HS code
           - Copy the URL from browser
           - Paste in sidebar "Custom WEBOC URL"
        
        2. **HS Code Not Found**: The code might not exist in WEBOC database
        
        3. **Website Structure Changed**: WEBOC may have updated their HTML
           - Enable Debug Mode to see details
        
        4. **Network Issues**: Check your internet connection
        """)
        
        # Show test button
        if st.button("🧪 Test Connection to WEBOC"):
            with st.spinner("Testing connection..."):
                try:
                    test_response = requests.get("https://www.weboc.gov.pk", timeout=10)
                    st.success(f"✅ WEBOC is accessible (HTTP {test_response.status_code})")
                except Exception as e:
                    st.error(f"❌ Cannot reach WEBOC: {str(e)}")

elif search_btn:
    st.warning("⚠️ Please enter an HS code to search")

# Search history
if st.session_state.search_history:
    st.markdown("---")
    st.subheader("📜 Recent Searches")
    
    for i, search in enumerate(st.session_state.search_history[:5]):
        with st.expander(f"{search['input']} - {search['timestamp']}", expanded=(i == 0)):
            result = search['result']
            if result.get('status') == 'success':
                cols = st.columns(3)
                cols[0].metric("CD", f"{result.get('customs_duty', 'N/A')}%")
                cols[1].metric("ST", f"{result.get('sales_tax', 'N/A')}%")
                cols[2].metric("IT", f"{result.get('income_tax', 'N/A')}%")
            else:
                st.error(f"Failed: {result.get('error', 'Unknown')}")

# Footer
st.markdown("---")
st.caption("💡 Data source: WEBOC Pakistan Customs | Always verify with official sources")