"""
Define LangChain tools from pricing_tools.py.
The LLM will read this schema to know when to call which tool and what parameters to pass.
"""

from langchain_core.tools import tool
from app.services.pricing_tools import (
    lookup_ad_price,
    calculate_tvc_cost,
    calculate_discount,
    check_package,
    calculate_documentary_cost,
)


@tool
def tool_lookup_ad_price(slot: str, price_list: str, duration_sec: int = 30) -> dict:
    """
    Tra đơn giá quảng cáo theo khung giờ và bảng giá.
    Dùng khi cần biết giá của một khung giờ cụ thể trước khi tính toán.

    Args:
        slot: Mã khung giờ. Ví dụ:
              - Bảng DNHP (QĐ 415): HP1..HP14, HD1..HD17,
              - Bảng tổng hợp (QĐ 414): S1..S9, C3..C4, TVTV, 
              - Phát thanh: QCFM1..QCFM5, QCFMGT1..QCFMGT4
        price_list: Bảng giá áp dụng "tong_hop" hoặc "dnhp"
        duration_sec: Thời lượng TVC tính bằng giây (default 30).
                      Chỉ có tác dụng với bảng tong_hop.
    """
    return lookup_ad_price(slot, price_list, duration_sec)


@tool
def tool_calculate_tvc_cost(
    slot: str,
    price_list: str,
    duration_sec: int,
    times: int,
    priority_position: bool = False,
) -> dict:
    """
    Tính tổng chi phí phát sóng TVC (trước chiết khấu).
    Dùng khi khách hàng muốn biết tổng tiền cho một chiến dịch quảng cáo.

    Args:
        slot: Mã khung giờ (xem tool_lookup_ad_price để biết danh sách)
        price_list: "tong_hop" hoặc "dnhp"
        duration_sec: Thời lượng TVC tính bằng giây (10, 15, 20, 30, 45, 60)
        times: Số lần phát sóng
        priority_position: True nếu muốn vị trí ưu tiên đầu/cuối khung QC (+6%)
    """
    return calculate_tvc_cost(slot, price_list, duration_sec, times, priority_position)


@tool
def tool_calculate_discount(
    total_before_discount: float,
    price_list: str,
    use_package: bool = False,
) -> dict:
    """
    Tính chiết khấu doanh số và thành tiền cuối cùng.
    Luôn gọi tool này SAU khi đã tính xong tổng chi phí.

    Args:
        total_before_discount: Tổng doanh số trước chiết khấu (VND)
        price_list: "tong_hop" hoặc "dnhp"
        use_package: True nếu khách đang dùng gói → không áp chiết khấu doanh số
    """
    return calculate_discount(total_before_discount, price_list, use_package)


@tool
def tool_check_package(
    estimated_slots: int,
    estimated_total: float,
) -> dict:
    """
    So sánh giá gói tích hợp vs giá lẻ để tư vấn cho khách hàng.
    CHỈ áp dụng cho khách hàng doanh nghiệp Hải Phòng (QĐ 415).
    Dùng khi khách hàng có nhu cầu phát nhiều lần hoặc hỏi về gói.

    Args:
        estimated_slots: Số lần phát dự kiến
        estimated_total: Tổng chi phí nếu mua lẻ (VND)
    """
    return check_package(estimated_slots, estimated_total)


@tool
def tool_calculate_documentary_cost(
    content_type: str,
    channel: str,
    slot_type: str,
    duration_min: int,
    self_provided_file: bool = False,
) -> dict:
    """
    Tính chi phí sản xuất và phát sóng phóng sự / phim tài liệu (QĐ 413).
    Dùng khi khách hàng hỏi về phóng sự tuyên truyền, không phải TVC thông thường.

    Args:
        content_type: Loại nội dung — "phong_su" | "phim_tai_lieu" | "phong_su_tai_lieu"
        channel: Kênh phát sóng — "THP" hoặc "THP3"
        slot_type: Khung giờ — "thuong" (giờ thường) hoặc "toi" (sau thời sự tối)
        duration_min: Thời lượng phút — 10, 15, 20 hoặc 30
        self_provided_file: True nếu đơn vị tự cung cấp file phát sóng (giảm 50%)
    """
    return calculate_documentary_cost(
        content_type, channel, slot_type, duration_min, self_provided_file
    )


# Export danh sách tools để dùng trong node
ALL_PRICING_TOOLS = [
    tool_lookup_ad_price,
    tool_calculate_tvc_cost,
    tool_calculate_discount,
    tool_check_package,
    tool_calculate_documentary_cost,
]