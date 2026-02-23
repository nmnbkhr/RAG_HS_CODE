"""Japan EPA/FTA agreement database — hardcoded country mappings."""

# EPA agreement → list of ISO 2-letter country codes
EPA_AGREEMENTS = {
    'CPTPP': ['AU', 'BN', 'CA', 'CL', 'MY', 'MX', 'NZ', 'PE', 'SG', 'VN'],
    'RCEP': [
        'CN', 'KR', 'AU', 'NZ', 'BN', 'KH', 'ID', 'LA', 'MY', 'MM',
        'PH', 'SG', 'TH', 'VN',
    ],
    'Japan-EU': [
        'AT', 'BE', 'BG', 'HR', 'CY', 'CZ', 'DK', 'EE', 'FI', 'FR',
        'DE', 'GR', 'HU', 'IE', 'IT', 'LV', 'LT', 'LU', 'MT', 'NL',
        'PL', 'PT', 'RO', 'SK', 'SI', 'ES', 'SE',
    ],
    'Japan-UK': ['GB'],
    'Japan-US': ['US'],
    'Japan-Singapore': ['SG'],
    'Japan-Mexico': ['MX'],
    'Japan-Malaysia': ['MY'],
    'Japan-Chile': ['CL'],
    'Japan-Thailand': ['TH'],
    'Japan-Indonesia': ['ID'],
    'Japan-Brunei': ['BN'],
    'Japan-Philippines': ['PH'],
    'Japan-Switzerland': ['CH'],
    'Japan-Vietnam': ['VN'],
    'Japan-India': ['IN'],
    'Japan-Peru': ['PE'],
    'Japan-Australia': ['AU'],
    'Japan-Mongolia': ['MN'],
}

# GSP beneficiary developing countries
GSP_BENEFICIARIES = [
    'PK', 'BD', 'LK', 'NP', 'KH', 'LA', 'MM', 'ET', 'TZ', 'MZ',
    'SN', 'MG', 'AF', 'HT', 'BJ', 'BF', 'BI', 'CF', 'TD', 'KM',
    'CD', 'DJ', 'GQ', 'ER', 'GM', 'GN', 'GW', 'LS', 'LR', 'MW',
    'ML', 'MR', 'NE', 'RW', 'ST', 'SL', 'SO', 'SS', 'TG', 'UG',
    'YE', 'ZM', 'BO', 'GT', 'HN', 'NI', 'PG', 'SB', 'TL', 'TV',
    'VU', 'WS',
]

# Country code → name (EN / JA)
COUNTRY_NAMES = {
    'en': {
        'AU': 'Australia', 'BN': 'Brunei', 'CA': 'Canada', 'CL': 'Chile',
        'MY': 'Malaysia', 'MX': 'Mexico', 'NZ': 'New Zealand', 'PE': 'Peru',
        'SG': 'Singapore', 'VN': 'Vietnam',
        'CN': 'China', 'KR': 'South Korea', 'KH': 'Cambodia', 'ID': 'Indonesia',
        'LA': 'Laos', 'MM': 'Myanmar', 'PH': 'Philippines', 'TH': 'Thailand',
        'AT': 'Austria', 'BE': 'Belgium', 'BG': 'Bulgaria', 'HR': 'Croatia',
        'CY': 'Cyprus', 'CZ': 'Czech Republic', 'DK': 'Denmark', 'EE': 'Estonia',
        'FI': 'Finland', 'FR': 'France', 'DE': 'Germany', 'GR': 'Greece',
        'HU': 'Hungary', 'IE': 'Ireland', 'IT': 'Italy', 'LV': 'Latvia',
        'LT': 'Lithuania', 'LU': 'Luxembourg', 'MT': 'Malta', 'NL': 'Netherlands',
        'PL': 'Poland', 'PT': 'Portugal', 'RO': 'Romania', 'SK': 'Slovakia',
        'SI': 'Slovenia', 'ES': 'Spain', 'SE': 'Sweden',
        'GB': 'United Kingdom', 'US': 'United States', 'CH': 'Switzerland',
        'IN': 'India', 'MN': 'Mongolia',
        'PK': 'Pakistan', 'BD': 'Bangladesh', 'LK': 'Sri Lanka', 'NP': 'Nepal',
        'ET': 'Ethiopia', 'TZ': 'Tanzania', 'MZ': 'Mozambique', 'SN': 'Senegal',
        'MG': 'Madagascar', 'AF': 'Afghanistan', 'HT': 'Haiti',
        'BO': 'Bolivia', 'GT': 'Guatemala', 'HN': 'Honduras', 'NI': 'Nicaragua',
        'TL': 'Timor-Leste', 'BR': 'Brazil', 'AR': 'Argentina',
        'RU': 'Russia', 'ZA': 'South Africa', 'TR': 'Turkey', 'SA': 'Saudi Arabia',
        'AE': 'UAE', 'EG': 'Egypt', 'NG': 'Nigeria', 'KE': 'Kenya',
        'CO': 'Colombia', 'EC': 'Ecuador', 'UY': 'Uruguay', 'PY': 'Paraguay',
    },
    'ja': {
        'AU': '\u30aa\u30fc\u30b9\u30c8\u30e9\u30ea\u30a2', 'BN': '\u30d6\u30eb\u30cd\u30a4',
        'CA': '\u30ab\u30ca\u30c0', 'CL': '\u30c1\u30ea',
        'MY': '\u30de\u30ec\u30fc\u30b7\u30a2', 'MX': '\u30e1\u30ad\u30b7\u30b3',
        'NZ': '\u30cb\u30e5\u30fc\u30b8\u30fc\u30e9\u30f3\u30c9', 'PE': '\u30da\u30eb\u30fc',
        'SG': '\u30b7\u30f3\u30ac\u30dd\u30fc\u30eb', 'VN': '\u30d9\u30c8\u30ca\u30e0',
        'CN': '\u4e2d\u56fd', 'KR': '\u97d3\u56fd',
        'KH': '\u30ab\u30f3\u30dc\u30b8\u30a2', 'ID': '\u30a4\u30f3\u30c9\u30cd\u30b7\u30a2',
        'LA': '\u30e9\u30aa\u30b9', 'MM': '\u30df\u30e3\u30f3\u30de\u30fc',
        'PH': '\u30d5\u30a3\u30ea\u30d4\u30f3', 'TH': '\u30bf\u30a4',
        'AT': '\u30aa\u30fc\u30b9\u30c8\u30ea\u30a2', 'BE': '\u30d9\u30eb\u30ae\u30fc',
        'BG': '\u30d6\u30eb\u30ac\u30ea\u30a2', 'HR': '\u30af\u30ed\u30a2\u30c1\u30a2',
        'CY': '\u30ad\u30d7\u30ed\u30b9', 'CZ': '\u30c1\u30a7\u30b3',
        'DK': '\u30c7\u30f3\u30de\u30fc\u30af', 'EE': '\u30a8\u30b9\u30c8\u30cb\u30a2',
        'FI': '\u30d5\u30a3\u30f3\u30e9\u30f3\u30c9', 'FR': '\u30d5\u30e9\u30f3\u30b9',
        'DE': '\u30c9\u30a4\u30c4', 'GR': '\u30ae\u30ea\u30b7\u30e3',
        'HU': '\u30cf\u30f3\u30ac\u30ea\u30fc', 'IE': '\u30a2\u30a4\u30eb\u30e9\u30f3\u30c9',
        'IT': '\u30a4\u30bf\u30ea\u30a2', 'LV': '\u30e9\u30c8\u30d3\u30a2',
        'LT': '\u30ea\u30c8\u30a2\u30cb\u30a2', 'LU': '\u30eb\u30af\u30bb\u30f3\u30d6\u30eb\u30af',
        'MT': '\u30de\u30eb\u30bf', 'NL': '\u30aa\u30e9\u30f3\u30c0',
        'PL': '\u30dd\u30fc\u30e9\u30f3\u30c9', 'PT': '\u30dd\u30eb\u30c8\u30ac\u30eb',
        'RO': '\u30eb\u30fc\u30de\u30cb\u30a2', 'SK': '\u30b9\u30ed\u30d0\u30ad\u30a2',
        'SI': '\u30b9\u30ed\u30d9\u30cb\u30a2', 'ES': '\u30b9\u30da\u30a4\u30f3',
        'SE': '\u30b9\u30a6\u30a7\u30fc\u30c7\u30f3',
        'GB': '\u30a4\u30ae\u30ea\u30b9', 'US': '\u30a2\u30e1\u30ea\u30ab',
        'CH': '\u30b9\u30a4\u30b9', 'IN': '\u30a4\u30f3\u30c9', 'MN': '\u30e2\u30f3\u30b4\u30eb',
        'PK': '\u30d1\u30ad\u30b9\u30bf\u30f3', 'BD': '\u30d0\u30f3\u30b0\u30e9\u30c7\u30b7\u30e5',
        'LK': '\u30b9\u30ea\u30e9\u30f3\u30ab', 'NP': '\u30cd\u30d1\u30fc\u30eb',
        'ET': '\u30a8\u30c1\u30aa\u30d4\u30a2', 'TZ': '\u30bf\u30f3\u30b6\u30cb\u30a2',
        'MZ': '\u30e2\u30b6\u30f3\u30d3\u30fc\u30af', 'SN': '\u30bb\u30cd\u30ac\u30eb',
        'MG': '\u30de\u30c0\u30ac\u30b9\u30ab\u30eb', 'AF': '\u30a2\u30d5\u30ac\u30cb\u30b9\u30bf\u30f3',
        'HT': '\u30cf\u30a4\u30c1',
        'BR': '\u30d6\u30e9\u30b8\u30eb', 'AR': '\u30a2\u30eb\u30bc\u30f3\u30c1\u30f3',
        'RU': '\u30ed\u30b7\u30a2', 'ZA': '\u5357\u30a2\u30d5\u30ea\u30ab',
        'TR': '\u30c8\u30eb\u30b3', 'SA': '\u30b5\u30a6\u30b8\u30a2\u30e9\u30d3\u30a2',
        'AE': 'UAE', 'EG': '\u30a8\u30b8\u30d7\u30c8',
    },
}

# Priority: bilateral > CPTPP > RCEP
_BILATERAL_EPAS = [
    'Japan-UK', 'Japan-US', 'Japan-Singapore', 'Japan-Mexico',
    'Japan-Malaysia', 'Japan-Chile', 'Japan-Thailand', 'Japan-Indonesia',
    'Japan-Brunei', 'Japan-Philippines', 'Japan-Switzerland',
    'Japan-Vietnam', 'Japan-India', 'Japan-Peru', 'Japan-Australia',
    'Japan-Mongolia',
]


def get_epa_for_country(country_code: str) -> str | None:
    """
    Return the best EPA agreement name for a country, or None.
    Priority: bilateral EPA > CPTPP > RCEP > Japan-EU
    """
    code = country_code.upper()
    # Check bilateral EPAs first
    for epa_name in _BILATERAL_EPAS:
        if code in EPA_AGREEMENTS.get(epa_name, []):
            return epa_name
    # Japan-EU
    if code in EPA_AGREEMENTS.get('Japan-EU', []):
        return 'Japan-EU'
    # CPTPP
    if code in EPA_AGREEMENTS.get('CPTPP', []):
        return 'CPTPP'
    # RCEP
    if code in EPA_AGREEMENTS.get('RCEP', []):
        return 'RCEP'
    return None


def is_gsp_country(country_code: str) -> bool:
    """Check if a country is a GSP beneficiary."""
    return country_code.upper() in GSP_BENEFICIARIES


def get_all_countries(lang: str = 'en') -> dict:
    """Return {code: name} dict for dropdown population."""
    return dict(sorted(COUNTRY_NAMES.get(lang, COUNTRY_NAMES['en']).items(),
                       key=lambda x: x[1]))


def get_countries_grouped_by_epa(lang: str = 'en') -> dict:
    """Return {agreement_name: [(code, display_name), ...]} for grouped dropdown."""
    names = COUNTRY_NAMES.get(lang, COUNTRY_NAMES['en'])
    grouped = {}
    for epa_name, codes in EPA_AGREEMENTS.items():
        entries = []
        for code in sorted(codes):
            display = names.get(code, code)
            entries.append((code, display))
        grouped[epa_name] = entries
    # Add GSP group
    gsp_entries = []
    for code in sorted(GSP_BENEFICIARIES):
        # Skip if already covered by an EPA
        if not get_epa_for_country(code):
            display = names.get(code, code)
            gsp_entries.append((code, display))
    if gsp_entries:
        grouped['GSP'] = gsp_entries
    return grouped
