"""
Pricing tools cho Broadcast AI.

3 bảng giá:
  - tong_hop     : QĐ 414 — áp dụng tất cả, đơn vị 10/15/20/30 giây
  - dnhp         : QĐ 415 — doanh nghiệp Hải Phòng, đơn vị 30 giây
  - tuyen_truyen : QĐ 413 — hỗ trợ tuyên truyền, tính theo phút

Dữ liệu bảng giá được load từ versioned JSON files trong app/data/pricing/.
Khi có quyết định giá mới, chỉ cần thêm file JSON mới — không sửa code.
"""

from typing import Optional
from app.services.pricing_loader import (
    get_price_dnhp,
    get_price_tong_hop,
    get_packages_dnhp,
    get_price_tuyen_truyen,
)

# Load bảng giá từ JSON files (cached sau lần đầu tiên)
PRICE_TONG_HOP: dict[str, dict] = get_price_tong_hop()
PRICE_DNHP: dict[str, int]      = get_price_dnhp()
PACKAGES_DNHP: dict[str, dict]  = get_packages_dnhp()

# ---------------------------------------------------------------------------
# Tool 1: lookup_ad_price — tra đơn giá
# ---------------------------------------------------------------------------

def lookup_ad_price(
    slot: str,
    price_list: str,
    duration_sec: int = 30,
) -> dict:
    """
    Tra đơn giá quảng cáo theo khung giờ và bảng giá.

    Args:
        slot: Mã khung giờ (vd: HP11, T1, VTV, QCFM1)
        price_list: "tong_hop" | "dnhp"
        duration_sec: Thời lượng TVC (giây) — chỉ dùng cho tong_hop

    Returns:
        dict: unit_price, slot, price_list, duration_sec, note
    """
    slot = slot.upper().strip()

    if price_list == "dnhp":
        # DNHP tính theo đơn vị 30 giây
        if slot not in PRICE_DNHP:
            return {"error": f"Không tìm thấy khung giờ '{slot}' trong bảng giá DNHP (QĐ 415)"}
        unit_price = PRICE_DNHP[slot]
        return {
            "slot": slot,
            "price_list": "dnhp",
            "unit_price": unit_price,
            "unit": "VND/30 giây/lần phát",
            "note": "Bảng giá QĐ 415 — Doanh nghiệp Hải Phòng",
        }

    elif price_list == "tong_hop":
        if slot not in PRICE_TONG_HOP:
            return {"error": f"Không tìm thấy khung giờ '{slot}' trong bảng giá tổng hợp (QĐ 414)"}

        prices = PRICE_TONG_HOP[slot]

        # Quy đổi thời lượng
        if duration_sec <= 10:
            key = "10s"
        elif duration_sec <= 15:
            key = "15s"
        elif duration_sec <= 20:
            key = "20s"
        elif duration_sec <= 30:
            key = "30s"
        elif duration_sec <= 40:
            # 40s = 30s + 10s
            unit_price = prices.get("30s", 0) + prices.get("10s", 0)
            return {
                "slot": slot,
                "price_list": "tong_hop",
                "unit_price": unit_price,
                "duration_sec": duration_sec,
                "unit": "VND/TVC",
                "note": f"40 giây = 30s ({prices.get('30s',0):,}đ) + 10s ({prices.get('10s',0):,}đ)",
            }
        elif duration_sec <= 45:
            unit_price = prices.get("30s", 0) + prices.get("15s", 0)
            return {
                "slot": slot,
                "price_list": "tong_hop",
                "unit_price": unit_price,
                "duration_sec": duration_sec,
                "unit": "VND/TVC",
                "note": f"45 giây = 30s + 15s",
            }
        elif duration_sec <= 50:
            unit_price = prices.get("30s", 0) + prices.get("20s", 0)
            return {
                "slot": slot,
                "price_list": "tong_hop",
                "unit_price": unit_price,
                "duration_sec": duration_sec,
                "unit": "VND/TVC",
                "note": f"50 giây = 30s + 20s",
            }
        elif duration_sec <= 60:
            unit_price = prices.get("30s", 0) * 2
            return {
                "slot": slot,
                "price_list": "tong_hop",
                "unit_price": unit_price,
                "duration_sec": duration_sec,
                "unit": "VND/TVC",
                "note": f"60 giây = 30s + 30s",
            }
        else:
            return {"error": f"Thời lượng {duration_sec}s vượt quá 60 giây, liên hệ trực tiếp để báo giá"}

        unit_price = prices.get(key, 0)
        return {
            "slot": slot,
            "price_list": "tong_hop",
            "unit_price": unit_price,
            "duration_sec": duration_sec,
            "unit": "VND/TVC",
            "note": "Bảng giá QĐ 414 — Tổng hợp",
        }

    else:
        return {"error": f"Bảng giá '{price_list}' không hợp lệ. Dùng: tong_hop | dnhp"}


# ---------------------------------------------------------------------------
# Tool 2: calculate_tvc_cost — tính tổng chi phí TVC
# ---------------------------------------------------------------------------

def calculate_tvc_cost(
    slot: str,
    price_list: str,
    duration_sec: int,
    times: int,
    priority_position: bool = False,
) -> dict:
    """
    Tính tổng chi phí phát sóng TVC.

    Args:
        slot: Mã khung giờ
        price_list: "tong_hop" | "dnhp"
        duration_sec: Thời lượng TVC (giây)
        times: Số lần phát
        priority_position: Vị trí ưu tiên đầu/cuối khung (+6% cho tong_hop)

    Returns:
        dict: chi tiết tính toán từng bước
    """
    # lấy đơn giá
    price_info = lookup_ad_price(slot, price_list, duration_sec)
    if "error" in price_info:
        return price_info

    unit_price = price_info["unit_price"]

    # quy đổi đơn vị cho DNHP (theo 30 giây)
    if price_list == "dnhp":
        if duration_sec <= 15:
            units = 0.5
        else:
            units = 1.0
        # Với DNHP, đơn giá đã là /30s nên nhân units
        cost_per_broadcast = unit_price * units
        duration_note = f"{duration_sec}s = {units} đơn vị × {unit_price:,}đ = {cost_per_broadcast:,.0f}đ/lần"
    else:
        # tong_hop: đơn giá đã tính đúng theo thời lượng
        cost_per_broadcast = unit_price
        duration_note = f"{duration_sec}s = {unit_price:,}đ/lần"

    # tính tổng trước phụ phí
    subtotal = cost_per_broadcast * times

    # phụ phí vị trí ưu tiên (chỉ tong_hop, +6% đơn giá 30s)
    priority_fee = 0
    if priority_position and price_list == "tong_hop":
        base_30s = PRICE_TONG_HOP.get(slot.upper(), {}).get("30s", 0)
        priority_fee = base_30s * 0.06 * times
        priority_note = f"+6% × {base_30s:,}đ × {times} lần = {priority_fee:,.0f}đ"
    else:
        priority_note = None

    total_before_discount = subtotal + priority_fee

    return {
        "slot": slot,
        "price_list": price_list,
        "duration_sec": duration_sec,
        "times": times,
        "unit_price": unit_price,
        "duration_note": duration_note,
        "subtotal": subtotal,
        "priority_fee": priority_fee,
        "priority_note": priority_note,
        "total_before_discount": total_before_discount,
        "currency": "VND",
        "vat_included": True,
    }


# ---------------------------------------------------------------------------
# Tool 3: calculate_discount — tính chiết khấu
# ---------------------------------------------------------------------------

def calculate_discount(
    total_before_discount: float,
    price_list: str,
    use_package: bool = False,
) -> dict:
    """
    Tính chiết khấu theo doanh số.

    Args:
        total_before_discount: Tổng doanh số trước chiết khấu (VND)
        price_list: "tong_hop" | "dnhp"
        use_package: Đã dùng gói → không áp dụng chiết khấu

    Returns:
        dict: tỷ lệ, số tiền chiết khấu, thành tiền
    """
    if use_package:
        return {
            "discount_rate": 0,
            "discount_amount": 0,
            "final_total": total_before_discount,
            "note": "Đã dùng giá gói → không áp dụng chiết khấu doanh số",
        }

    if price_list == "dnhp":
        # QĐ 415: chiết khấu từ 30 triệu
        if total_before_discount < 30_000_000:
            rate = 0
            note = "Dưới 30 triệu → không chiết khấu"
        elif total_before_discount < 60_000_000:
            rate = 0.05
            note = "30–60 triệu → chiết khấu 5%"
        elif total_before_discount < 100_000_000:
            rate = 0.10
            note = "60–100 triệu → chiết khấu 10%"
        elif total_before_discount < 180_000_000:
            rate = 0.15
            note = "100–180 triệu → chiết khấu 15%"
        elif total_before_discount < 360_000_000:
            rate = 0.20
            note = "180–360 triệu → chiết khấu 20%"
        else:
            rate = 0.30
            note = "Từ 360 triệu → chiết khấu 30%"

    elif price_list == "tong_hop":
        # QĐ 414: chiết khấu từ 500 triệu
        if total_before_discount < 500_000_000:
            rate = 0
            note = "Dưới 500 triệu → không chiết khấu (QĐ 414)"
        elif total_before_discount < 800_000_000:
            rate = 0.20
            note = "500–800 triệu → chiết khấu 20%"
        elif total_before_discount < 1_000_000_000:
            rate = 0.22
            note = "800 triệu–1 tỷ → chiết khấu 22%"
        else:
            rate = 0.25
            note = "Từ 1 tỷ → chiết khấu 25%"
    else:
        return {"error": f"Bảng giá '{price_list}' không hợp lệ"}

    discount_amount = total_before_discount * rate
    final_total = total_before_discount - discount_amount

    return {
        "total_before_discount": total_before_discount,
        "discount_rate": rate,
        "discount_percent": f"{rate * 100:.0f}%",
        "discount_amount": discount_amount,
        "final_total": final_total,
        "note": note,
        "currency": "VND",
        "vat_included": True,
    }


# ---------------------------------------------------------------------------
# Tool 4: check_package — kiểm tra có nên dùng gói không (chỉ DNHP)
# ---------------------------------------------------------------------------

def check_package(
    estimated_slots: int,
    estimated_total: float,
) -> dict:
    """
    So sánh giá gói vs giá lẻ cho DNHP.
    Chỉ áp dụng QĐ 415.

    Args:
        estimated_slots: Số lần phát dự kiến
        estimated_total: Tổng chi phí nếu mua lẻ (VND)

    Returns:
        dict: so sánh các gói, gợi ý gói phù hợp nhất
    """
    recommendations = []

    for pkg_name, pkg in PACKAGES_DNHP.items():
        if estimated_slots <= pkg["slots"]:
            saving = estimated_total - pkg["price"]
            recommendations.append({
                "package": pkg_name,
                "package_price": pkg["price"],
                "included_slots": pkg["slots"],
                "banner_weeks": pkg["banner_weeks"],
                "max_days": pkg["max_days"],
                "saving_vs_retail": saving,
                "is_cheaper": saving > 0,
                "note": f"Tiết kiệm {saving:,.0f}đ so với mua lẻ" if saving > 0 else f"Đắt hơn mua lẻ {-saving:,.0f}đ",
            })

    if not recommendations:
        return {
            "use_package": False,
            "note": f"Số lần phát {estimated_slots} vượt quá gói lớn nhất (300 lần). Liên hệ để báo giá riêng.",
        }

    # Gói rẻ nhất phù hợp
    best = min(
        [r for r in recommendations if r["is_cheaper"]],
        key=lambda x: x["package_price"],
        default=None,
    )

    return {
        "estimated_slots": estimated_slots,
        "estimated_retail_total": estimated_total,
        "options": recommendations,
        "recommendation": best["package"] if best else None,
        "use_package": best is not None,
        "note": f"Nên dùng {best['package']}" if best else "Mua lẻ sẽ rẻ hơn",
    }


# ---------------------------------------------------------------------------
# Tool 5: calculate_documentary_cost — tính chi phí phóng sự/phim tài liệu
# QĐ 413 — hỗ trợ tuyên truyền, tính theo phút
# ---------------------------------------------------------------------------

PRICE_TUYEN_TRUYEN: dict[str, int] = get_price_tuyen_truyen()


def calculate_documentary_cost(
    content_type: str,
    channel: str,
    slot_type: str,
    duration_min: int,
    self_provided_file: bool = False,
) -> dict:
    """
    Tính chi phí phóng sự / phim tài liệu (QĐ 413).

    Args:
        content_type: "phong_su" | "phim_tai_lieu" | "phong_su_tai_lieu"
        channel: "THP" | "THP3"
        slot_type: "thuong" (giờ thường) | "toi" (sau thời sự tối)
        duration_min: Thời lượng phút (10, 15, 20, 30)
        self_provided_file: Tự cung cấp file → tính 50%

    Returns:
        dict: chi tiết chi phí
    """
    type_map = {
        "phong_su": "phong_su",
        "phim_tai_lieu": "ptl",
        "phong_su_tai_lieu": "phong_su",
    }
    prefix = type_map.get(content_type)
    if not prefix:
        return {"error": f"Loại nội dung '{content_type}' không hợp lệ"}

    key = f"{prefix}_{channel}_{slot_type}_{duration_min}p"
    if key not in PRICE_TUYEN_TRUYEN:
        return {"error": f"Không tìm thấy mức giá cho: {content_type} / {channel} / {slot_type} / {duration_min} phút"}

    base_price = PRICE_TUYEN_TRUYEN[key]
    final_price = base_price * 0.5 if self_provided_file else base_price

    return {
        "content_type": content_type,
        "channel": channel,
        "slot_type": slot_type,
        "duration_min": duration_min,
        "base_price": base_price,
        "self_provided_file": self_provided_file,
        "final_price": final_price,
        "discount_note": "Tự cung cấp file → tính 50% đơn giá" if self_provided_file else None,
        "price_list": "tuyen_truyen",
        "regulation": "QĐ 413/QĐ-BPTTH",
        "currency": "VND",
        "vat_included": True,
    }


# ---------------------------------------------------------------------------
# Registry — LangChain tool definitions sẽ import từ đây
# ---------------------------------------------------------------------------

TOOL_FUNCTIONS = {
    "lookup_ad_price": lookup_ad_price,
    "calculate_tvc_cost": calculate_tvc_cost,
    "calculate_discount": calculate_discount,
    "check_package": check_package,
    "calculate_documentary_cost": calculate_documentary_cost,
}