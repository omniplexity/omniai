import { useEffect, useMemo, useState } from "react";
import type { SystemConfigSnapshot } from "./types";

type Status = "idle" | "loading" | "ready" | "forbidden" | "error";

type Props = {
  config: SystemConfigSnapshot | null;
  status: Status;
  error: string;
  fetchedAt?: string;
  rawJson?: string;
  onRefresh: () => void;
  onCopyNumber: (value: number) => void;
  onCopyJson: () => void;
  onCopyText?: (value: string) => void;
};

function formatBytes(n: number): string {
  if (!Number.isFinite(n) || n < 0) return String(n);
  const units = ["B", "KB", "MB", "GB", "TB"];
  let v = n;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i += 1;
  }
  const rounded = i === 0 ? `${Math.trunc(v)}` : `${v.toFixed(2)}`;
  return `${n} (${rounded} ${units[i]})`;
}

type RowData = {
  key: string;
  value: string;
  copyNumber?: number;
  copyText?: string;
};

function Row({
  row,
  onCopyNumber,
  onCopyText,
}: {
  row: RowData;
  onCopyNumber?: (value: number) => void;
  onCopyText?: (value: string) => void;
}) {
  return (
    <div className="ops-row">
      <div>
        <span className="k">{row.key}:</span> <span className="v">{row.value}</span>
      </div>
      {typeof row.copyNumber === "number" && onCopyNumber ? <button aria-label={`Copy ${row.key}`} onClick={() => onCopyNumber(row.copyNumber || 0)}>Copy</button> : null}
      {typeof row.copyNumber !== "number" && row.copyText && onCopyText ? <button aria-label={`Copy ${row.key}`} onClick={() => onCopyText(row.copyText || "")}>Copy</button> : null}
      {typeof row.copyNumber !== "number" && (!row.copyText || !onCopyText) ? <span /> : null}
    </div>
  );
}

function fmtLocal(ts?: string): string {
  if (!ts) return "";
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return ts;
  return d.toLocaleString();
}

function formatStaleness(fetchedAt?: string, nowMs?: number): string {
  if (!fetchedAt) return "-";
  const ts = Date.parse(fetchedAt);
  if (Number.isNaN(ts)) return "-";
  const deltaSec = Math.max(0, Math.floor(((nowMs || Date.now()) - ts) / 1000));
  if (deltaSec < 10) return "just now";
  if (deltaSec < 60) return `${deltaSec}s ago`;
  const deltaMin = Math.floor(deltaSec / 60);
  if (deltaMin < 60) return `${deltaMin}m ago`;
  const deltaHour = Math.floor(deltaMin / 60);
  return `${deltaHour}h ago`;
}

export function SystemConfigPanel({ config, status, error, fetchedAt, rawJson, onRefresh, onCopyNumber, onCopyJson, onCopyText }: Props) {
  const [showRaw, setShowRaw] = useState(false);
  const [query, setQuery] = useState("");
  const [nowMs, setNowMs] = useState(() => Date.now());
  const [open, setOpen] = useState<Record<string, boolean>>({
    metadata: true,
    notifications: true,
    sse: true,
    artifacts: true,
    sessions: true,
    quotas: true,
    raw: false,
  });
  const generatedAtLocal = useMemo(() => fmtLocal(config?.generated_at), [config?.generated_at]);
  const fetchedAtLocal = useMemo(() => fmtLocal(fetchedAt), [fetchedAt]);
  const staleness = useMemo(() => formatStaleness(fetchedAt, nowMs), [fetchedAt, nowMs]);

  useEffect(() => {
    if (!fetchedAt) return undefined;
    setNowMs(Date.now());
    const timer = window.setInterval(() => {
      setNowMs(Date.now());
    }, 5000);
    return () => {
      window.clearInterval(timer);
    };
  }, [fetchedAt]);

  useEffect(() => {
    setOpen((prev) => ({ ...prev, raw: showRaw }));
  }, [showRaw]);

  if (status === "forbidden") return <div role="status">Not authorized</div>;
  if (status === "loading") return <div role="status">Loading...</div>;
  if (status === "error") return <div role="status">{error || "Failed to load system config"}</div>;
  if (!config) {
    return (
      <button aria-label="Load System Config" onClick={onRefresh}>
        Load System Config
      </button>
    );
  }

  const codes = config.notify_tool_errors_only_codes.length ? config.notify_tool_errors_only_codes.join(", ") : "[]";
  const bindings = config.notify_tool_errors_only_bindings.length ? config.notify_tool_errors_only_bindings.join(", ") : "[]";
  const normalizedQuery = query.trim().toLowerCase();
  const statusLabel = status[0].toUpperCase() + status.slice(1);

  const rows = {
    metadata: [
      { key: "generated_at", value: generatedAtLocal || config.generated_at || "", copyText: config.generated_at || undefined },
      { key: "fetched_at", value: fetchedAtLocal || fetchedAt || "" },
      { key: "contract_version", value: String(config.contract_version || "") },
      { key: "runtime_version", value: String(config.runtime_version || "") },
    ] satisfies RowData[],
    notifications: [
      { key: "notify_tool_errors", value: String(config.notify_tool_errors) },
      { key: "notify_tool_errors_only_codes", value: codes },
      { key: "notify_tool_errors_only_bindings", value: bindings },
      { key: "notify_tool_errors_max_per_run", value: String(config.notify_tool_errors_max_per_run), copyNumber: config.notify_tool_errors_max_per_run },
    ] satisfies RowData[],
    sse: [
      { key: "sse_max_replay", value: String(config.sse_max_replay), copyNumber: config.sse_max_replay },
      { key: "sse_heartbeat_seconds", value: String(config.sse_heartbeat_seconds), copyNumber: config.sse_heartbeat_seconds },
    ] satisfies RowData[],
    artifacts: [
      { key: "artifact_max_bytes", value: formatBytes(config.artifact_max_bytes), copyNumber: config.artifact_max_bytes },
      { key: "artifact_part_size", value: formatBytes(config.artifact_part_size), copyNumber: config.artifact_part_size },
    ] satisfies RowData[],
    sessions: [
      { key: "session_ttl_seconds", value: String(config.session_ttl_seconds), copyNumber: config.session_ttl_seconds },
      { key: "session_sliding_enabled", value: String(config.session_sliding_enabled) },
      { key: "session_sliding_window_seconds", value: String(config.session_sliding_window_seconds), copyNumber: config.session_sliding_window_seconds },
    ] satisfies RowData[],
    quotas: [
      { key: "max_events_per_run", value: String(config.max_events_per_run), copyNumber: config.max_events_per_run },
      { key: "max_bytes_per_run", value: formatBytes(config.max_bytes_per_run), copyNumber: config.max_bytes_per_run },
    ] satisfies RowData[],
  };

  function sectionRows(section: RowData[]): RowData[] {
    if (!normalizedQuery) return section;
    return section.filter((row) => `${row.key} ${row.value}`.toLowerCase().includes(normalizedQuery));
  }

  function toggleSection(sectionId: string) {
    setOpen((prev) => ({ ...prev, [sectionId]: !prev[sectionId] }));
  }

  function renderSection(sectionId: keyof typeof rows, title: string) {
    const isOpen = Boolean(open[sectionId]);
    const filtered = sectionRows(rows[sectionId]);
    return (
      <section className="ops-section" key={sectionId}>
        <button
          type="button"
          className="ops-section-toggle"
          aria-expanded={isOpen}
          aria-controls={`ops-section-${sectionId}`}
          onClick={() => toggleSection(sectionId)}
        >
          {title}
        </button>
        <div id={`ops-section-${sectionId}`} hidden={!isOpen}>
          {filtered.length ? filtered.map((row) => <Row key={row.key} row={row} onCopyNumber={onCopyNumber} onCopyText={onCopyText} />) : <div className="ops-empty">No matches</div>}
        </div>
      </section>
    );
  }

  return (
    <div className="ops-panel">
      <div className="ops-sticky-header">
        <div className="ops-header-top">
          <h4>System Config</h4>
          <span className={`ops-status-badge ops-status-${status}`}>{statusLabel}</span>
        </div>
        <div className="row">
          <button aria-label="Refresh System Config" onClick={onRefresh}>Refresh Config</button>
          <button aria-label="Copy System Config JSON" onClick={onCopyJson}>Copy JSON</button>
          <button aria-label={showRaw ? "Hide Raw JSON" : "Show Raw JSON"} onClick={() => setShowRaw((v) => !v)}>
            {showRaw ? "Hide Raw" : "Show Raw"}
          </button>
        </div>
        <div className="ops-fetched-line">Fetched: {staleness}</div>
      </div>

      <div className="ops-search-wrap">
        <input
          aria-label="Search system config"
          placeholder="Search key/value"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      {renderSection("notifications", "Notifications gating")}
      {renderSection("sse", "SSE")}
      {renderSection("artifacts", "Artifacts")}
      {renderSection("sessions", "Sessions")}
      {renderSection("quotas", "Run quotas")}
      {renderSection("metadata", "Metadata")}

      <section className="ops-section">
        <button
          type="button"
          className="ops-section-toggle"
          aria-expanded={Boolean(open.raw)}
          aria-controls="ops-section-raw"
          onClick={() => {
            setShowRaw((v) => !v);
            toggleSection("raw");
          }}
        >
          Raw JSON
        </button>
        <div id="ops-section-raw" hidden={!open.raw}>
          {showRaw ? (
            <pre aria-label="System Config Raw JSON" className="ops-raw-json">
              {rawJson || JSON.stringify(config, null, 2)}
            </pre>
          ) : (
            <div className="ops-empty">No matches</div>
          )}
        </div>
      </section>
    </div>
  );
}
