import { ToolMetricRow } from "../../types";

interface ToolMetricsPanelProps {
  toolMetrics: ToolMetricRow[];
}

export function ToolMetricsPanel({ toolMetrics }: ToolMetricsPanelProps) {
  return (
    <div className="dashboard-container">
      <div className="section-header"><span className="section-title">Tool Metrics</span></div>
      <div className="section-content">
        <div className="list" style={{ maxHeight: "420px", overflowY: "auto" }}>
          {toolMetrics.map((t) => (
            <div key={`${t.tool_id}-${t.tool_version}`} className="list-item">
              <div className="list-item-content">
                <div className="list-item-title text-xs">{t.tool_id}@{t.tool_version}</div>
                <div className="list-item-subtitle text-xs">calls: {t.calls} | errors: {t.errors} | lat: {t.last_latency_ms ?? "n/a"}ms</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
