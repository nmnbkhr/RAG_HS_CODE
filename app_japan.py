"""
Japan Customs HS Code & Duty Calculator — Standalone Streamlit App.
Runs independently on port 8503. Imports ONLY from japan/ package.
"""

import streamlit as st
import pandas as pd

from japan.i18n import t
from japan.duty_calculator import JapanDutyCalculator
from japan.tariff_scraper import JapanTariffScraper
from japan.hs_normalizer import normalize, is_valid
from japan.epa_database import (
    get_epa_for_country, is_gsp_country, get_all_countries,
    get_countries_grouped_by_epa, COUNTRY_NAMES,
)
from japan.exchange_rate import get_customs_fx, get_supported_currencies
from japan.consumption_tax import get_rate as get_consumption_rate, is_food_item
from japan.excise_tax import get_excise_info

# LLM search — optional (requires openai package + API key)
try:
    from japan.llm_search import llm_search, is_llm_available, LLMClassification
    _LLM_AVAILABLE = True
except ImportError:
    _LLM_AVAILABLE = False

# ---------------------------------------------------------------------------
# Page Config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Japan Customs Calculator / \u65e5\u672c\u7a0e\u95a2\u8a08\u7b97\u6a5f",
    page_icon="\U0001f1ef\U0001f1f5",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# CSS — Japan Blue Theme
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    :root {
        --jp-blue: #1B4F72;
        --jp-blue-light: #2E86C1;
        --jp-blue-pale: #E8F0FE;
        --bg: #F8F9FC;
        --card-bg: #FFFFFF;
        --text-primary: #1A1A2E;
        --text-secondary: #4A5568;
        --border: #E2E8F0;
        --success: #16A34A;
        --warning: #D97706;
        --error: #DC2626;
        --info: #2563EB;
        --radius: 8px;
        --shadow: 0 2px 8px rgba(0,0,0,0.06);
        --shadow-lg: 0 4px 16px rgba(0,0,0,0.1);
    }

    .main { padding: 1rem 2rem; background: var(--bg); }
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }

    /* Header */
    .main-header {
        background: linear-gradient(135deg, #1B4F72 0%, #2E86C1 60%, #3498DB 100%);
        padding: 2rem 2.5rem; border-radius: var(--radius); color: white;
        margin-bottom: 2rem; box-shadow: var(--shadow-lg);
        border-bottom: 4px solid #154360;
        position: relative; overflow: hidden;
    }
    .main-header::before {
        content: ''; position: absolute; top: -50%; right: -20%;
        width: 300px; height: 300px;
        background: radial-gradient(circle, rgba(255,255,255,0.06) 0%, transparent 70%);
        border-radius: 50%;
    }
    .main-header h1 { margin: 0; font-size: 2.2rem; font-weight: 800; letter-spacing: -0.5px; }
    .main-header p { margin: 0.5rem 0 0 0; font-size: 1.05rem; opacity: 0.85; }
    .header-badge {
        display: inline-block; background: rgba(255,255,255,0.15);
        border: 1px solid rgba(255,255,255,0.25);
        padding: 0.2rem 0.75rem; border-radius: 20px;
        font-size: 0.8rem; margin-top: 0.5rem; font-weight: 500;
    }

    /* Tab Bar */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.5rem; background-color: var(--card-bg);
        padding: 0.5rem; border-radius: var(--radius);
        border: 1px solid var(--border); box-shadow: var(--shadow);
    }
    .stTabs [data-baseweb="tab"] {
        padding: 0.75rem 1.5rem; border-radius: 6px; font-weight: 600;
        font-size: 0.9rem; color: var(--text-secondary);
        border-bottom: 3px solid transparent; transition: all 0.2s ease;
    }
    .stTabs [data-baseweb="tab"]:hover {
        background: var(--jp-blue-pale); color: var(--jp-blue);
    }
    .stTabs [aria-selected="true"] {
        color: var(--jp-blue) !important;
        border-bottom: 3px solid var(--jp-blue) !important;
        background: var(--jp-blue-pale) !important; font-weight: 700;
    }

    /* Section Headers */
    .section-header {
        font-size: 1.2rem; font-weight: 700; color: var(--text-primary);
        margin: 1.5rem 0 1rem 0; padding: 0.6rem 0 0.5rem 1rem;
        border-left: 4px solid var(--jp-blue);
        border-bottom: 1px solid var(--border);
        background: linear-gradient(90deg, var(--jp-blue-pale) 0%, transparent 100%);
        border-radius: 0 var(--radius) 0 0;
    }

    /* Buttons — Japan Blue */
    .stButton > button {
        border-radius: 6px; font-weight: 600;
        transition: all 0.2s ease; border: none; letter-spacing: 0.3px;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(27, 79, 114, 0.25);
    }
    .stButton > button[kind="primary"],
    .stButton > button[data-testid="stBaseButton-primary"],
    button[data-testid="baseButton-primary"] {
        background: linear-gradient(135deg, #1B4F72 0%, #2E86C1 100%) !important;
        color: white !important; border: none !important;
    }
    .stButton > button[kind="primary"]:hover,
    .stButton > button[data-testid="stBaseButton-primary"]:hover,
    button[data-testid="baseButton-primary"]:hover {
        background: linear-gradient(135deg, #154360 0%, #1B4F72 100%) !important;
    }
    .stButton > button[kind="secondary"],
    .stButton > button[data-testid="stBaseButton-secondary"],
    button[data-testid="baseButton-secondary"] {
        background: white !important; color: #1B4F72 !important;
        border: 2px solid #1B4F72 !important;
    }
    .stButton > button[kind="secondary"]:hover,
    .stButton > button[data-testid="stBaseButton-secondary"]:hover,
    button[data-testid="baseButton-secondary"]:hover {
        background: #E8F0FE !important;
    }

    /* Input Focus */
    .stTextInput > div > div > input:focus,
    .stNumberInput > div > div > input:focus {
        border-color: var(--jp-blue) !important;
        box-shadow: 0 0 0 3px rgba(27, 79, 114, 0.15) !important;
    }
    div[data-baseweb="select"] > div:focus-within {
        border-color: var(--jp-blue) !important;
        box-shadow: 0 0 0 3px rgba(27, 79, 114, 0.15) !important;
    }

    /* Metrics */
    [data-testid="stMetric"] {
        background: var(--card-bg); border: 1px solid var(--border);
        border-left: 4px solid var(--jp-blue); border-radius: var(--radius);
        padding: 1rem 1.25rem; box-shadow: var(--shadow);
    }
    [data-testid="stMetric"]:hover { box-shadow: var(--shadow-lg); }
    [data-testid="stMetricLabel"] {
        font-size: 0.8rem; font-weight: 600; color: var(--text-secondary);
        text-transform: uppercase; letter-spacing: 0.5px;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.6rem; font-weight: 700; color: var(--jp-blue);
    }

    /* Cards */
    .form-card {
        background: var(--card-bg); border: 1px solid var(--border);
        border-radius: var(--radius); padding: 1.5rem;
        margin-bottom: 1.5rem; box-shadow: var(--shadow);
    }
    .info-box {
        background: linear-gradient(135deg, #DBEAFE 0%, #EFF6FF 100%);
        border-left: 4px solid var(--info);
        padding: 1rem 1.25rem; border-radius: 0 var(--radius) var(--radius) 0;
        margin: 1rem 0; box-shadow: var(--shadow);
    }
    .success-box {
        background: linear-gradient(135deg, #D1FAE5 0%, #ECFDF5 100%);
        border-left: 4px solid var(--success);
        padding: 1rem 1.25rem; border-radius: 0 var(--radius) var(--radius) 0;
        margin: 1rem 0; box-shadow: var(--shadow);
    }
    .warning-box {
        background: linear-gradient(135deg, #FEF3C7 0%, #FFFBEB 100%);
        border-left: 4px solid var(--warning);
        padding: 1rem 1.25rem; border-radius: 0 var(--radius) var(--radius) 0;
        margin: 1rem 0; box-shadow: var(--shadow);
    }

    /* EPA Badge */
    .epa-badge-yes {
        display: inline-flex; align-items: center; gap: 6px;
        padding: 0.25rem 0.75rem; border-radius: 20px;
        font-size: 0.85rem; font-weight: 600;
        background: #D1FAE5; color: #065F46;
    }
    .epa-badge-no {
        display: inline-flex; align-items: center; gap: 6px;
        padding: 0.25rem 0.75rem; border-radius: 20px;
        font-size: 0.85rem; font-weight: 600;
        background: #FEE2E2; color: #991B1B;
    }
    .gsp-badge {
        display: inline-flex; align-items: center; gap: 6px;
        padding: 0.25rem 0.75rem; border-radius: 20px;
        font-size: 0.85rem; font-weight: 600;
        background: #FEF3C7; color: #92400E;
    }

    /* DataFrames */
    .stDataFrame {
        border-radius: var(--radius); overflow: hidden;
        box-shadow: var(--shadow); border: 1px solid var(--border);
    }
    .stDataFrame [data-testid="stDataFrameResizable"] th,
    .stDataFrame thead th {
        background: #1B4F72 !important; color: white !important;
        font-weight: 600; font-size: 0.85rem;
    }
    .stDataFrame tbody tr:nth-child(even) { background: #F0F4FA; }
    .stDataFrame tbody tr:hover { background: #E8F0FE; }

    /* Section Divider */
    .section-divider {
        height: 1px;
        background: linear-gradient(90deg, transparent, var(--border), transparent);
        margin: 1.5rem 0; border: none;
    }

    /* Sidebar */
    .sidebar-card {
        background: var(--card-bg); border: 1px solid var(--border);
        border-radius: var(--radius); padding: 1rem;
        margin-bottom: 0.75rem; box-shadow: var(--shadow);
    }
    .sidebar-card h4 {
        margin: 0 0 0.5rem 0; font-size: 0.85rem; font-weight: 700;
        color: var(--jp-blue); text-transform: uppercase; letter-spacing: 0.5px;
    }
    section[data-testid="stSidebar"] { background: #F0F4FA; border-right: 1px solid var(--border); }

    /* Footer */
    .app-footer {
        background: linear-gradient(135deg, #1B4F72 0%, #2E86C1 100%);
        color: white; padding: 1.5rem 2rem; border-radius: var(--radius);
        margin-top: 2rem; text-align: center;
    }
    .app-footer p { margin: 0.25rem 0; font-size: 0.9rem; opacity: 0.9; }
    .app-footer .footer-title { font-weight: 700; font-size: 1rem; opacity: 1; }
    .app-footer .footer-disclaimer {
        font-size: 0.75rem; opacity: 0.7; margin-top: 0.75rem;
        padding-top: 0.75rem; border-top: 1px solid rgba(255,255,255,0.2);
    }
    .app-footer a { color: #AED6F1; text-decoration: none; }
    .app-footer a:hover { text-decoration: underline; }

    /* Mobile */
    @media (max-width: 768px) {
        .main { padding: 0.5rem 1rem; }
        .main-header { padding: 1.25rem; }
        .main-header h1 { font-size: 1.6rem; }
        .stTabs [data-baseweb="tab"] { padding: 0.5rem 0.75rem; font-size: 0.8rem; }
        [data-testid="stMetricValue"] { font-size: 1.2rem; }
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Session State
# ---------------------------------------------------------------------------
if 'jp_lang' not in st.session_state:
    st.session_state.jp_lang = 'en'
if 'jp_calculator' not in st.session_state:
    st.session_state.jp_calculator = JapanDutyCalculator()
if 'jp_last_lookup' not in st.session_state:
    st.session_state.jp_last_lookup = None
if 'jp_prefill' not in st.session_state:
    st.session_state.jp_prefill = None


def _t(key: str) -> str:
    """Shortcut: translate using current session language."""
    return t(key, st.session_state.jp_lang)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    # Language toggle
    st.markdown('<div class="sidebar-card"><h4>\U0001f310 Language</h4>', unsafe_allow_html=True)
    lang_choice = st.radio(
        _t('sidebar_language'),
        ['English', '\u65e5\u672c\u8a9e'],
        horizontal=True,
        key='jp_lang_radio',
        label_visibility='collapsed',
    )
    st.session_state.jp_lang = 'ja' if lang_choice == '\u65e5\u672c\u8a9e' else 'en'
    st.markdown('</div>', unsafe_allow_html=True)

    # FX Rate
    st.markdown(f'<div class="sidebar-card"><h4>{_t("sidebar_fx_title")}</h4>', unsafe_allow_html=True)
    try:
        usd_rate, usd_src = get_customs_fx('USD')
        st.metric('JPY/USD', f'\u00a5{usd_rate:,.2f}')
        st.caption(usd_src)
    except Exception:
        st.caption('Rate unavailable')
    st.markdown('</div>', unsafe_allow_html=True)

    # Tariff cache info
    st.markdown('<div class="sidebar-card"><h4>Tariff Data</h4>', unsafe_allow_html=True)
    cache_size = st.session_state.jp_calculator.scraper.cache_size()
    if cache_size > 0:
        st.success(f'{cache_size:,} codes cached')
    else:
        st.warning('No cache. Use "Scrape Chapter" in Lookup tab.')
    st.markdown('</div>', unsafe_allow_html=True)

    # AI Search toggle
    if _LLM_AVAILABLE:
        st.markdown(
            f'<div class="sidebar-card"><h4>{_t("ai_search_title")}</h4>',
            unsafe_allow_html=True,
        )
        if is_llm_available():
            ai_enabled = st.toggle(
                _t('ai_search_toggle'),
                value=False,
                key='jp_ai_search',
                help=_t('ai_search_help'),
            )
            if ai_enabled:
                st.caption(_t('ai_search_hint'))
        else:
            st.warning(_t('ai_search_unavailable'))
        st.markdown('</div>', unsafe_allow_html=True)

    # About
    st.markdown(f'<div class="sidebar-card"><h4>{_t("sidebar_about_title")}</h4>', unsafe_allow_html=True)
    st.caption(_t('sidebar_about_text'))
    st.markdown(f'**{_t("sidebar_links_title")}:**')
    st.markdown("""
- [Japan Customs](https://www.customs.go.jp/english/)
- [Tariff Schedule](https://www.customs.go.jp/english/tariff/)
- [EPA Info](https://www.customs.go.jp/english/c-answer_e/sonota/9301_e.htm)
    """)
    st.markdown('</div>', unsafe_allow_html=True)

    # Disclaimer
    st.markdown('<div class="sidebar-card">', unsafe_allow_html=True)
    st.caption(_t('sidebar_disclaimer'))
    st.markdown('</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown(f"""
<div class="main-header">
    <h1>{_t('app_title')}</h1>
    <p>{_t('app_subtitle')}</p>
    <span class="header-badge">{_t('app_badge')}</span>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_labels = [_t('tab_lookup'), _t('tab_calc')]
tab_lookup, tab_calc = st.tabs(tab_labels)


# ===== TAB 1: HS Code Lookup =====
with tab_lookup:
    st.markdown(f'<div class="section-header">{_t("lookup_header")}</div>', unsafe_allow_html=True)
    st.caption(_t('lookup_caption'))

    col1, col2 = st.columns([4, 1])
    with col1:
        hs_input = st.text_input(
            _t('lookup_input_label'),
            placeholder='e.g. 0901.21, coffee, EV car, laptop computer...',
            key='jp_hs_lookup',
        )
    with col2:
        st.write('')
        search_btn = st.button(
            _t('lookup_search_btn'), use_container_width=True,
            type='primary', key='jp_search_btn',
        )

    st.caption('Accepts HS codes (0901.21), keywords (coffee), or natural language (EV car front wheel drive)')

    # Quick examples
    st.markdown(f'**{_t("lookup_examples")}**')
    ex_cols = st.columns(5)
    examples = [
        ('Coffee', '0901.21'),
        ('Rice', '1006.30'),
        ('EV car', 'EV car'),
        ('Laptop', 'laptop computer'),
        ('Beer', 'beer'),
    ]
    for idx, (label, code) in enumerate(examples):
        with ex_cols[idx]:
            if st.button(label, use_container_width=True, key=f'jp_ex_{idx}'):
                hs_input = code
                search_btn = True

    # Scrape controls
    with st.expander('Scrape tariff data from Japan Customs'):
        scrape_cols = st.columns([2, 1])
        with scrape_cols[0]:
            ch_num = st.number_input('Chapter (01-97)', min_value=1, max_value=97, value=9, key='jp_scrape_ch')
        with scrape_cols[1]:
            st.write('')
            if st.button('Scrape Chapter', use_container_width=True, key='jp_scrape_btn'):
                with st.spinner(f'Scraping chapter {ch_num:02d}...'):
                    results = st.session_state.jp_calculator.scraper.scrape_chapter(ch_num)
                    st.session_state.jp_calculator.scraper.save_cache()
                if results:
                    st.success(f'Scraped {len(results)} entries from chapter {ch_num:02d}')
                else:
                    st.warning(f'No entries found for chapter {ch_num:02d}')

    # Search execution
    if search_btn and hs_input:
        scraper = st.session_state.jp_calculator.scraper
        hs_input_stripped = hs_input.strip()
        lang = st.session_state.jp_lang

        # Route through LLM search or keyword search
        ai_on = _LLM_AVAILABLE and st.session_state.get('jp_ai_search', False)
        classification = None

        if ai_on and is_llm_available():
            with st.spinner(_t('ai_analyzing')):
                results, classification = llm_search(
                    hs_input_stripped, scraper, lang=lang,
                )
        else:
            results = scraper.search(hs_input_stripped, lang=lang)

        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

        # Show LLM feedback when AI search was used
        if classification and not classification.error:
            intent_display = classification.intent_jp if (lang == 'ja' and classification.intent_jp) else classification.intent
            terms_str = ', '.join(classification.search_terms[:8])
            codes_str = ', '.join(classification.headings[:5])
            st.markdown(
                f'<div class="info-box">'
                f'<b>{_t("ai_understanding")}:</b> {intent_display}<br>'
                f'<small>'
                f'<b>{_t("ai_search_terms")}:</b> {terms_str} &nbsp;|&nbsp; '
                f'<b>{_t("ai_headings")}:</b> {codes_str} &nbsp;|&nbsp; '
                f'<b>{_t("ai_confidence")}:</b> {classification.confidence}'
                f'</small></div>',
                unsafe_allow_html=True,
            )
        elif classification and classification.error:
            st.markdown(
                f'<div class="warning-box">{_t("ai_fallback").format(classification.error)}</div>',
                unsafe_allow_html=True,
            )

        if results:
            st.markdown(f'<div class="success-box"><b>{_t("lookup_results")}</b> \u2014 {len(results)} match(es)</div>', unsafe_allow_html=True)

            for i, entry in enumerate(results):
                code = entry.get('statistical_code', '')
                desc_en = entry.get('desc_en', '')
                desc_jp = entry.get('desc_jp', '')
                unit = entry.get('unit', '')
                gen = entry.get('general_rate', '') or '\u2014'
                wto = entry.get('wto_rate', '') or '\u2014'
                temp = entry.get('temporary_rate', '') or '\u2014'
                gsp = entry.get('gsp_rate', '') or '\u2014'

                # --- Card header: code + primary description ---
                _desc_en_display = desc_en or "\u2014"
                _desc_jp_display = desc_jp or "\u2014"
                primary_desc = _desc_jp_display if lang == 'ja' else _desc_en_display
                secondary_desc = _desc_en_display if lang == 'ja' else _desc_jp_display
                primary_label = _t('description_jp') if lang == 'ja' else _t('description_en')
                secondary_label = _t('description_en') if lang == 'ja' else _t('description_jp')

                st.markdown(
                    f'<div class="form-card" style="padding:1rem 1.25rem;margin-bottom:0.75rem;">'
                    f'<div style="display:flex;justify-content:space-between;align-items:baseline;">'
                    f'<span style="font-size:1.1rem;font-weight:700;color:var(--jp-blue);font-family:monospace;">{code}</span>'
                    f'<span style="font-size:0.8rem;color:var(--text-secondary);">{_t("unit")}: {unit}</span>'
                    f'</div>'
                    f'<p style="margin:0.35rem 0 0.15rem 0;font-size:0.95rem;color:var(--text-primary);">{primary_desc}</p>'
                    f'<p style="margin:0;font-size:0.8rem;color:var(--text-secondary);">{secondary_desc}</p>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                # --- Key rates: 4 compact metrics in a row ---
                rate_cols = st.columns(4)
                with rate_cols[0]:
                    st.metric(_t('general_rate'), gen)
                with rate_cols[1]:
                    st.metric(_t('wto_rate'), wto)
                with rate_cols[2]:
                    st.metric(_t('temporary_rate'), temp or '\u2014')
                with rate_cols[3]:
                    # Consumption tax
                    cons_rate = get_consumption_rate(code)
                    cons_label = _t('reduced_rate_label') if cons_rate == 0.08 else _t('standard_rate_label')
                    st.metric(_t('consumption_tax_indicator'), cons_label)

                # --- Excise warning (only if applicable) ---
                exc_info = get_excise_info(code)
                if exc_info:
                    name = exc_info.get(f'name_{lang}', exc_info['name_en'])
                    st.markdown(
                        f'<div class="warning-box"><b>{_t("breakdown_excise")}:</b> '
                        f'{name} \u2014 \u00a5{exc_info["rate"]:,.0f}/{exc_info["per"]}</div>',
                        unsafe_allow_html=True,
                    )

                # --- EPA rates in collapsible expander ---
                epa_rates = entry.get('epa_rates', {})
                epa_filled = {k: v for k, v in epa_rates.items() if v and v not in ('\u2014', '-')}
                btn_col, expander_col = st.columns([1, 3])
                with btn_col:
                    if st.button(_t('lookup_use_in_calc'), key=f'jp_use_{i}', use_container_width=True):
                        st.session_state.jp_prefill = entry
                        st.info(_t('lookup_data_saved'))
                with expander_col:
                    if epa_filled or gsp != '\u2014':
                        epa_label = f'EPA / GSP rates ({len(epa_filled)} agreements)'
                        with st.expander(epa_label):
                            epa_rows = []
                            if gsp != '\u2014':
                                epa_rows.append({'Agreement': 'GSP', 'Rate': gsp})
                            for epa_name, epa_val in epa_filled.items():
                                epa_rows.append({'Agreement': epa_name, 'Rate': epa_val})
                            st.dataframe(
                                pd.DataFrame(epa_rows),
                                use_container_width=True,
                                hide_index=True,
                            )

                if i < len(results) - 1:
                    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        else:
            st.warning(_t('lookup_no_results'))


# ===== TAB 2: Import Duty Calculator =====
with tab_calc:
    st.markdown(f'<div class="section-header">{_t("calc_header")}</div>', unsafe_allow_html=True)
    st.caption(_t('calc_caption'))

    prefill = st.session_state.jp_prefill or {}
    prefill_code = prefill.get('statistical_code', '')

    # Section 1: HS Code
    st.markdown(f'<div class="form-card">', unsafe_allow_html=True)
    st.markdown(f'<div class="section-header">{_t("calc_hs_section")}</div>', unsafe_allow_html=True)
    hs_col1, hs_col2 = st.columns([3, 1])
    with hs_col1:
        calc_hs = st.text_input(
            _t('calc_hs_input'),
            value=prefill_code,
            placeholder=_t('calc_hs_placeholder'),
            key='jp_calc_hs',
        )
    with hs_col2:
        st.write('')
        if calc_hs and st.button(_t('calc_fetch_btn'), use_container_width=True, key='jp_calc_fetch'):
            entry = st.session_state.jp_calculator.scraper.get_rates(calc_hs)
            if entry:
                st.session_state.jp_prefill = entry
                st.success(f'Loaded: {entry.get("desc_en", "")[:60]}')
                st.rerun()
            else:
                st.error(_t('error_hs_not_found'))

    if prefill:
        desc_en = prefill.get('desc_en', '')
        desc_jp = prefill.get('desc_jp', '')
        if lang == 'ja' and desc_jp:
            st.markdown(f'<div class="info-box"><b>{_t("description_jp")}:</b> {desc_jp}</div>', unsafe_allow_html=True)
            if desc_en:
                st.caption(f'{_t("description_en")}: {desc_en}')
        elif desc_en:
            st.markdown(f'<div class="info-box"><b>{_t("description_en")}:</b> {desc_en}</div>', unsafe_allow_html=True)
            if desc_jp:
                st.caption(f'{_t("description_jp")}: {desc_jp}')
    st.markdown('</div>', unsafe_allow_html=True)

    # Section 2: Country of Origin
    st.markdown(f'<div class="form-card">', unsafe_allow_html=True)
    st.markdown(f'<div class="section-header">{_t("calc_country_section")}</div>', unsafe_allow_html=True)

    lang = st.session_state.jp_lang
    names = COUNTRY_NAMES.get(lang, COUNTRY_NAMES['en'])

    # Build grouped options
    grouped = get_countries_grouped_by_epa(lang)
    country_options = [_t('calc_country_none')]
    country_codes = ['']
    for epa_name, entries in grouped.items():
        country_options.append(f'\u2500\u2500 {epa_name} \u2500\u2500')
        country_codes.append('')
        for code, name in entries:
            country_options.append(f'  {name} ({code})')
            country_codes.append(code)
    # Add "Other" section for unlisted countries
    country_options.append('\u2500\u2500 Other \u2500\u2500')
    country_codes.append('')
    for code in sorted(names.keys()):
        if code not in [c for _, entries in grouped.items() for c, _ in entries]:
            if code not in [c for c in country_codes if c]:
                country_options.append(f'  {names[code]} ({code})')
                country_codes.append(code)

    selected_idx = st.selectbox(
        _t('calc_country_label'),
        range(len(country_options)),
        format_func=lambda x: country_options[x],
        key='jp_country_select',
    )
    selected_country = country_codes[selected_idx] if selected_idx else ''

    # EPA / GSP badges
    if selected_country:
        epa = get_epa_for_country(selected_country)
        gsp = is_gsp_country(selected_country)
        badge_html = ''
        if epa:
            badge_html += f'<span class="epa-badge-yes">\u2705 {_t("calc_epa_badge_yes").format(epa)}</span> '
        else:
            badge_html += f'<span class="epa-badge-no">\u274c {_t("calc_epa_badge_no")}</span> '
        if gsp:
            badge_html += f'<span class="gsp-badge">\U0001f30d {_t("calc_gsp_badge")}</span>'
        st.markdown(badge_html, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Section 3: Values
    st.markdown(f'<div class="form-card">', unsafe_allow_html=True)
    st.markdown(f'<div class="section-header">{_t("calc_values_section")}</div>', unsafe_allow_html=True)

    val_row1 = st.columns(3)
    with val_row1[0]:
        calc_fob = st.number_input(_t('calc_fob'), min_value=0.0, step=0.01, value=0.0, key='jp_fob')
    with val_row1[1]:
        calc_freight = st.number_input(_t('calc_freight'), min_value=0.0, step=0.01, value=0.0, key='jp_freight')
    with val_row1[2]:
        calc_insurance = st.number_input(_t('calc_insurance'), min_value=0.0, step=0.01, value=0.0, key='jp_insurance')

    val_row2 = st.columns(4)
    currencies = get_supported_currencies()
    with val_row2[0]:
        calc_currency = st.selectbox(_t('calc_currency'), currencies, key='jp_currency')
    with val_row2[1]:
        calc_quantity = st.number_input(_t('calc_quantity'), min_value=0.0, step=1.0, value=1.0, key='jp_qty')
    with val_row2[2]:
        calc_unit = st.selectbox(
            _t('calc_unit'),
            ['KG', 'L', 'NO', 'M', 'M2', 'M3', 'PR', 'DZ', 'GT', 'SET'],
            key='jp_unit',
        )
    with val_row2[3]:
        calc_manual_fx = st.number_input(
            _t('calc_manual_fx'), min_value=0.0, step=0.01, value=0.0,
            help=_t('calc_manual_fx_help'), key='jp_manual_fx',
        )

    use_simplified = st.checkbox(_t('calc_simplified_checkbox'), key='jp_simplified')

    st.markdown('</div>', unsafe_allow_html=True)

    # Calculate button
    if st.button(_t('calc_btn'), type='primary', use_container_width=True, key='jp_calc_btn'):
        if not calc_hs or calc_quantity <= 0 or calc_fob <= 0:
            st.error(_t('calc_error_inputs'))
        else:
            with st.spinner(_t('calc_btn') + '...'):
                result = st.session_state.jp_calculator.calculate(
                    hs_code=calc_hs,
                    country=selected_country,
                    fob=calc_fob,
                    freight=calc_freight,
                    insurance=calc_insurance,
                    currency=calc_currency,
                    quantity=calc_quantity,
                    unit=calc_unit,
                    use_simplified=use_simplified,
                    manual_fx_rate=calc_manual_fx,
                )

            # Results
            st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="section-header">{_t("results_header")}</div>', unsafe_allow_html=True)

            # 4-column metrics
            met_cols = st.columns(4)
            with met_cols[0]:
                st.metric(_t('results_cif'), f'\u00a5{result["cif_jpy"]:,.0f}')
            with met_cols[1]:
                st.metric(_t('results_duty'), f'\u00a5{result["customs_duty"]:,.0f}')
            with met_cols[2]:
                st.metric(_t('results_tax'), f'\u00a5{result["consumption_tax"]:,.0f}')
            with met_cols[3]:
                st.metric(_t('results_total'), f'\u00a5{result["total_landed"]:,.0f}')

            # Simplified note
            if result['is_simplified']:
                st.markdown(
                    f'<div class="info-box">{_t("breakdown_simplified_note")}</div>',
                    unsafe_allow_html=True,
                )

            st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

            # Applied rate display
            sr = result['selected_rate']
            if sr:
                rate_display = ''
                if sr.rate_type == 'ad_valorem':
                    rate_display = f'{sr.value}%' if sr.value else _t('duty_free')
                elif sr.rate_type == 'specific':
                    rate_display = f'\u00a5{sr.per_unit_value:,.0f}/{sr.per_unit_name}'
                elif sr.rate_type == 'combined':
                    rate_display = f'{sr.value}% + \u00a5{sr.per_unit_value:,.0f}/{sr.per_unit_name}'
                applied_label = f'{rate_display} ({sr.agreement})'
            else:
                applied_label = _t('duty_free')

            # Breakdown table
            cons_pct = int(result['consumption_rate'] * 100)
            breakdown_data = {
                _t('results_breakdown'): [
                    _t('breakdown_fob'),
                    _t('breakdown_freight'),
                    _t('breakdown_insurance'),
                    _t('breakdown_cif_foreign'),
                    f'{_t("results_fx_rate")} ({result["fx_source"]})',
                    _t('breakdown_cif_jpy'),
                    '',
                    _t('breakdown_applied_rate'),
                    _t('breakdown_customs_duty'),
                    _t('breakdown_excise'),
                    _t('breakdown_consumption_tax').format(cons_pct),
                    '',
                    _t('breakdown_total'),
                ],
                '\u00a5': [
                    f'{result["fob"]:,.2f} {result["currency"]}',
                    f'{result["freight"]:,.2f} {result["currency"]}',
                    f'{result["insurance"]:,.2f} {result["currency"]}',
                    f'{result["cif_original"]:,.2f} {result["currency"]}',
                    f'{result["fx_rate"]:,.4f}',
                    f'\u00a5{result["cif_jpy"]:,.0f}',
                    '',
                    applied_label,
                    f'\u00a5{result["customs_duty"]:,.0f}',
                    f'\u00a5{result["excise"]:,.0f}' if result['excise'] > 0 else _t('breakdown_excise_na'),
                    f'\u00a5{result["consumption_tax"]:,.0f}',
                    '',
                    f'\u00a5{result["total_landed"]:,.0f}',
                ],
            }
            st.dataframe(pd.DataFrame(breakdown_data), use_container_width=True, hide_index=True)

            # Rate comparison table
            if result['all_rates']:
                st.markdown(f'<div class="section-header">{_t("results_rate_comparison")}</div>', unsafe_allow_html=True)
                all_r = result['all_rates']
                agreement_applied = sr.agreement if sr else ''

                comp_rows = [
                    {
                        _t('rate_agreement'): _t('general_rate'),
                        _t('rate_value'): all_r.get('general_rate', '\u2014') or '\u2014',
                        _t('rate_status'): _t('rate_applied') if agreement_applied == 'General' else _t('rate_not_applied'),
                    },
                    {
                        _t('rate_agreement'): _t('wto_rate'),
                        _t('rate_value'): all_r.get('wto_rate', '\u2014') or '\u2014',
                        _t('rate_status'): _t('rate_applied') if agreement_applied in ('WTO', 'CPTPP', 'RCEP', 'Japan-EU', 'GSP') and all_r.get('wto_rate') else _t('rate_not_applied'),
                    },
                    {
                        _t('rate_agreement'): _t('temporary_rate'),
                        _t('rate_value'): all_r.get('temporary_rate', '\u2014') or '\u2014',
                        _t('rate_status'): _t('rate_applied') if agreement_applied == 'Temporary' else _t('rate_not_applied'),
                    },
                ]

                # Add EPA rows from actual scraped EPA data
                epa_rates = all_r.get('epa_rates', {})
                if selected_country:
                    epa = get_epa_for_country(selected_country)
                    if epa and epa_rates:
                        # Try to find the matching EPA rate column
                        epa_rate_val = epa_rates.get(epa, '') or '\u2014'
                        comp_rows.append({
                            _t('rate_agreement'): epa,
                            _t('rate_value'): epa_rate_val,
                            _t('rate_status'): _t('rate_applied') if agreement_applied == epa else _t('rate_not_applied'),
                        })
                    elif epa:
                        comp_rows.append({
                            _t('rate_agreement'): epa,
                            _t('rate_value'): '\u2014',
                            _t('rate_status'): _t('rate_applied') if agreement_applied == epa else _t('rate_not_applied'),
                        })

                # Add Japan-US rate if available
                jp_us = all_r.get('jp_us_rate', '')
                if jp_us and jp_us not in ('\u2014', '-'):
                    comp_rows.append({
                        _t('rate_agreement'): 'Japan-US',
                        _t('rate_value'): jp_us,
                        _t('rate_status'): _t('rate_applied') if selected_country == 'US' else _t('rate_not_applied'),
                    })

                df_comp = pd.DataFrame(comp_rows)
                st.dataframe(df_comp, use_container_width=True, hide_index=True)

            # Disclaimer
            st.caption(
                f'{_t("results_fx_rate")}: {result["fx_source"]} ({result["fx_rate"]:,.4f}) | '
                f'{_t("hs_code")}: {result["hs_code"]}'
            )


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.markdown(f"""
<div class="app-footer">
    <p class="footer-title">{_t('footer_title')}</p>
    <p>{_t('footer_formula')}</p>
    <p>{_t('footer_sources')} |
       <a href="https://www.customs.go.jp/english/" target="_blank">customs.go.jp</a></p>
    <p class="footer-disclaimer">{_t('footer_disclaimer')}</p>
</div>
""", unsafe_allow_html=True)
