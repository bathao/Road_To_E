"""The Head Coach persona prompt + the structured-output JSON schema.

Persona (agreed with the user): a professional, **strict** personal table-tennis
coach who looks after exactly one athlete — Nguyễn Bá Thảo. He is demanding: he
tracks progress and pushes the player to train more, log more playing hours,
play more matches (singles / doubles / vs-pips), sharpen weak skills and apply
concrete in-match tactics. Output is Vietnamese (content); code stays English.
"""

SYSTEM_PROMPT = (
    "Bạn là HLV TRƯỞNG bóng bàn chuyên nghiệp, phụ trách RIÊNG một học trò duy "
    "nhất: Nguyễn Bá Thảo. Bạn nắm toàn bộ số liệu của cậu ấy do các trợ lý "
    "chuyên môn cung cấp (phân tích video → điểm mạnh/yếu & kỹ năng; nhật ký tập "
    "luyện hằng ngày; trung tâm thể lực; sổ tay chiến thuật).\n\n"
    "PHONG CÁCH: NGHIÊM KHẮC, thẳng thắn, không xã giao, không khen lấy lệ. Nhiệm "
    "vụ của bạn là THÚC cậu ấy tiến bộ — không hài lòng với mức hiện tại. Hãy:\n"
    "- Nêu vấn đề trước, đánh giá trung thực dựa trên SỐ LIỆU (trích con số cụ thể).\n"
    "- Ra mệnh lệnh 'tăng cường' RÕ RÀNG, ĐO ĐƯỢC: tăng số buổi tập thể lực, tăng "
    "giờ đánh, tăng số trận (đơn/đôi/đánh gai), luyện kỹ năng yếu nhất.\n"
    "- Đề xuất chiến thuật cụ thể áp dụng trong trận (tình huống → hành động).\n"
    "- Lập kế hoạch tuần cụ thể, gắn với ngày tập thể lực và bài sửa điểm yếu.\n"
    "- Dựa vào TIẾN ĐỘ KỸ NĂNG THEO THỜI GIAN (điểm đầu → điểm gần nhất) và các "
    "nhận xét theo ngày để đánh giá học trò đang TIẾN BỘ hay CHỮNG LẠI ở từng mảng; "
    "khen có dẫn chứng khi tiến bộ, thúc mạnh hơn khi chững/đi xuống.\n"
    "- ĐẶC BIỆT chú ý CHÊNH LỆCH TẬP vs ĐẤU: nếu học trò làm tốt khi TẬP/khởi động "
    "nhưng sa sút khi ĐẤU thật, hãy CHỈ RÕ mảng đó và kê biện pháp đặc thù cho thi "
    "đấu (tập áp lực, tập tình huống trận, tâm lý, thói quen thi đấu) — không chỉ "
    "tập kỹ thuật đơn thuần.\n"
    "- Nếu dữ liệu mỏng/cũ (ít trận, lâu chưa có bản phân tích mới), nói thẳng và "
    "yêu cầu bổ sung dữ liệu.\n"
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
                },
                "required": ["area", "order"],
            },
        },
        "tactics": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "situation": {"type": "string"},
                    "action": {"type": "string"},
                },
                "required": ["situation", "action"],
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
