import { useCallback, useEffect, useMemo, useState } from "react";
import type { Dispatch, SetStateAction } from "react";
import type { SystemConfigSnapshot } from "./types";

export type SystemConfigStatus = "idle" | "loading" | "ready" | "forbidden" | "error";

type SystemConfigPanelProps = {
  config: SystemConfigSnapshot | null;
  status: SystemConfigStatus;
  error: string;
  fetchedAt?: string;
  rawJson?: string;
  onRefresh: () => void;
  onCopyJson: () => void;
};

function normalizeSystemConfig(cfg: Partial<SystemConfigSnapshot>): SystemConfigSnapshot {
  return {
    notify_tool_errors: Boolean(cfg.notify_tool_errors),
    notify_tool_errors_only_codes: Array.isArray(cfg.notify_tool_errors_only_codes) ? cfg.notify_tool_errors_only_codes.filter((v): v is string => typeof v === "string") : [],
    notify_tool_errors_only_bindings: Array.isArray(cfg.notify_tool_errors_only_bindings) ? cfg.notify_tool_errors_only_bindings.filter((v): v is string => typeof v === "string") : [],
    notify_tool_errors_max_per_run: Number(cfg.notify_tool_errors_max_per_run || 0),
    sse_max_replay: Number(cfg.sse_max_replay || 0),
    sse_heartbeat_seconds: Number(cfg.sse_heartbeat_seconds || 0),
    artifact_max_bytes: Number(cfg.artifact_max_bytes || 0),
    artifact_part_size: Number(cfg.artifact_part_size || 0),
    session_ttl_seconds: Number(cfg.session_ttl_seconds || 0),
    session_sliding_enabled: Boolean(cfg.session_sliding_enabled),
    session_sliding_window_seconds: Number(cfg.session_sliding_window_seconds || 0),
    max_events_per_run: Number(cfg.max_events_per_run || 0),
    max_bytes_per_run: Number(cfg.max_bytes_per_run || 0),
    generated_at: typeof cfg.generated_at === "string" ? cfg.generated_at : undefined,
    contract_version: typeof cfg.contract_version === "string" ? cfg.contract_version : undefined,
    runtime_version: typeof cfg.runtime_version === "string" ? cfg.runtime_version : undefined,
  };
}

async function safeCopyText(value: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(value);
  } catch {
    // ignore clipboard errors
  }
}

export function useSystemConfig(apiBaseUrl: string): {
  opsOpen: boolean;
  setOpsOpen: Dispatch<SetStateAction<boolean>>;
  toggleOps: () => void;
  systemConfig: SystemConfigSnapshot | null;
  systemConfigStatus: SystemConfigStatus;
  systemConfigError: string;
  systemConfigRawJson: string;
  systemConfigFetchedAt: string;
  loadSystemConfig: () => Promise<void>;
  copySystemConfigJson: () => Promise<void>;
  panelProps: SystemConfigPanelProps;
} {
  const [opsOpen, setOpsOpen] = useState(false);
  const [systemConfig, setSystemConfig] = useState<SystemConfigSnapshot | null>(null);
  const [systemConfigStatus, setSystemConfigStatus] = useState<SystemConfigStatus>("idle");
  const [systemConfigError, setSystemConfigError] = useState("");
  const [systemConfigRawJson, setSystemConfigRawJson] = useState("");
  const [systemConfigFetchedAt, setSystemConfigFetchedAt] = useState("");

  const loadSystemConfig = useCallback(async () => {
    setSystemConfigStatus("loading");
    setSystemConfigError("");
    try {
      const res = await fetch(`${apiBaseUrl}/v1/system/config`, { credentials: "include" });
      if (res.status === 403) {
        setSystemConfigStatus("forbidden");
        setSystemConfig(null);
        setSystemConfigRawJson("");
        setSystemConfigFetchedAt("");
        return;
      }
      if (!res.ok) {
        setSystemConfigStatus("error");
        setSystemConfigError(await res.text());
        return;
      }
      const rawText = await res.text();
      setSystemConfigRawJson(rawText);
      setSystemConfigFetchedAt(new Date().toISOString());
      const cfg = (JSON.parse(rawText) as Partial<SystemConfigSnapshot>) ?? {};
      setSystemConfig(normalizeSystemConfig(cfg));
      setSystemConfigStatus("ready");
    } catch (err) {
      setSystemConfigStatus("error");
      setSystemConfigError(err instanceof Error ? err.message : "Failed to load system config");
    }
  }, [apiBaseUrl]);

  const copySystemConfigJson = useCallback(async () => {
    if (!systemConfig && !systemConfigRawJson) return;
    await safeCopyText(systemConfigRawJson || JSON.stringify(systemConfig ?? {}, null, 2));
  }, [systemConfig, systemConfigRawJson]);

  const toggleOps = useCallback(() => {
    setOpsOpen((v) => !v);
  }, []);

  useEffect(() => {
    if (opsOpen) return;
    setSystemConfigStatus("idle");
    setSystemConfigError("");
    // Drop cached payload on close so reopen is always a clean refetch
    setSystemConfig(null);
    setSystemConfigRawJson("");
    setSystemConfigFetchedAt("");
  }, [opsOpen]);

  useEffect(() => {
    if (!opsOpen || systemConfigStatus !== "idle") return;
    void loadSystemConfig();
  }, [opsOpen, systemConfigStatus, loadSystemConfig]);

  const panelProps = useMemo<SystemConfigPanelProps>(() => ({
    config: systemConfig,
    status: systemConfigStatus,
    error: systemConfigError,
    fetchedAt: systemConfigFetchedAt,
    rawJson: systemConfigRawJson,
    onRefresh: () => {
      void loadSystemConfig();
    },
    onCopyJson: () => {
      void copySystemConfigJson();
    },
  }), [systemConfig, systemConfigStatus, systemConfigError, systemConfigFetchedAt, systemConfigRawJson, loadSystemConfig, copySystemConfigJson]);

  return {
    opsOpen,
    setOpsOpen,
    toggleOps,
    systemConfig,
    systemConfigStatus,
    systemConfigError,
    systemConfigRawJson,
    systemConfigFetchedAt,
    loadSystemConfig,
    copySystemConfigJson,
    panelProps,
  };
}
