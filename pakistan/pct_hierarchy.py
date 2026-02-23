"""
Pakistan Customs Tariff (PCT) hierarchy for display and validation.
The LLM handles search intelligence — this module handles:
  - Classification breadcrumb display
  - Parts vs Products detection
  - Heading context display
  - User education on what HS does/doesn't classify
"""

# Heading descriptions — top 200 traded headings
# Used for: displaying heading context in search results
HEADING_DESCRIPTIONS = {
    # Chapter 87 — Vehicles
    '8701': 'Tractors (other than tractors of heading 87.09)',
    '8702': 'Motor vehicles for the transport of ten or more persons, including the driver',
    '8703': 'Motor cars and other motor vehicles principally designed for the transport of persons (other than those of heading 87.02), including station wagons and racing cars',
    '8704': 'Motor vehicles for the transport of goods',
    '8705': 'Special purpose motor vehicles',
    '8708': 'Parts and accessories of the motor vehicles of headings 87.01 to 87.05',
    '8711': 'Motorcycles (including mopeds) and cycles fitted with an auxiliary motor',
    '8712': 'Bicycles and other cycles, not motorised',
    '8716': 'Trailers and semi-trailers',

    # Chapter 85 — Electronics
    '8517': 'Telephone sets, including smartphones; other apparatus for transmission or reception of voice, images or other data',
    '8471': 'Automatic data processing machines and units thereof',
    '8528': 'Monitors and projectors; reception apparatus for television',
    '8507': 'Electric accumulators, including separators therefor',
    '8541': 'Semiconductor devices; light-emitting diodes; photovoltaic cells',
    '8542': 'Electronic integrated circuits',
    '8414': 'Air or vacuum pumps; fans',
    '8415': 'Air conditioning machines',
    '8418': 'Refrigerators, freezers',
    '8450': 'Household washing machines',
    '8516': 'Electric instantaneous or storage water heaters; electric irons, hair dryers',

    # Chapter 84 — Machinery
    '8407': 'Spark-ignition internal combustion piston engines',
    '8408': 'Compression-ignition internal combustion piston engines (diesel)',
    '8413': 'Pumps for liquids',
    '8429': 'Self-propelled bulldozers, graders, scrapers, excavators',
    '8431': 'Parts for machinery of headings 84.25 to 84.30',
    '8443': 'Printing machinery; printers, copying machines, facsimile machines',
    '8474': 'Machinery for sorting, screening, mixing or kneading earth, stone, ores',

    # Food & Agriculture
    '0901': 'Coffee, whether or not roasted or decaffeinated',
    '0902': 'Tea, whether or not flavoured',
    '0910': 'Ginger, saffron, turmeric, thyme, curry and other spices',
    '1001': 'Wheat and meslin',
    '1005': 'Maize (corn)',
    '1006': 'Rice',
    '1701': 'Cane or beet sugar and chemically pure sucrose',
    '1507': 'Soya-bean oil',
    '1511': 'Palm oil',
    '1512': 'Sunflower-seed or safflower oil',
    '0713': 'Dried leguminous vegetables (lentils, chickpeas, beans)',

    # Petroleum & Chemicals
    '2709': 'Petroleum oils, crude',
    '2710': 'Petroleum oils, other than crude',
    '2711': 'Petroleum gases and other gaseous hydrocarbons',
    '3004': 'Medicaments for therapeutic or prophylactic uses, in dosage',
    '3102': 'Mineral or chemical fertilisers, nitrogenous',
    '3105': 'Mineral or chemical fertilisers containing NPK',

    # Textiles (Pakistan TOP export)
    '5201': 'Cotton, not carded or combed',
    '5208': 'Woven fabrics of cotton, >=85% cotton, <=200 g/m2',
    '5209': 'Woven fabrics of cotton, >=85% cotton, >200 g/m2',
    '5210': 'Woven fabrics of cotton, <85% cotton, mixed with man-made fibres',
    '6109': 'T-shirts, singlets and other vests, knitted or crocheted',
    '6110': 'Jerseys, pullovers, cardigans, knitted or crocheted',
    '6203': "Men's or boys' suits, jackets, trousers",
    '6204': "Women's or girls' suits, jackets, dresses, skirts",
    '6302': 'Bed linen, table linen, toilet linen and kitchen linen',
    '5701': 'Carpets and other textile floor coverings, knotted',
    '5702': 'Carpets and other textile floor coverings, woven',
    '6301': 'Blankets and travelling rugs',

    # Iron & Steel
    '7208': 'Flat-rolled products of iron/steel, >=600mm wide, hot-rolled',
    '7210': 'Flat-rolled products of iron/steel, >=600mm wide, clad/plated/coated',
    '7213': 'Bars and rods, hot-rolled, of iron or non-alloy steel',
    '7214': 'Other bars and rods of iron or non-alloy steel',
    '7304': 'Tubes, pipes and hollow profiles, seamless, of iron or steel',
    '7306': 'Other tubes, pipes and hollow profiles, of iron or steel',

    # Other key Pakistan imports
    '2523': 'Portland cement, aluminous cement, slag cement',
    '3901': 'Polymers of ethylene, in primary forms',
    '3923': 'Articles for packing of goods, of plastics',
    '4011': 'New pneumatic tyres, of rubber',
    '6403': 'Footwear with outer soles of rubber/plastics, uppers of leather',
    '7108': 'Gold, unwrought or in semi-manufactured forms',
    '7113': 'Articles of jewellery, of precious metal',
    '7601': 'Unwrought aluminium',
    '9018': 'Instruments and appliances used in medical, surgical or veterinary sciences',

    # Fruits & Produce
    '0804': 'Dates, figs, pineapples, avocados, guavas, mangoes and mangosteens',
    '0805': 'Citrus fruit, fresh or dried',
    '0808': 'Apples, pears and quinces, fresh',
    '0810': 'Other fruit, fresh',
}

# Chapter descriptions
CHAPTER_DESCRIPTIONS = {
    1: 'Live animals', 2: 'Meat and edible meat offal',
    3: 'Fish and crustaceans', 4: 'Dairy produce; eggs; honey',
    5: 'Products of animal origin', 6: 'Live trees and plants',
    7: 'Edible vegetables', 8: 'Edible fruit and nuts',
    9: 'Coffee, tea, mate and spices', 10: 'Cereals',
    11: 'Products of milling industry', 12: 'Oil seeds',
    13: 'Lac; gums, resins', 14: 'Vegetable plaiting materials',
    15: 'Animal/vegetable fats and oils', 16: 'Preparations of meat/fish',
    17: 'Sugars and confectionery', 18: 'Cocoa and cocoa preparations',
    19: 'Preparations of cereals/flour', 20: 'Preparations of vegetables/fruit',
    21: 'Miscellaneous edible preparations', 22: 'Beverages, spirits, vinegar',
    23: 'Residues from food industries', 24: 'Tobacco',
    25: 'Salt; sulphur; cement', 26: 'Ores, slag and ash',
    27: 'Mineral fuels, petroleum', 28: 'Inorganic chemicals',
    29: 'Organic chemicals', 30: 'Pharmaceutical products',
    31: 'Fertilisers', 32: 'Tanning/dyeing extracts; paints',
    33: 'Essential oils; perfumery; cosmetics', 34: 'Soap; washing preparations',
    35: 'Albuminoidal substances; glues', 36: 'Explosives',
    37: 'Photographic goods', 38: 'Miscellaneous chemical products',
    39: 'Plastics and articles thereof', 40: 'Rubber and articles thereof',
    41: 'Raw hides and skins', 42: 'Articles of leather',
    43: 'Furskins and artificial fur', 44: 'Wood and articles of wood',
    45: 'Cork', 46: 'Basketware',
    47: 'Pulp of wood', 48: 'Paper and paperboard',
    49: 'Printed books, newspapers', 50: 'Silk',
    51: 'Wool and animal hair', 52: 'Cotton',
    53: 'Other vegetable textile fibres', 54: 'Man-made filaments',
    55: 'Man-made staple fibres', 56: 'Wadding, felt, nonwovens',
    57: 'Carpets and textile floor coverings', 58: 'Special woven fabrics',
    59: 'Impregnated/coated textile fabrics', 60: 'Knitted or crocheted fabrics',
    61: 'Knitted or crocheted garments', 62: 'Non-knitted garments',
    63: 'Other made up textile articles', 64: 'Footwear',
    65: 'Headgear', 66: 'Umbrellas',
    67: 'Prepared feathers; artificial flowers', 68: 'Articles of stone/cement',
    69: 'Ceramic products', 70: 'Glass and glassware',
    71: 'Precious metals; jewellery', 72: 'Iron and steel',
    73: 'Articles of iron or steel', 74: 'Copper',
    75: 'Nickel', 76: 'Aluminium',
    78: 'Lead', 79: 'Zinc', 80: 'Tin', 81: 'Other base metals',
    82: 'Tools of base metal', 83: 'Miscellaneous articles of base metal',
    84: 'Nuclear reactors; boilers; machinery', 85: 'Electrical machinery and equipment',
    86: 'Railway locomotives', 87: 'Vehicles other than railway',
    88: 'Aircraft and spacecraft', 89: 'Ships, boats',
    90: 'Optical, measuring, medical instruments', 91: 'Clocks and watches',
    92: 'Musical instruments', 93: 'Arms and ammunition',
    94: 'Furniture; bedding; lamps', 95: 'Toys, games, sports',
    96: 'Miscellaneous manufactured articles', 97: 'Works of art; antiques',
}


def get_heading_description(hs_code):
    """Get 4-digit heading description for any HS code"""
    clean = hs_code.replace('.', '').replace('-', '').replace(' ', '')
    heading = clean[:4]
    return HEADING_DESCRIPTIONS.get(heading, '')


def get_chapter_description(hs_code):
    """Get chapter description"""
    clean = hs_code.replace('.', '').replace('-', '').replace(' ', '')
    try:
        chapter = int(clean[:2])
        return CHAPTER_DESCRIPTIONS.get(chapter, '')
    except ValueError:
        return ''


def get_classification_path(hs_code):
    """Full breadcrumb for display"""
    clean = hs_code.replace('.', '').replace('-', '').replace(' ', '')
    try:
        chapter_num = int(clean[:2])
    except ValueError:
        return {}
    heading = clean[:4]

    return {
        'section': _get_section(chapter_num),
        'chapter': f"{chapter_num:02d}",
        'chapter_desc': CHAPTER_DESCRIPTIONS.get(chapter_num, ''),
        'heading': f"{heading[:2]}.{heading[2:]}",
        'heading_desc': HEADING_DESCRIPTIONS.get(heading, ''),
        'full_code': hs_code,
    }


def is_part_not_product(description):
    """Detect if entry is a PART/ACCESSORY rather than complete product"""
    if not description:
        return False
    desc_lower = description.lower()
    part_indicators = [
        'for motor vehicles', 'parts and accessories', 'parts suitable for',
        'parts of', 'suitable for use', 'of the vehicles of',
        'of the machines of', 'for the engines of',
    ]
    return any(ind in desc_lower for ind in part_indicators)


def _get_section(chapter):
    sections = [
        (1, 5, 'I'), (6, 14, 'II'), (15, 15, 'III'), (16, 24, 'IV'),
        (25, 27, 'V'), (28, 38, 'VI'), (39, 40, 'VII'), (41, 43, 'VIII'),
        (44, 46, 'IX'), (47, 49, 'X'), (50, 63, 'XI'), (64, 67, 'XII'),
        (68, 70, 'XIII'), (71, 71, 'XIV'), (72, 83, 'XV'), (84, 85, 'XVI'),
        (86, 89, 'XVII'), (90, 92, 'XVIII'), (93, 93, 'XIX'), (94, 96, 'XX'),
        (97, 97, 'XXI'),
    ]
    for start, end, num in sections:
        if start <= chapter <= end:
            return num
    return ''
