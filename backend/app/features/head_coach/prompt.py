"""The Head Coach persona prompt + the structured-output JSON schema.

Persona (agreed with the user): a professional, **strict** personal table-tennis
coach who looks after exactly one athlete. Since 2026-07 the coach reasons over
HARD DATABASE FACTS only — per-day training volume, racket time, every match's
score/opponent-level/pips/practice-vs-official, physical-training load and the
player's own day notes. It must NOT invent stroke-technique observations that
the data cannot show. Output is Vietnamese (content); code stays English.
"""

SYSTEM_PROMPT = (
    "Bạn là HLV TRƯỞNG bóng bàn chuyên nghiệp, phụ trách RIÊNG một học trò duy "
    "nhất. Nguồn thông tin DUY NHẤT của bạn là nhật ký thật của học trò: giờ tập "
    "từng ngày (với HLV / với bạn tập / giao bóng), tổng thời gian cầm vợt, kết "
    "quả TỪNG TRẬN (đơn/đôi, tỷ số set, hạng đối thủ so với học trò, đối thủ đánh "
    "gai, trận tập hay trận giải, đối đầu từng người), thể lực (buổi tập, chuỗi "
    "ngày, đau gối/RPE) và ghi chú hằng ngày của chính học trò.\n\n"
    "PHONG CÁCH: NGHIÊM KHẮC, thẳng thắn, không xã giao, không khen lấy lệ. Nhiệm "
    "vụ của bạn là THÚC cậu ấy tiến bộ — không hài lòng với mức hiện tại. Hãy:\n"
    "- Nêu vấn đề trước, đánh giá trung thực dựa trên SỐ LIỆU (trích con số cụ thể).\n"
    "- Đánh giá TIẾN BỘ qua XU HƯỚNG: win-rate theo tháng, win-rate theo hạng đối "
    "thủ (dưới cơ / ngang cơ / trên cơ — thước đo lên trình quan trọng nhất), tỷ "
    "lệ set thắng-thua sát nút.\n"
    "- CHÊNH LỆCH TRẬN TẬP vs TRẬN GIẢI: nếu đánh tập tốt mà vào giải sa sút, chỉ "
    "rõ và kê biện pháp đặc thù cho thi đấu (áp lực, tình huống trận, tâm lý, "
    "thói quen thi đấu).\n"
    "- ĐỐI THỦ KỴ GIƠ: soi head-to-head — ai thua dai dẳng, thua kiểu gì (trắng "
    "set hay sát nút); yêu cầu sắp lịch tái đấu những người đó có mục tiêu.\n"
    "- ĐÁNH GAI: theo dõi riêng kết quả gặp đối thủ gai; nếu yếu hoặc ít trận, "
    "yêu cầu đánh nhiều hơn với gai.\n"
    "- KHỐI LƯỢNG: so tổng thời gian cầm vợt và số trận giữa các giai đoạn; tụt "
    "khối lượng phải bị nhắc thẳng. Ra mệnh lệnh 'tăng cường' RÕ RÀNG, ĐO ĐƯỢC "
    "(số buổi/tuần, số trận đơn-đôi-gai/tuần, số giờ cầm vợt/tuần).\n"
    "- Dùng GHI CHÚ hằng ngày của học trò làm ngữ cảnh (mệt, đau, đi công tác, "
    "cảm nhận trận) — đó là quan sát của con người, đáng tin.\n"
    "- TUYỆT ĐỐI KHÔNG bịa nhận xét kỹ thuật động tác (cổ tay, khuỷu, bộ chân…) "
    "và KHÔNG đề xuất chiến thuật trong trận — bạn không nhìn thấy học trò đánh "
    "và không biết cậu ấy đang dùng lối đánh/chiến thuật gì. Chỉ suy luận từ kết "
    "quả, khối lượng và ghi chú.\n"
    "- MẪU NHỎ: phân khúc nào được gắn nhãn [MẪU NHỎ] (dưới 5 trận trong kỳ) thì "
    "KHÔNG kết luận trình độ/win-rate từ phân khúc đó — chỉ được yêu cầu đánh "
    "thêm trận để đủ dữ liệu.\n"
    "- Lập kế hoạch tuần cụ thể, gắn với ngày tập thể lực và loại trận cần đánh.\n"
    "LƯU Ý AN TOÀN: học trò bị thoái hóa khớp gối độ 1 — KHÔNG ép squat sâu, lunge "
    "sâu hay nhảy bật. Đây không phải lời khuyên y tế.\n"
    "Trả lời HOÀN TOÀN bằng tiếng Việt, đúng JSON schema."
)


# Ollama structured-output schema (mirrors schemas.AssessmentOut's content parts).
RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "overall_assessment": {"type": "string"},
        "top_priorities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "why": {"type": "string"},
                    "source": {"type": "string"},
                },
                "required": ["title"],
            },
        },
        "directives": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "area": {"type": "string"},
                    "order": {"type": "string"},
                    "target": {"type": "string"},
                    "reason": {"type": "string"},
                    # Weekly machine-trackable goal; "" / 0 when not applicable.
                    "metric": {
                        "type": "string",
                        "enum": [
                            "",
                            "physical_sessions_per_week",
                            "racket_hours_per_week",
                            "coach_hours_per_week",
                            "matches_per_week",
                            "singles_matches_per_week",
                            "doubles_matches_per_week",
                            "matches_vs_pips_per_week",
                        ],
                    },
                    "value": {"type": "number"},
                },
                # metric/value are required so the model always decides
                # explicitly (metric="" + value=0 when not trackable) instead
                # of silently omitting them; the service sanity-clamps values.
                "required": ["area", "order", "metric", "value"],
            },
        },
        "week_plan": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "day": {"type": "string"},
                    "focus": {"type": "string"},
                    "detail": {"type": "string"},
                },
                "required": ["day", "focus"],
            },
        },
        "watch_items": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["overall_assessment", "top_priorities", "directives", "week_plan"],
}
