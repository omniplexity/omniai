import { useEffect, useMemo, useState } from "preact/hooks";
import {
  getDuckDnsLogs,
  getDuckDnsStatus,
  postDuckDnsTest,
  postDuckDnsUpdate,
  type DuckDnsLog,
  type DuckDnsStatus
} from "../core/api/opsDuckdnsApi";

function remediationFor(code?: string | null): string {
  switch ((code || "").toUpperCase()) {
    case "DUCKDNS_TOKEN_MISSING":
      return "Set DUCKDNS_TOKEN on server (Machine scope), then restart backend/scheduler.";
    case "DUCKDNS_KO":
      return "DuckDNS rejected token/subdomain pair. Verify both values in DuckDNS dashboard.";
    case "DUCKDNS_NETWORK":
      return "Server cannot reach DuckDNS/IP services. Check DNS, firewall, and outbound connectivity.";
    case "DUCKDNS_PARSE":
      return "Unexpected provider response. Check logs and try manual update again.";
    default:
      return "Check latest logs and backend health endpoint for more context.";
  }
}

function fmtUnix(value: number | null | undefined): string {
  if (!value) return "n/a";
  return new Date(value * 1000).toLocaleString();
}

function fmtIso(value: string | null | undefined): string {
  if (!value) return "n/a";
  return new Date(value).toLocaleString();
}

export function OpsRoute() {
  const [status, setStatus] = useState<DuckDnsStatus | null>(null);
  const [logs, setLogs] = useState<DuckDnsLog[]>([]);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionNote, setActionNote] = useState<string | null>(null);

  async function loadData() {
    try {
      setError(null);
      const [s, l] = await Promise.all([getDuckDnsStatus(), getDuckDnsLogs(200)]);
      setStatus(s);
      setLogs(l);
    } catch (e: any) {
      setError(String(e?.message || e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadData();
  }, []);

  useEffect(() => {
    if (!autoRefresh) return;
    const t = window.setInterval(() => void loadData(), 10000);
    return () => window.clearInterval(t);
  }, [autoRefresh]);

  async function onTest() {
    setBusy(true);
    setActionNote(null);
    try {
      const res = await postDuckDnsTest();
      setActionNote(`Test executed: ${res?.response ?? "OK"} (${res?.ip ?? "no ip"})`);
      await loadData();
    } catch (e: any) {
      setActionNote(`Test failed: ${String(e?.message || e)}`);
    } finally {
      setBusy(false);
    }
  }

  async function onForceUpdate() {
    setBusy(true);
    setActionNote(null);
    try {
      const res = await postDuckDnsUpdate(true);
      setActionNote(`Force update executed: ${res?.response ?? "OK"} (${res?.ip ?? "no ip"})`);
      await loadData();
    } catch (e: any) {
      setActionNote(`Force update failed: ${String(e?.message || e)}`);
    } finally {
      setBusy(false);
    }
  }

  async function onCopyDiagnostics() {
    const bundle = {
      generated_at: new Date().toISOString(),
      status,
      recent_logs: logs.slice(0, 50).map((l) => ({
        created_at: l.created_at,
        subdomain: l.subdomain,
        ip: l.ip,
        response: l.response,
        success: l.success,
        error_code: l.error_code,
        error_message: l.error_message,
        latency_ms: l.latency_ms,
        source: l.source
      }))
    };
    await navigator.clipboard.writeText(JSON.stringify(bundle, null, 2));
    setActionNote("Redacted diagnostics copied to clipboard.");
  }

  const lastErrorCode = status?.last_update?.error_code ?? logs.find((x) => !x.success)?.error_code;
  const remediation = useMemo(() => remediationFor(lastErrorCode), [lastErrorCode]);

  return (
    <div class="page pad" data-testid="ops-page">
      <div class="card wide">
        <h1 class="h1">Ops Console</h1>
        <p class="muted">Admin-only DuckDNS operations and diagnostics.</p>
      </div>

      {loading ? (
        <div class="card wide"><p role="status">Loading DuckDNS status...</p></div>
      ) : null}

      {error ? (
        <div class="card wide" role="alert" aria-live="assertive">
          <h2 class="h2">Backend Unreachable</h2>
          <p class="muted">{error}</p>
          <button class="btn" onClick={() => void loadData()} aria-label="Retry loading ops status">Retry</button>
        </div>
      ) : null}

      {status ? (
        <div class="card wide" aria-label="DuckDNS status card">
          <h2 class="h2">DuckDNS Status</h2>
          {status.scheduler_enabled && status.scheduler_stale ? (
            <div role="alert" aria-live="assertive" style="border:1px solid #f59e0b; background:#fffbeb; padding:10px; border-radius:8px; margin-bottom:10px;">
              <p style="color:#92400e; font-weight:600; margin:0 0 8px 0;">
                Scheduler stale: last successful DuckDNS update is older than {status.scheduler_stale_threshold_minutes} minutes.
              </p>
              <p style="margin:0;"><strong>Remediation:</strong></p>
              <ul style="margin:6px 0 0 20px;">
                <li>Check Scheduled Task health and last run result.</li>
                <li>Check machine-scope <code>DUCKDNS_TOKEN</code> availability.</li>
                <li>Check outbound connectivity from server to DuckDNS/IP endpoints.</li>
              </ul>
            </div>
          ) : null}
          <p><strong>Token present:</strong> {status.token_present ? "Yes" : "No"}</p>
          <p><strong>Subdomain:</strong> {status.subdomain}</p>
          <p><strong>Scheduler enabled:</strong> {status.scheduler_enabled ? "Yes" : "No"}</p>
          <p><strong>Scheduler last run:</strong> {fmtUnix(status.scheduler_last_run_unix)}</p>
          <p><strong>Scheduler last OK:</strong> {fmtUnix(status.scheduler_last_ok_unix)}</p>
          <p><strong>Scheduler stale:</strong> {status.scheduler_stale ? "Yes" : "No"}</p>
          <p><strong>Last update:</strong> {fmtIso(status.last_update?.created_at)}</p>
          <p><strong>Last IP:</strong> {status.last_update?.ip || "n/a"}</p>
          <p><strong>Last response:</strong> {status.last_update?.response || "n/a"}</p>
          <p><strong>Last error code:</strong> {status.last_update?.error_code || "n/a"}</p>
          <p><strong>Last error message:</strong> {status.last_update?.error_message || "n/a"}</p>
          <p><strong>Next scheduled run:</strong> {fmtUnix(status.next_scheduled_run_unix)}</p>
        </div>
      ) : null}

      <div class="card wide">
        <h2 class="h2">Actions</h2>
        <div style="display:flex; gap:8px; flex-wrap:wrap;">
          <button class="btn primary" onClick={() => void onTest()} disabled={busy} aria-label="Test DuckDNS now">
            Test DuckDNS now
          </button>
          <button class="btn" onClick={() => void onForceUpdate()} disabled={busy} aria-label="Force DuckDNS update now">
            Force update now
          </button>
          <button class="btn" onClick={() => void onCopyDiagnostics()} aria-label="Copy diagnostic bundle">
            Copy diagnostic bundle
          </button>
          <label style="display:flex; align-items:center; gap:6px;">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e: any) => setAutoRefresh(Boolean(e.currentTarget?.checked))}
              aria-label="Toggle auto refresh"
            />
            Auto-refresh
          </label>
        </div>
        {actionNote ? <p role="status">{actionNote}</p> : null}
      </div>

      <div class="card wide" role="region" aria-label="Remediation guidance">
        <h2 class="h2">Remediation</h2>
        <p><strong>Error code:</strong> {lastErrorCode || "n/a"}</p>
        <p>{remediation}</p>
      </div>

      <div class="card wide">
        <h2 class="h2">Recent DuckDNS Logs</h2>
        <div style="max-height: 360px; overflow: auto;">
          <table style="width:100%; border-collapse: collapse;" aria-label="DuckDNS recent logs table">
            <thead>
              <tr>
                <th align="left">Time</th>
                <th align="left">Source</th>
                <th align="left">IP</th>
                <th align="left">Response</th>
                <th align="left">Error</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((row) => (
                <tr key={row.id}>
                  <td>{fmtIso(row.created_at)}</td>
                  <td>{row.source}</td>
                  <td>{row.ip || "n/a"}</td>
                  <td>{row.response || "n/a"}</td>
                  <td>{row.error_code || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {logs.length === 0 ? <p class="muted">No logs yet.</p> : null}
        </div>
      </div>
    </div>
  );
}
