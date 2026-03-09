from typing import Optional


KEYWORD_CATEGORY_MAP = {
    "food": ["swiggy", "zomato", "dominos", "pizza", "burger", "restaurant", "cafe"],
    "transport": ["uber", "ola", "metro", "bus", "train", "fuel", "petrol", "diesel"],
    "rent": ["rent", "landlord", "lease"],
    "shopping": ["amazon", "flipkart", "mall", "shopping"],
    "salary": ["salary", "payroll", "bonus"],
    "other": [],
}


def suggest_category(description: str) -> Optional[str]:
    if not description:
        return None
    value = description.lower()
    for category, keywords in KEYWORD_CATEGORY_MAP.items():
        if any(keyword in value for keyword in keywords):
            return category
    return None
