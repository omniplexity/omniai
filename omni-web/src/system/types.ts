export type SystemConfigSnapshot = {
  notify_tool_errors: boolean;
  notify_tool_errors_only_codes: string[];
  notify_tool_errors_only_bindings: string[];
  notify_tool_errors_max_per_run: number;
  sse_max_replay: number;
  sse_heartbeat_seconds: number;
  artifact_max_bytes: number;
  artifact_part_size: number;
  session_ttl_seconds: number;
  session_sliding_enabled: boolean;
  session_sliding_window_seconds: number;
  max_events_per_run: number;
  max_bytes_per_run: number;
  generated_at?: string;
  contract_version?: string;
  runtime_version?: string;
};
