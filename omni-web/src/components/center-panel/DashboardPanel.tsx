import { Suspense, lazy, useState } from "react";
import { RunSummary, RunMetrics, ProvenanceSummary, ProvenanceGraph, ProvenanceWhyPath, ArtifactRef, ResearchSource, WorkflowInfo, WorkflowRun, ProvenanceCaps } from "../../types";

const ProvenanceGraphView = lazy(() => import("../../provenance/ProvenanceGraphView").then((m) => ({ default: m.ProvenanceGraphView })));

interface DashboardPanelProps {
  summary: RunSummary | null;
  runMetrics: RunMetrics | null;
  provenance: ProvenanceSummary | null;
  provenanceGraph: ProvenanceGraph | null;
  provenanceError: string;
  selectedProvArtifact: string;
  selectedProvPaths: ProvenanceWhyPath[];
  selectedProvTruncated: boolean;
  provenanceViewMode: "list" | "graph";
  provenanceCaps: ProvenanceCaps;
  artifacts: ArtifactRef[];
  researchQuery: string;
  researchSources: ResearchSource[];
  researchReport: string;
  workflowGraphJson: string;
  workflows: WorkflowInfo[];
  selectedWorkflowId: string;
  workflowRuns: WorkflowRun[];
  selectedRunId: string;
  onStartResearch: () => void;
  onResearchQueryChange: (query: string) => void;
  onDefineWorkflow: () => void;
  onWorkflowGraphChange: (json: string) => void;
  onStartWorkflow: () => void;
  onLoadWorkflowRuns: () => void;
  onSelectWorkflow: (id: string) => void;
  onExportProvenance: () => void;
  onRefetchProvenance: () => void;
  onProvenanceCapsChange: (caps: Partial<ProvenanceCaps>) => void;
  onProvenanceViewModeChange: (mode: "list" | "graph") => void;
  onArtifactSelect: (artifactId: string) => void;
}

export function DashboardPanel({
  summary,
  runMetrics,
  provenance,
  provenanceGraph,
  provenanceError,
  selectedProvArtifact,
  selectedProvPaths,
  selectedProvTruncated,
  provenanceViewMode,
  provenanceCaps,
  artifacts,
  researchQuery,
  researchSources,
  researchReport,
  workflowGraphJson,
  workflows,
  selectedWorkflowId,
  workflowRuns,
  selectedRunId,
  onStartResearch,
  onResearchQueryChange,
  onDefineWorkflow,
  onWorkflowGraphChange,
  onStartWorkflow,
  onLoadWorkflowRuns,
  onSelectWorkflow,
  onExportProvenance,
  onRefetchProvenance,
  onProvenanceCapsChange,
  onProvenanceViewModeChange,
  onArtifactSelect,
}: DashboardPanelProps) {
  const [researchQueryLocal, setResearchQueryLocal] = useState(researchQuery);

  return (
    <div className="dashboard-container">
      {/* Header */}
      <div className="section-header">
        <div className="flex items-center gap-md">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
            <line x1="3" y1="9" x2="21" y2="9" />
            <line x1="9" y1="21" x2="9" y2="9" />
          </svg>
          <span className="section-title">Dashboard</span>
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="dashboard-grid">
        <div className="metric-card">
          <div className="metric-label">Status</div>
          <div className={`metric-value ${summary?.status === "active" ? "success" : ""}`}>
            {summary?.status || "No run"}
          </div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Events</div>
          <div className="metric-value info">
            {runMetrics?.event_count || summary?.event_count || 0}
          </div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Tool Calls</div>
          <div className="metric-value">
            {runMetrics?.tool_calls || 0}
          </div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Artifacts</div>
          <div className="metric-value">
            {runMetrics?.artifacts_count || provenance?.artifacts_count || 0}
          </div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Errors</div>
          <div className={`metric-value ${(runMetrics?.tool_errors || 0) > 0 ? "error" : ""}`}>
            {runMetrics?.tool_errors || 0}
          </div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Duration</div>
          <div className="metric-value">
            {runMetrics?.duration_ms ? `${Math.round(runMetrics.duration_ms / 1000)}s` : "-"}
          </div>
        </div>
      </div>

      {/* Provenance Section */}
      <div className="provenance-container">
        <div className="provenance-header">
          <div className="flex items-center gap-md">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
            <span className="card-title">Provenance</span>
          </div>
          <div className="flex items-center gap-sm">
            <button 
              className="btn btn-ghost btn-sm"
              onClick={onExportProvenance}
              disabled={!provenanceGraph}
            >
              Export
            </button>
            <button 
              className="btn btn-ghost btn-sm"
              onClick={onRefetchProvenance}
              disabled={!selectedRunId}
            >
              Refresh
            </button>
          </div>
        </div>

        {/* Provenance Controls */}
        <div className="prov-controls">
          <label className="input-label">
            Max Depth
            <input
              type="number"
              className="input"
              value={provenanceCaps.max_depth}
              onChange={(e) => onProvenanceCapsChange({ max_depth: Number(e.target.value) })}
              min={1}
              style={{ width: "80px", marginLeft: "8px" }}
            />
          </label>
          <label className="input-label">
            Node Cap
            <input
              type="number"
              className="input"
              value={provenanceCaps.node_cap}
              onChange={(e) => onProvenanceCapsChange({ node_cap: Number(e.target.value) })}
              min={1}
              style={{ width: "100px", marginLeft: "8px" }}
            />
          </label>
          <label className="input-label">
            Edge Cap
            <input
              type="number"
              className="input"
              value={provenanceCaps.edge_cap}
              onChange={(e) => onProvenanceCapsChange({ edge_cap: Number(e.target.value) })}
              min={1}
              style={{ width: "100px", marginLeft: "8px" }}
            />
          </label>
        </div>

        {/* View Mode Tabs */}
        <div className="tabs">
          <button 
            className={`tab ${provenanceViewMode === "graph" ? "active" : ""}`}
            onClick={() => onProvenanceViewModeChange("graph")}
          >
            Graph
          </button>
          <button 
            className={`tab ${provenanceViewMode === "list" ? "active" : ""}`}
            onClick={() => onProvenanceViewModeChange("list")}
          >
            List
          </button>
        </div>

        {/* Provenance Content */}
        {provenanceError && (
          <div className="card-body">
            <pre className="text-secondary">{provenanceError}</pre>
          </div>
        )}

        {provenanceGraph && provenanceViewMode === "graph" && (
          <div className="prov-canvas">
            <Suspense fallback={<div className="spinner" />}>
              <ProvenanceGraphView
                graph={provenanceGraph}
                why={{ paths: selectedProvPaths, truncated: selectedProvTruncated }}
                onArtifactSelect={onArtifactSelect}
              />
            </Suspense>
          </div>
        )}

        {provenanceGraph && provenanceViewMode === "list" && (
          <div className="card-body">
            <div className="mb-md">
              <strong>{provenanceGraph.nodes.length}</strong> nodes / <strong>{provenanceGraph.edges.length}</strong> edges
            </div>
            <select
              className="input"
              value={selectedProvArtifact}
              onChange={(e) => onArtifactSelect(e.target.value)}
            >
              <option value="">Select artifact...</option>
              {provenanceGraph.nodes.filter((n) => n.type === "artifact").map((n) => (
                <option key={n.id} value={n.id}>{n.label}</option>
              ))}
            </select>
            {selectedProvPaths.length > 0 && (
              <div className="mt-md">
                <strong>Why is this here?</strong>
                {selectedProvPaths.map((path, idx) => (
                  <div key={idx} className="mt-sm">
                    <div className="text-sm text-secondary">Path {idx + 1}</div>
                    <ol className="text-sm">
                      {path.nodes.map((node, nIdx) => (
                        <li key={nIdx}>{node}</li>
                      ))}
                    </ol>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Artifact Gallery */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">Artifacts ({artifacts.length})</span>
        </div>
        <div className="card-body">
          {artifacts.length === 0 ? (
            <div className="empty-state">
              <p className="text-secondary">No artifacts yet</p>
            </div>
          ) : (
            <div className="artifact-gallery">
              {artifacts.map((a) => (
                <div key={a.artifact_id} className="artifact-card">
                  <div className="artifact-icon">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                      <polyline points="14 2 14 8 20 8" />
                    </svg>
                  </div>
                  <div className="artifact-title">{a.title || a.artifact_id.slice(0, 12)}</div>
                  <div className="artifact-meta">
                    {a.kind} • {Math.round(a.size_bytes / 1024)}KB
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Deep Research */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">Deep Research</span>
        </div>
        <div className="card-body">
          <div className="flex gap-sm mb-md">
            <input
              type="text"
              className="input"
              value={researchQuery}
              onChange={(e) => onResearchQueryChange(e.target.value)}
              placeholder="Research query..."
              style={{ flex: 1 }}
            />
            <button 
              className="btn btn-primary"
              onClick={onStartResearch}
              disabled={!selectedRunId}
            >
              Start Research
            </button>
          </div>
          
          {researchSources.length > 0 && (
            <div className="mb-md">
              <div className="text-sm font-medium mb-sm">Sources ({researchSources.length})</div>
              <div className="list">
                {researchSources.map((s) => (
                  <div key={s.source_id} className="list-item">
                    <div className="list-item-content">
                      <div className="list-item-title">{s.title}</div>
                      <div className="list-item-subtitle">{s.url}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {researchReport && (
            <div>
              <div className="text-sm font-medium mb-sm">Report</div>
              <pre className="text-sm" style={{ whiteSpace: "pre-wrap" }}>{researchReport}</pre>
            </div>
          )}
        </div>
      </div>

      {/* Workflows */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">Workflows</span>
        </div>
        <div className="card-body">
          <div className="mb-md">
            <textarea
              className="input"
              value={workflowGraphJson}
              onChange={(e) => onWorkflowGraphChange(e.target.value)}
              rows={4}
              placeholder="Workflow JSON..."
            />
            <button className="btn btn-secondary btn-sm" onClick={onDefineWorkflow}>
              Define Workflow
            </button>
          </div>
          
          <div className="flex gap-sm mb-md">
            <select
              className="input"
              value={selectedWorkflowId}
              onChange={(e) => onSelectWorkflow(e.target.value)}
              style={{ flex: 1 }}
            >
              <option value="">Select workflow...</option>
              {workflows.map((w) => (
                <option key={`${w.workflow_id}-${w.version}`} value={w.workflow_id}>
                  {w.name}@{w.version}
                </option>
              ))}
            </select>
            <button 
              className="btn btn-primary"
              onClick={onStartWorkflow}
              disabled={!selectedWorkflowId || !selectedRunId}
            >
              Start
            </button>
            <button 
              className="btn btn-ghost"
              onClick={onLoadWorkflowRuns}
              disabled={!selectedRunId}
            >
              Refresh
            </button>
          </div>

          {workflowRuns.length > 0 && (
            <div className="list">
              {workflowRuns.map((r) => (
                <div key={r.workflow_run_id} className="list-item">
                  <span className={`badge badge-${r.status === "completed" ? "success" : r.status === "failed" ? "error" : "warning"}`}>
                    {r.status}
                  </span>
                  <div className="list-item-content">
                    <div className="list-item-title">{r.workflow_run_id.slice(0, 12)}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
