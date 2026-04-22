from typing import Union


def format_currency(amount: Union[int, float], suffix: str = "đồng") -> str:
    """
    Format số tiền: 5000000 → '5.000.000 đồng'
    """
    if amount is None:
        return "0 đồng"
    return f"{int(amount):,}".replace(",", ".") + f" {suffix}"


def format_currency_vnd(amount: Union[int, float]) -> str:
    """
    Format số tiền VND: 5000000 → '5.000.000 đồng'
    """
    return format_currency(amount, "đồng")


def parse_currency(text: str) -> float:
    """
    Parse chuỗi tiền về số: '5.000.000 đồng' → 5000000
    """
    if not text:
        return 0.0
    cleaned = text.replace(" đồng", "").replace("đồng", "").replace(".", "").replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return 0.0