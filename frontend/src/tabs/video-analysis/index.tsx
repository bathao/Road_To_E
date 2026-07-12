import { useCallback, useEffect, useMemo, useState } from "react";
import { videoApi } from "./api";
import PasteForm from "./components/PasteForm";
import ReportList from "./components/ReportList";
import ReviewPanel from "./components/ReviewPanel";
import type {
  AnalysisReport,
  AnalysisReportDetail,
  FindingDecision,
  ModelHealth,
} from "./types";

// Pure analysis intake: paste a cloud analysis (tagged date + setting) → the
// text model parses it into findings, auto-saves them, and auto-rebuilds the
// skill ledger. The living profile / skills / findings are shown in the Profile
// tab, not here.
export default function VideoAnalysis() {
  const [health, setHealth] = useState<ModelHealth | null>(null);
  const [reports, setReports] = useState<AnalysisReport[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<AnalysisReportDetail | null>(null);

  const [submitting, setSubmitting] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fail = (e: unknown) => setError(e instanceof Error ? e.message : String(e));

  const reloadReports = useCallback(async () => setReports(await videoApi.listReports()), []);
  const reloadDetail = useCallback(async (id: number) => {
    setDetail(await videoApi.getAnalysisReport(id));
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const [h, rl] = await Promise.all([videoApi.health(), videoApi.listReports()]);
        setHealth(h);
        setReports(rl);
      } catch (e) {
        fail(e);
      }
    })();
  }, []);

  useEffect(() => {
    if (selectedId == null) {
      setDetail(null);
      return;
    }
    void reloadDetail(selectedId).catch(fail);
  }, [selectedId, reloadDetail]);

  // Poll while any report is parsing (parsing also auto-rebuilds the ledger).
  const anyParsing = useMemo(() => reports.some((r) => r.status === "parsing"), [reports]);
  useEffect(() => {
    if (!anyParsing) return;
    const timer = setInterval(() => {
      void reloadReports().catch(() => {});
      if (selectedId != null) void reloadDetail(selectedId).catch(() => {});
    }, 2500);
    return () => clearInterval(timer);
  }, [anyParsing, selectedId, reloadReports, reloadDetail]);

  const handleCreateReport = async (form: Parameters<typeof videoApi.createReport>[0]) => {
    setError(null);
    setSubmitting(true);
    try {
      const r = await videoApi.createReport(form);
      await reloadReports();
      setSelectedId(r.id);
    } catch (e) {
      fail(e);
    } finally {
      setSubmitting(false);
    }
  };

  const handleReview = async (decisions: FindingDecision[]) => {
    if (selectedId == null) return;
    setReviewing(true);
    try {
      await videoApi.reviewReport(selectedId, decisions);
      await Promise.all([reloadDetail(selectedId), reloadReports()]);
    } catch (e) {
      fail(e);
    } finally {
      setReviewing(false);
    }
  };

  const handleDeleteReport = async (id: number) => {
    if (!window.confirm("Xóa bản phân tích này (và các nhận xét chưa duyệt của nó)?")) return;
    try {
      await videoApi.deleteReport(id);
      if (selectedId === id) setSelectedId(null);
      await reloadReports();
    } catch (e) {
      fail(e);
    }
  };

  return (
    <div className="va-tab">
      {error && <div className="pb-error">{error}</div>}

      <div className="va-analyze-col">
        <PasteForm health={health} submitting={submitting} onCreate={handleCreateReport} />
        <section className="va-card">
          <div className="va-card-head">
            <h3>🗂️ Các bản phân tích</h3>
            {anyParsing && <span className="va-muted">đang bóc tách…</span>}
          </div>
          <ReportList
            reports={reports}
            selectedId={selectedId}
            onSelect={setSelectedId}
            onDelete={handleDeleteReport}
          />
        </section>
        {detail && (
          <ReviewPanel
            detail={detail}
            reviewing={reviewing}
            onReview={handleReview}
            onDelete={() => handleDeleteReport(detail.id)}
          />
        )}
      </div>
    </div>
  );
}
