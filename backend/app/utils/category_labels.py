"""Canonical display labels for UCI 697 coded categories (raw codes remain intact)."""

COURSES = {
    33: "Biofuel Production Technologies", 171: "Animation and Multimedia Design",
    8014: "Social Service (evening)", 9003: "Agronomy", 9070: "Communication Design",
    9085: "Veterinary Nursing", 9119: "Informatics Engineering",
    9130: "Equiniculture", 9147: "Management", 9238: "Social Service",
    9254: "Tourism", 9500: "Nursing", 9556: "Oral Hygiene",
    9670: "Advertising and Marketing Management", 9773: "Journalism and Communication",
    9853: "Basic Education", 9991: "Management (evening)",
}

APPLICATION_MODES = {
    1: "1st phase - general contingent", 2: "Ordinance No. 612/93",
    5: "1st phase - special contingent (Azores)",
    7: "Holders of other higher courses", 10: "Ordinance No. 854-B/99",
    15: "International student (bachelor)",
    16: "1st phase - special contingent (Madeira)",
    17: "2nd phase - general contingent", 18: "3rd phase - general contingent",
    26: "Ordinance No. 533-A/99", 27: "Ordinance No. 533-A/99 (different plan)",
    39: "Over 23 years old", 42: "Transfer", 43: "Change of course",
    44: "Technological specialization diploma holders",
    51: "Change of institution/course", 53: "Short cycle diploma holders",
    57: "Change of institution/course (international)",
}

PREVIOUS_QUALIFICATIONS = {
    1: "Secondary education", 2: "Higher education - bachelor's degree",
    3: "Higher education - degree", 4: "Higher education - master's degree",
    5: "Higher education - doctorate", 6: "Frequency of higher education",
    9: "12th year of schooling - not completed", 10: "11th year of schooling - not completed",
    12: "Other - 11th year of schooling", 14: "10th year of schooling",
    15: "10th year of schooling - not completed", 19: "Basic education 3rd cycle",
    38: "Basic education 2nd cycle", 39: "Technological specialization course",
    40: "Higher education - degree (1st cycle)",
    42: "Professional higher technical course", 43: "Higher education - master (2nd cycle)",
}


def category_label(category: str, code: int | None) -> str | None:
    if code is None:
        return None
    mapping = {"course": COURSES, "application_mode": APPLICATION_MODES,
               "previous_qualification": PREVIOUS_QUALIFICATIONS}.get(category, {})
    return mapping.get(code, str(code))
