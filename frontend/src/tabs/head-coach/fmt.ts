// Shared time formatting for the Head Coach tab (verdict meta + chat).

/** Render a backend timestamp in VN time. Old snapshots were serialized as
 *  naive UTC (no timezone suffix) — treat them as UTC so they don't render
 *  7 hours early. */
export function fmtTime(iso: string | null): string {
  if (!iso) return "";
  const hasTz = /Z$|[+-]\d{2}:\d{2}$/.test(iso);
  const d = new Date(hasTz ? iso : `${iso}Z`);
  return d.toLocaleString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh" });
}

/** Short form for chat bubbles: time only for today, date + time otherwise. */
export function fmtChatTime(iso: string | null): string {
  if (!iso) return "";
  const hasTz = /Z$|[+-]\d{2}:\d{2}$/.test(iso);
  const d = new Date(hasTz ? iso : `${iso}Z`);
  const opts: Intl.DateTimeFormatOptions = {
    timeZone: "Asia/Ho_Chi_Minh",
    hour: "2-digit",
    minute: "2-digit",
  };
  const sameDay =
    d.toLocaleDateString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh" }) ===
    new Date().toLocaleDateString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh" });
  if (!sameDay) {
    opts.day = "2-digit";
    opts.month = "2-digit";
  }
  return d.toLocaleString("vi-VN", opts);
}
