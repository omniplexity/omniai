// Project Types
export type Project = { id: string; name: string; created_at: string };
export type Thread = { id: string; project_id: string; title: string; created_at: string };
export type Run = { id: string; thread_id: string; status: string; created_at: string; pins: Record<string, unknown> };
export type RunSummary = { run_id: string; status: string; created_at: string; event_count: number; last_seq: number; pins: Record<string, unknown> };

// Event Types
export type EventEnvelope = { event_id: string; run_id: string; thread_id: string; project_id: string; seq: number; ts: string; kind: string; payload: Record<string, unknown>; actor: string };

// Artifact Types
export type ArtifactRef = { artifact_id: string; kind: string; media_type: string; size_bytes: number; content_hash: string; created_at: string; storage_ref: string; title?: string };

// Tool Types
export type ToolRow = { tool_id: string; version: string };
export type Approval = { approval_id: string; status: string; tool_id: string; tool_version: string };
export type ToolMetricRow = { tool_id: string; tool_version: string; calls: number; errors: number; last_latency_ms?: number | null; last_error_code?: string | null };

// MCP Types
export type McpServer = { server_id: string; name: string; status: string; last_latency_ms?: number };

// Memory Types
export type MemoryItem = { memory_id: string; type: string; scope_type: string; scope_id?: string | null; title?: string; content: string; updated_at: string };

// Research Types
export type ResearchSource = { source_id: string; title: string; url: string; snippet?: string };

// Workflow Types
export type WorkflowInfo = { workflow_id: string; name: string; version: string };
export type WorkflowRun = { workflow_run_id: string; status: string };

// Registry Types
export type RegistryPackage = { package_id: string; version: string; tier: string; status: string; moderation?: { reports_count?: number } };
export type ToolPin = { tool_id: string; tool_version: string; pinned_at: string };

// Metrics Types
export type RunMetrics = { run_id: string; created_at: string; completed_at?: string | null; duration_ms?: number | null; event_count: number; tool_calls: number; tool_errors: number; artifacts_count: number; bytes_in: number; bytes_out: number };

// Provenance Types
export type ProvenanceSummary = { run_id: string; events_count: number; artifacts_count: number; research_sources_count: number; report_artifact_ids: string[] };
export type ProvenanceNode = { id: string; type: string; label: string; meta: Record<string, unknown> };
export type ProvenanceEdge = { from: string; to: string; kind: string; meta: Record<string, unknown> };
export type ProvenanceGraph = {
  run_id: string;
  generated_at: string;
  truncated?: boolean;
  truncation?: { node_cap_hit?: boolean; edge_cap_hit?: boolean; depth_cap_hit?: boolean };
  nodes: ProvenanceNode[];
  edges: ProvenanceEdge[];
};
export type ProvenanceWhyPath = { nodes: string[]; edges: ProvenanceEdge[] };
export type ProvenanceWhyResponse = { artifact_id: string; paths: ProvenanceWhyPath[]; truncated: boolean };

// User & Collaboration Types
export type Me = { user_id: string; display_name: string; avatar_url?: string; created_at: string; username?: string };
export type Member = { project_id: string; user_id: string; role: string; added_at: string; display_name?: string };
export type CommentRow = { comment_id: string; project_id: string; run_id?: string | null; thread_id?: string | null; target_type: "run" | "event" | "artifact"; target_id: string; author_id: string; body: string; created_at: string };
export type ActivityRow = { activity_id: string; activity_seq: number; project_id: string; kind: string; ref_type: string; ref_id: string; actor_id: string; created_at: string };

// Notification Types
export type NotificationRow = {
  notification_id: string;
  notification_seq: number;
  user_id: string;
  project_id?: string | null;
  run_id?: string | null;
  activity_seq?: number | null;
  kind: string;
  created_at: string;
  payload: Record<string, unknown>;
  read_at?: string | null;
};
export type NotificationStateRow = {
  last_seen_notification_seq: number;
  updated_at: string;
};

// Offline Queue Types
export type OfflineAction = {
  id: string;
  method: string;
  endpoint: string;
  body: unknown;
  idempotency_key: string;
  status: "pending" | "done" | "failed";
  created_at: string;
  last_error?: string;
  scope?: { project_id?: string; run_id?: string };
};

export type DeferredUpload = {
  id: string;
  file: File;
  file_name: string;
  run_id: string;
  kind: string;
  media_type: string;
  title?: string;
  purpose: string;
  status: "pending" | "done" | "failed";
  created_at: string;
  last_error?: string;
};

// System Config Types
export type ProvenanceCaps = { max_depth: number; node_cap: number; edge_cap: number };
