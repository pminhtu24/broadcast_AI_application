"""
Pricing Loader — load và cache bảng giá từ versioned JSON files.

Cơ chế versioning:
  - Mỗi bảng giá lưu trong file riêng: price_{name}_v{year}.json
  - Mỗi file có metadata.effective_date
  - Loader tự chọn file có effective_date mới nhất nhưng không vượt quá ngày hôm nay
  - Data được cache in-memory sau lần load đầu tiên (singleton pattern)

Ví dụ: Khi có QĐ mới năm 2027, chỉ cần thêm price_dnhp_v2027.json.
File cũ giữ nguyên để audit và rollback.
"""

import json
import logging
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).parent.parent / "data" / "pricing"


def _find_active_file(pattern: str) -> Path:
    """
    Tìm file JSON active theo pattern, chọn effective_date mới nhất
    mà không vượt quá ngày hôm nay.

    Args:
        pattern: glob pattern, vd "price_dnhp_v*.json"

    Returns:
        Path đến file active

    Raises:
        FileNotFoundError: Nếu không tìm thấy file nào phù hợp
    """
    today = date.today()
    candidates = []

    for path in sorted(_DATA_DIR.glob(pattern)):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            effective_date = date.fromisoformat(
                data["metadata"]["effective_date"]
            )
            if effective_date <= today:
                candidates.append((effective_date, path, data))
        except (KeyError, ValueError, json.JSONDecodeError) as e:
            logger.warning(f"[PricingLoader] Bỏ qua file lỗi {path.name}: {e}")

    if not candidates:
        raise FileNotFoundError(
            f"[PricingLoader] Không tìm thấy file bảng giá active: {pattern}"
        )

    # Chọn file có effective_date mới nhất
    candidates.sort(key=lambda x: x[0], reverse=True)
    effective_date, path, _ = candidates[0]
    logger.info(
        f"[PricingLoader] Active: {path.name} (effective: {effective_date})"
    )
    return path


def _load_json(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Public API — mỗi hàm cache kết quả sau lần gọi đầu tiên
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_price_dnhp() -> dict[str, int]:
    """
    Trả về dict bảng giá DNHP (QĐ 415).
    Format: {"HP8": 500000, ...}
    """
    path = _find_active_file("price_dnhp_v*.json")
    data = _load_json(path)
    prices = {k: int(v) for k, v in data["prices"].items()}
    logger.info(f"[PricingLoader] Loaded DNHP: {len(prices)} slots")
    return prices


@lru_cache(maxsize=1)
def get_price_tong_hop() -> dict[str, dict]:
    """
    Trả về dict bảng giá tổng hợp (QĐ 414).
    Format: {"T1": {"10s": 10000000, "15s": 13000000, ...}, ...}
    """
    path = _find_active_file("price_tong_hop_v*.json")
    data = _load_json(path)
    prices = {
        slot: {k: int(v) for k, v in durations.items()}
        for slot, durations in data["prices"].items()
    }
    logger.info(f"[PricingLoader] Loaded tong_hop: {len(prices)} slots")
    return prices


@lru_cache(maxsize=1)
def get_packages_dnhp() -> dict[str, dict]:
    """
    Trả về dict gói tích hợp DNHP.
    Format: {"goi_1": {"price": 30000000, "slots": 75, ...}, ...}
    """
    path = _find_active_file("packages_dnhp_v*.json")
    data = _load_json(path)
    logger.info(f"[PricingLoader] Loaded packages: {len(data['packages'])} gói")
    return data["packages"]


@lru_cache(maxsize=1)
def get_price_tuyen_truyen() -> dict[str, int]:
    """
    Trả về dict bảng giá tuyên truyền (QĐ 413).
    Format: {"phong_su_THP_toi_15p": 75000000, ...}
    """
    path = _find_active_file("price_tuyen_truyen_v*.json")
    data = _load_json(path)
    prices = {k: int(v) for k, v in data["prices"].items()}
    logger.info(f"[PricingLoader] Loaded tuyen_truyen: {len(prices)} entries")
    return prices


@lru_cache(maxsize=4)
def get_active_metadata(price_list_name: str) -> dict:
    """
    Trả về metadata của bảng giá đang active.
    Dùng để log, debug, hoặc expose qua API.

    Args:
        price_list_name: "dnhp" | "tong_hop" | "packages_dnhp" | "tuyen_truyen"
    """
    pattern_map = {
        "dnhp":          "price_dnhp_v*.json",
        "tong_hop":      "price_tong_hop_v*.json",
        "packages_dnhp": "packages_dnhp_v*.json",
        "tuyen_truyen":  "price_tuyen_truyen_v*.json",
    }
    pattern = pattern_map.get(price_list_name)
    if not pattern:
        return {"error": f"Unknown price_list_name: {price_list_name}"}

    path = _find_active_file(pattern)
    data = _load_json(path)
    return data.get("metadata", {})
