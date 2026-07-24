// Chat with the Head Coach. Every reply is generated server-side from the
// live facts bundle + the coach's notebook + the FULL history read back from
// the database — the conversation itself is the coach's verbatim memory.
//
// Flow mirrors the verdict: send → a pending coach row appears immediately →
// poll GET /chat every 3s until `pending` clears (local LLM, ~30-90s).
import { useEffect, useRef, useState } from "react";
import { headCoachApi } from "../api";
import { useLoad, useMutate } from "../../../shared/useApi";
import type { ChatHistory, ChatMessage } from "../types";
import { fmtChatTime } from "../fmt";

function Bubble({ m }: { m: ChatMessage }) {
  if (m.role === "coach" && m.status === "pending") {
    return (
      <div className="hc-msg coach">
        <div className="hc-bubble pending">
          HLV đang xem số liệu và trả lời
          <span className="hc-dots">
            <span>.</span>
            <span>.</span>
            <span>.</span>
          </span>
        </div>
      </div>
    );
  }
  if (m.role === "coach" && m.status === "error") {
    return (
      <div className="hc-msg coach">
        <div className="hc-bubble error">
          ⚠️ HLV không trả lời được: {m.error_msg || "lỗi không rõ"}. Gửi lại
          câu hỏi để thử lần nữa.
        </div>
      </div>
    );
  }
  return (
    <div className={`hc-msg ${m.role}`}>
      <div className="hc-bubble">{m.content}</div>
      <div className="hc-msg-time">{fmtChatTime(m.created_at)}</div>
    </div>
  );
}

export default function CoachChat({ onCoachReply }: { onCoachReply: () => void }) {
  const {
    data,
    setData,
    error: loadError,
  } = useLoad<ChatHistory>(() => headCoachApi.getChat(), []);
  const { run, error, busy, clearError } = useMutate();
  const [text, setText] = useState("");
  const listRef = useRef<HTMLDivElement>(null);
  const pending = data?.pending ?? false;
  const messages = data?.messages ?? [];

  // While a reply is in flight, poll; when it lands, refresh the notebook too
  // (the coach may have auto-written notes from this exchange).
  useEffect(() => {
    if (!pending) return;
    const timer = setInterval(async () => {
      try {
        const h = await headCoachApi.getChat();
        setData(h);
        if (!h.pending) onCoachReply();
      } catch {
        // transient poll failure — keep polling
      }
    }, 3000);
    return () => clearInterval(timer);
  }, [pending, setData, onCoachReply]);

  // Keep the newest message in view.
  useEffect(() => {
    const el = listRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages.length, pending]);

  const send = async () => {
    const t = text.trim();
    if (!t || pending || busy) return;
    clearError();
    const out = await run(() => headCoachApi.sendChat(t));
    if (out !== undefined) {
      setText("");
      setData(out);
    }
  };

  return (
    <div className="hc-chat">
      <div className="hc-chat-list" ref={listRef}>
        {loadError && messages.length === 0 && (
          <div className="hc-error">
            ⚠️ Không tải được lịch sử trao đổi: {loadError}
          </div>
        )}
        {messages.length === 0 && !loadError && (
          <div className="hc-chat-empty">
            Chưa có trao đổi nào. Hỏi HLV bất cứ điều gì — đặt mục tiêu ngắn hạn
            (ví dụ: <i>“Tôi muốn đánh đơn tốt cho giải 2/8”</i>), báo lịch bận,
            hay hỏi về số liệu. Mọi trao đổi được lưu lại và HLV nhớ hết.
          </div>
        )}
        {messages.map((m) => (
          <Bubble key={m.id} m={m} />
        ))}
      </div>
      {error && <div className="hc-error">⚠️ {error}</div>}
      <div className="hc-chat-input">
        <textarea
          rows={2}
          value={text}
          placeholder={
            pending ? "HLV đang trả lời…" : "Nhắn cho HLV… (Enter để gửi)"
          }
          disabled={pending}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void send();
            }
          }}
        />
        <button
          className="btn primary"
          onClick={send}
          disabled={pending || busy || !text.trim()}
        >
          Gửi
        </button>
      </div>
    </div>
  );
}
