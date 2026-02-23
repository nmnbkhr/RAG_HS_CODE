"""Bilingual EN/JP string dictionary for Japan Customs Calculator."""

STRINGS = {
    'en': {
        # App
        'app_title': 'Japan Customs Duty Calculator',
        'app_subtitle': 'HS Code Classification & Import Duty Calculation',
        'app_badge': 'FY 2025-26 | Japan Customs Tariff',

        # Tabs
        'tab_lookup': 'HS Code Lookup',
        'tab_calc': 'Import Duty Calculator',

        # Sidebar
        'sidebar_language': 'Language',
        'sidebar_fx_title': 'Exchange Rate',
        'sidebar_about_title': 'About',
        'sidebar_about_text': (
            'Japan Customs tariff data from customs.go.jp. '
            'Supports EPA/FTA, GSP, WTO, and General tariff rates.'
        ),
        'sidebar_links_title': 'Official Resources',
        'sidebar_disclaimer': (
            'This tool provides estimates for reference only. '
            'For official assessments, verify with Japan Customs (customs.go.jp).'
        ),

        # Lookup tab
        'lookup_header': 'HS Code Lookup & Classification',
        'lookup_caption': 'Search Japan Customs Tariff by 9-digit HS code or item description',
        'lookup_input_label': 'Search HS Code or Item Description',
        'lookup_input_placeholder': "Enter HS code (e.g., 0901.21-010) or item name (e.g., 'green tea')",
        'lookup_search_btn': 'Search',
        'lookup_examples': 'Quick Examples:',
        'lookup_results': 'Search Results',
        'lookup_no_results': 'No results found',
        'lookup_use_in_calc': 'Use in Calculator',
        'lookup_data_saved': 'Data saved! Switch to Import Duty Calculator tab.',

        # Lookup result labels
        'hs_code': 'HS Code',
        'description_en': 'Description (EN)',
        'description_jp': 'Description (JP)',
        'unit': 'Unit',
        'general_rate': 'General Rate',
        'wto_rate': 'WTO Rate',
        'temporary_rate': 'Temporary Rate',
        'gsp_rate': 'GSP Rate',
        'epa_rate': 'EPA Rate',
        'rate_columns': 'Tariff Rate Columns',
        'consumption_tax_indicator': 'Consumption Tax',
        'standard_rate_label': '10% (Standard)',
        'reduced_rate_label': '8% (Reduced - Food)',

        # Calculator tab
        'calc_header': 'Import Duty Calculator',
        'calc_caption': 'Calculate customs duties and taxes for imports into Japan',
        'calc_hs_section': '1. HS Code',
        'calc_hs_input': 'HS Code',
        'calc_hs_placeholder': 'e.g., 0901.21-010',
        'calc_fetch_btn': 'Fetch',
        'calc_country_section': '2. Country of Origin',
        'calc_country_label': 'Country of Origin',
        'calc_country_none': 'Select country...',
        'calc_epa_badge_yes': 'EPA: {}',
        'calc_epa_badge_no': 'No EPA Agreement',
        'calc_gsp_badge': 'GSP Eligible',
        'calc_values_section': '3. Values',
        'calc_fob': 'FOB Value',
        'calc_freight': 'Freight',
        'calc_insurance': 'Insurance',
        'calc_currency': 'Currency',
        'calc_quantity': 'Quantity',
        'calc_unit': 'Unit',
        'calc_manual_fx': 'Exchange Rate (optional)',
        'calc_manual_fx_help': 'Leave at 0 to auto-fetch rate',
        'calc_simplified_checkbox': 'Use Simplified Tariff (CIF < JPY 200,000)',
        'calc_btn': 'Calculate Duties & Taxes',
        'calc_error_inputs': 'Please provide valid HS code, quantity, and FOB value.',

        # Results
        'results_header': 'Calculation Results',
        'results_cif': 'CIF Value',
        'results_duty': 'Customs Duty',
        'results_tax': 'Consumption Tax',
        'results_total': 'Total Landed Cost',
        'results_fx_rate': 'FX Rate',
        'results_breakdown': 'Duty Breakdown',
        'results_rate_comparison': 'Rate Comparison',

        # Breakdown table
        'breakdown_fob': 'FOB Value',
        'breakdown_freight': 'Freight',
        'breakdown_insurance': 'Insurance',
        'breakdown_cif_foreign': 'CIF Value (Foreign)',
        'breakdown_cif_jpy': 'CIF Value (JPY)',
        'breakdown_applied_rate': 'Applied Rate',
        'breakdown_customs_duty': 'Customs Duty',
        'breakdown_excise': 'Excise Tax',
        'breakdown_excise_na': 'N/A',
        'breakdown_consumption_tax': 'Consumption Tax ({}%)',
        'breakdown_total': 'Total Landed Cost',
        'breakdown_simplified_note': '(Simplified Tariff Applied)',

        # Rate comparison table
        'rate_agreement': 'Agreement',
        'rate_value': 'Rate',
        'rate_status': 'Status',
        'rate_applied': 'Applied',
        'rate_not_applied': '\u2014',
        'rate_not_available': '\u2014',

        # Duty types
        'duty_ad_valorem': 'Ad Valorem',
        'duty_specific': 'Specific',
        'duty_combined': 'Combined',
        'duty_free': 'Free',

        # Country groups
        'group_cptpp': 'CPTPP',
        'group_rcep': 'RCEP',
        'group_eu': 'Japan-EU EPA',
        'group_bilateral': 'Bilateral EPA',
        'group_gsp': 'GSP Countries',
        'group_other': 'Other Countries',

        # Error messages
        'error_system_init': 'System not initialized. Please refresh the page.',
        'error_hs_not_found': 'HS code not found in tariff database.',
        'error_fetch_failed': 'Failed to fetch tariff data.',
        'error_invalid_hs': 'Invalid HS code format.',
        'error_no_rates': 'No rate data available for this code.',

        # Footer
        'footer_title': 'Japan Customs \u2014 HS Code & Import Duty Calculator',
        'footer_formula': 'Import: CIF Basis | Customs Duty + Excise + Consumption Tax (10%/8%)',
        'footer_sources': 'Data Sources: Japan Customs (customs.go.jp)',
        'footer_disclaimer': (
            'Japan Customs Tariff FY 2025-26. For official assessments, '
            'verify with Japan Customs (customs.go.jp). '
            'This tool provides estimates for reference only.'
        ),
    },

    'ja': {
        # App
        'app_title': '\u65e5\u672c\u7a0e\u95a2\u95a2\u7a0e\u8a08\u7b97\u6a5f',
        'app_subtitle': 'HS\u30b3\u30fc\u30c9\u5206\u985e\u30fb\u8f38\u5165\u95a2\u7a0e\u8a08\u7b97',
        'app_badge': '\u4ee4\u548c7\u5e74\u5ea6 | \u65e5\u672c\u7a0e\u95a2\u95a2\u7a0e\u7387\u8868',

        # Tabs
        'tab_lookup': 'HS\u30b3\u30fc\u30c9\u691c\u7d22',
        'tab_calc': '\u8f38\u5165\u95a2\u7a0e\u8a08\u7b97',

        # Sidebar
        'sidebar_language': '\u8a00\u8a9e',
        'sidebar_fx_title': '\u70ba\u66ff\u30ec\u30fc\u30c8',
        'sidebar_about_title': '\u3053\u306e\u30c4\u30fc\u30eb\u306b\u3064\u3044\u3066',
        'sidebar_about_text': (
            '\u7a0e\u95a2\u306e\u95a2\u7a0e\u7387\u30c7\u30fc\u30bf\u306fcustoms.go.jp\u306b\u57fa\u3065\u3044\u3066\u3044\u307e\u3059\u3002'
            'EPA/FTA\u3001GSP\u3001WTO\u3001\u4e00\u822c\u7a0e\u7387\u306b\u5bfe\u5fdc\u3057\u3066\u3044\u307e\u3059\u3002'
        ),
        'sidebar_links_title': '\u516c\u5f0f\u30ea\u30bd\u30fc\u30b9',
        'sidebar_disclaimer': (
            '\u3053\u306e\u30c4\u30fc\u30eb\u306f\u53c2\u8003\u60c5\u5831\u3067\u3059\u3002'
            '\u7a0e\u95a2\uff08customs.go.jp\uff09\u3067\u3054\u78ba\u8a8d\u304f\u3060\u3055\u3044\u3002'
        ),

        # Lookup tab
        'lookup_header': 'HS\u30b3\u30fc\u30c9\u691c\u7d22\u30fb\u5206\u985e',
        'lookup_caption': '9\u6841HS\u30b3\u30fc\u30c9\u307e\u305f\u306f\u54c1\u540d\u3067\u65e5\u672c\u7a0e\u95a2\u95a2\u7a0e\u7387\u8868\u3092\u691c\u7d22',
        'lookup_input_label': 'HS\u30b3\u30fc\u30c9\u307e\u305f\u306f\u54c1\u540d\u3092\u5165\u529b',
        'lookup_input_placeholder': 'HS\u30b3\u30fc\u30c9\uff08\u4f8b: 0901.21-010\uff09\u307e\u305f\u306f\u54c1\u540d\uff08\u4f8b: \u7dd1\u8336\uff09',
        'lookup_search_btn': '\u691c\u7d22',
        'lookup_examples': '\u30af\u30a4\u30c3\u30af\u4f8b:',
        'lookup_results': '\u691c\u7d22\u7d50\u679c',
        'lookup_no_results': '\u7d50\u679c\u304c\u898b\u3064\u304b\u308a\u307e\u305b\u3093',
        'lookup_use_in_calc': '\u8a08\u7b97\u6a5f\u3067\u4f7f\u7528',
        'lookup_data_saved': '\u30c7\u30fc\u30bf\u4fdd\u5b58\u6e08\u307f\uff01\u8f38\u5165\u95a2\u7a0e\u8a08\u7b97\u30bf\u30d6\u306b\u5207\u308a\u66ff\u3048\u3066\u304f\u3060\u3055\u3044\u3002',

        # Lookup result labels
        'hs_code': 'HS\u30b3\u30fc\u30c9',
        'description_en': '\u54c1\u540d\uff08\u82f1\u8a9e\uff09',
        'description_jp': '\u54c1\u540d\uff08\u65e5\u672c\u8a9e\uff09',
        'unit': '\u5358\u4f4d',
        'general_rate': '\u4e00\u822c\u7a0e\u7387',
        'wto_rate': 'WTO\u7a0e\u7387',
        'temporary_rate': '\u6682\u5b9a\u7a0e\u7387',
        'gsp_rate': '\u7279\u6075\u7a0e\u7387',
        'epa_rate': 'EPA\u7a0e\u7387',
        'rate_columns': '\u95a2\u7a0e\u7387\u4e00\u89a7',
        'consumption_tax_indicator': '\u6d88\u8cbb\u7a0e',
        'standard_rate_label': '10%\uff08\u6a19\u6e96\u7a0e\u7387\uff09',
        'reduced_rate_label': '8%\uff08\u8efd\u6e1b\u7a0e\u7387\u30fb\u98df\u54c1\uff09',

        # Calculator tab
        'calc_header': '\u8f38\u5165\u95a2\u7a0e\u8a08\u7b97',
        'calc_caption': '\u65e5\u672c\u3078\u306e\u8f38\u5165\u54c1\u306e\u95a2\u7a0e\u30fb\u7a0e\u91d1\u3092\u8a08\u7b97',
        'calc_hs_section': '1. HS\u30b3\u30fc\u30c9',
        'calc_hs_input': 'HS\u30b3\u30fc\u30c9',
        'calc_hs_placeholder': '\u4f8b: 0901.21-010',
        'calc_fetch_btn': '\u53d6\u5f97',
        'calc_country_section': '2. \u539f\u7523\u56fd',
        'calc_country_label': '\u539f\u7523\u56fd',
        'calc_country_none': '\u56fd\u3092\u9078\u629e...',
        'calc_epa_badge_yes': 'EPA: {}',
        'calc_epa_badge_no': 'EPA\u5354\u5b9a\u306a\u3057',
        'calc_gsp_badge': '\u7279\u6075\u95a2\u7a0e\u5bfe\u8c61',
        'calc_values_section': '3. \u4fa1\u683c\u60c5\u5831',
        'calc_fob': 'FOB\u4fa1\u683c',
        'calc_freight': '\u904b\u8cc3',
        'calc_insurance': '\u4fdd\u967a',
        'calc_currency': '\u901a\u8ca8',
        'calc_quantity': '\u6570\u91cf',
        'calc_unit': '\u5358\u4f4d',
        'calc_manual_fx': '\u70ba\u66ff\u30ec\u30fc\u30c8\uff08\u4efb\u610f\uff09',
        'calc_manual_fx_help': '0\u306e\u307e\u307e\u3067\u81ea\u52d5\u53d6\u5f97',
        'calc_simplified_checkbox': '\u7c21\u6613\u7a0e\u7387\u3092\u4f7f\u7528\uff08CIF 20\u4e07\u5186\u672a\u6e80\uff09',
        'calc_btn': '\u95a2\u7a0e\u30fb\u7a0e\u91d1\u3092\u8a08\u7b97',
        'calc_error_inputs': '\u6709\u52b9\u306aHS\u30b3\u30fc\u30c9\u3001\u6570\u91cf\u3001FOB\u4fa1\u683c\u3092\u5165\u529b\u3057\u3066\u304f\u3060\u3055\u3044\u3002',

        # Results
        'results_header': '\u8a08\u7b97\u7d50\u679c',
        'results_cif': 'CIF\u4fa1\u683c',
        'results_duty': '\u95a2\u7a0e',
        'results_tax': '\u6d88\u8cbb\u7a0e',
        'results_total': '\u7dcf\u8f38\u5165\u539f\u4fa1',
        'results_fx_rate': '\u70ba\u66ff\u30ec\u30fc\u30c8',
        'results_breakdown': '\u8a08\u7b97\u5185\u8a33',
        'results_rate_comparison': '\u7a0e\u7387\u6bd4\u8f03',

        # Breakdown table
        'breakdown_fob': 'FOB\u4fa1\u683c',
        'breakdown_freight': '\u904b\u8cc3',
        'breakdown_insurance': '\u4fdd\u967a',
        'breakdown_cif_foreign': 'CIF\u4fa1\u683c\uff08\u5916\u8ca8\uff09',
        'breakdown_cif_jpy': 'CIF\u4fa1\u683c\uff08\u5186\uff09',
        'breakdown_applied_rate': '\u9069\u7528\u7a0e\u7387',
        'breakdown_customs_duty': '\u95a2\u7a0e',
        'breakdown_excise': '\u7279\u5225\u7a0e',
        'breakdown_excise_na': '\u8a72\u5f53\u306a\u3057',
        'breakdown_consumption_tax': '\u6d88\u8cbb\u7a0e ({}%)',
        'breakdown_total': '\u7dcf\u8f38\u5165\u539f\u4fa1',
        'breakdown_simplified_note': '\uff08\u7c21\u6613\u7a0e\u7387\u9069\u7528\uff09',

        # Rate comparison table
        'rate_agreement': '\u5354\u5b9a',
        'rate_value': '\u7a0e\u7387',
        'rate_status': '\u30b9\u30c6\u30fc\u30bf\u30b9',
        'rate_applied': '\u9069\u7528\u4e2d',
        'rate_not_applied': '\u2014',
        'rate_not_available': '\u2014',

        # Duty types
        'duty_ad_valorem': '\u5f93\u4fa1\u7a0e',
        'duty_specific': '\u5f93\u91cf\u7a0e',
        'duty_combined': '\u8907\u5408\u7a0e',
        'duty_free': '\u7121\u7a0e',

        # Country groups
        'group_cptpp': 'CPTPP',
        'group_rcep': 'RCEP',
        'group_eu': '\u65e5EU\u30fbEPA',
        'group_bilateral': '\u4e8c\u56fd\u9593EPA',
        'group_gsp': '\u7279\u6075\u53d7\u76ca\u56fd',
        'group_other': '\u305d\u306e\u4ed6\u306e\u56fd',

        # Error messages
        'error_system_init': '\u30b7\u30b9\u30c6\u30e0\u304c\u521d\u671f\u5316\u3055\u308c\u3066\u3044\u307e\u305b\u3093\u3002\u30da\u30fc\u30b8\u3092\u66f4\u65b0\u3057\u3066\u304f\u3060\u3055\u3044\u3002',
        'error_hs_not_found': '\u95a2\u7a0e\u7387\u30c7\u30fc\u30bf\u30d9\u30fc\u30b9\u306bHS\u30b3\u30fc\u30c9\u304c\u898b\u3064\u304b\u308a\u307e\u305b\u3093\u3002',
        'error_fetch_failed': '\u95a2\u7a0e\u30c7\u30fc\u30bf\u306e\u53d6\u5f97\u306b\u5931\u6557\u3057\u307e\u3057\u305f\u3002',
        'error_invalid_hs': 'HS\u30b3\u30fc\u30c9\u306e\u5f62\u5f0f\u304c\u7121\u52b9\u3067\u3059\u3002',
        'error_no_rates': '\u3053\u306e\u30b3\u30fc\u30c9\u306e\u7a0e\u7387\u30c7\u30fc\u30bf\u304c\u3042\u308a\u307e\u305b\u3093\u3002',

        # Footer
        'footer_title': '\u65e5\u672c\u7a0e\u95a2 \u2014 HS\u30b3\u30fc\u30c9\u30fb\u8f38\u5165\u95a2\u7a0e\u8a08\u7b97\u6a5f',
        'footer_formula': '\u8f38\u5165: CIF\u30d9\u30fc\u30b9 | \u95a2\u7a0e + \u7279\u5225\u7a0e + \u6d88\u8cbb\u7a0e (10%/8%)',
        'footer_sources': '\u30c7\u30fc\u30bf\u30bd\u30fc\u30b9: \u7a0e\u95a2 (customs.go.jp)',
        'footer_disclaimer': (
            '\u65e5\u672c\u7a0e\u95a2\u95a2\u7a0e\u7387\u8868 \u4ee4\u548c7\u5e74\u5ea6\u3002'
            '\u516c\u5f0f\u306e\u8a55\u4fa1\u306b\u3064\u3044\u3066\u306f\u3001\u7a0e\u95a2\uff08customs.go.jp\uff09\u3067\u3054\u78ba\u8a8d\u304f\u3060\u3055\u3044\u3002'
            '\u3053\u306e\u30c4\u30fc\u30eb\u306f\u53c2\u8003\u60c5\u5831\u306e\u307f\u3092\u63d0\u4f9b\u3057\u307e\u3059\u3002'
        ),
    },
}


def t(key: str, lang: str = 'en') -> str:
    """Get translated string by key and language code."""
    return STRINGS.get(lang, STRINGS['en']).get(key, STRINGS['en'].get(key, key))
