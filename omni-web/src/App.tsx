import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { createSseClient, type SseClient } from "./sse";
import { discardAction, enqueueAction, listPending, markDone, markFailed } from "./offlineQueue";
import { discardDeferredUpload, enqueueDeferredUpload, listPendingDeferredUploads, markDeferredUploadDone, markDeferredUploadFailed } from "./offlineUploads";
import { Shell } from "./components/layout/Shell";
import { LeftSidebar } from "./components/left-sidebar/LeftSidebar";
import { ChatPanel } from "./components/center-panel/ChatPanel";
import { EditorPanel } from "./components/center-panel/EditorPanel";
import { DashboardPanel } from "./components/center-panel/DashboardPanel";
import { McpBrowserPanel } from "./components/center-panel/McpBrowserPanel";
import { ToolsPanel } from "./components/center-panel/ToolsPanel";
import { MemoryPanel } from "./components/center-panel/MemoryPanel";
import { RegistryPanel } from "./components/center-panel/RegistryPanel";
import { LandingPage } from "./components/auth/LandingPage";
import type {
  Project, Thread, Run, RunSummary, ArtifactRef, EventEnvelope, ToolRow, Approval, McpServer,
  MemoryItem, ResearchSource, WorkflowInfo, WorkflowRun, RegistryPackage, ToolPin, RunMetrics,
  ToolMetricRow, ProvenanceSummary, ProvenanceGraph, ProvenanceWhyPath, Me, ProvenanceCaps
} from "./types";
import type { OfflineAction as OfflineActionType, DeferredUpload as DeferredUploadType } from "./types";

const DEFAULT_API_BASE_URL = "";
const STORAGE_KEY = "omniai.phase1.context";
const defaultPins = { model: { provider: "stub", model_id: "stub-model", params: {}, seed: null }, tools: [], runtime: { executor_version: "v0" } };
const debugDataIntegrity = String((import.meta as { env?: Record<string, string> }).env?.VITE_OMNI_DEBUG_DATA_INTEGRITY || "").toLowerCase() === "true";

export function App() {
  const [apiBaseUrl, setApiBaseUrl] = useState(DEFAULT_API_BASE_URL);

  // Load runtime config from public folder
  useEffect(() => {
    const configPath = `${import.meta.env.BASE_URL}runtime-config.json`.replace(/\/+/g, "/");
    fetch(configPath)
      .then((res) => res.json())
      .then((config) => {
        if (config.apiBaseUrl) setApiBaseUrl(config.apiBaseUrl);
      })
      .catch(() => {});
  }, []);

  // State
  const [projects, setProjects] = useState<Project[]>([]);
  const [threads, setThreads] = useState<Thread[]>([]);
  const [uncategorizedThreads, setUncategorizedThreads] = useState<Thread[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [selectedThreadId, setSelectedThreadId] = useState("");
  const [selectedRunId, setSelectedRunId] = useState("");
  const [activeTab, setActiveTab] = useState<
    "Chat" | "Editor" | "Dashboard" | "MCP Browser" |
    "Tools" | "Memory" | "Marketplace"
  >("Chat");
  const [events, setEvents] = useState<EventEnvelope[]>([]);
  const [artifacts, setArtifacts] = useState<ArtifactRef[]>([]);
  const [summary, setSummary] = useState<RunSummary | null>(null);
  const [runMetrics, setRunMetrics] = useState<RunMetrics | null>(null);
  const [toolMetrics, setToolMetrics] = useState<ToolMetricRow[]>([]);
  const [provenance, setProvenance] = useState<ProvenanceSummary | null>(null);
  const [provenanceGraph, setProvenanceGraph] = useState<ProvenanceGraph | null>(null);
  const [selectedProvArtifact, setSelectedProvArtifact] = useState("");
  const [selectedProvPaths, setSelectedProvPaths] = useState<ProvenanceWhyPath[]>([]);
  const [selectedProvTruncated, setSelectedProvTruncated] = useState(false);
  const [provenanceViewMode, setProvenanceViewMode] = useState<"list" | "graph">("graph");
  const [provenanceCaps, setProvenanceCaps] = useState<ProvenanceCaps>({ max_depth: 6, node_cap: 5000, edge_cap: 10000 });
  const [provenanceGraphError, setProvenanceGraphError] = useState("");
  const [me, setMe] = useState<Me | null>(null);
  const [projectUnread, setProjectUnread] = useState<Record<string, number>>({});
  const [isOnline, setIsOnline] = useState<boolean>(navigator.onLine);
  const [pendingActions, setPendingActions] = useState<OfflineActionType[]>([]);
  const [replayBusy, setReplayBusy] = useState(false);
  const [deferredUploads, setDeferredUploads] = useState<DeferredUploadType[]>([]);
  const [uploadProgress, setUploadProgress] = useState<Record<string, number>>({});
  const [csrfToken, setCsrfToken] = useState("");
  const [loginUsername, setLoginUsername] = useState("dev-user");
  const [loginPassword, setLoginPassword] = useState("");
  const [loginLoading, setLoginLoading] = useState(false);
  const [loginError, setLoginError] = useState("");
  const [chatText, setChatText] = useState("");
  const [agentMode, setAgentMode] = useState(true);
  const [docTitle, setDocTitle] = useState("Untitled");
  const [docText, setDocText] = useState("");
  const [loadArtifactId, setLoadArtifactId] = useState("");
  const [tools, setTools] = useState<ToolRow[]>([]);
  const [invokeToolId, setInvokeToolId] = useState("web.search");
  const [invokeInputs, setInvokeInputs] = useState("{\"query\":\"omni\"}");
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [mcpServers, setMcpServers] = useState<McpServer[]>([]);
  const [mcpEndpoint, setMcpEndpoint] = useState("http://127.0.0.1:9000/");
  const [selectedMcpServerId, setSelectedMcpServerId] = useState("");
  const [mcpTools, setMcpTools] = useState<Array<{ name: string }>>([]);
  const [mcpToolName, setMcpToolName] = useState("echo");
  const [mcpArgs, setMcpArgs] = useState("{\"text\":\"hello\"}");
  const [memoryItems, setMemoryItems] = useState<MemoryItem[]>([]);
  const [memoryType, setMemoryType] = useState("semantic");
  const [memoryTitle, setMemoryTitle] = useState("");
  const [memoryContent, setMemoryContent] = useState("");
  const [memoryQuery, setMemoryQuery] = useState("");
  const [memoryBudget, setMemoryBudget] = useState(1000);
  const [memoryPreview, setMemoryPreview] = useState("");
  const [researchQuery, setResearchQuery] = useState("OmniAI");
  const [researchSources, setResearchSources] = useState<ResearchSource[]>([]);
  const [researchReport, setResearchReport] = useState("");
  const [workflowGraphJson, setWorkflowGraphJson] = useState("{\"workflow_id\":\"demo\",\"name\":\"demo\",\"version\":\"1\",\"entry_node_id\":\"n1\",\"nodes\":[{\"id\":\"n1\",\"type\":\"transform\",\"config\":{}}],\"edges\":[]}");
  const [workflows, setWorkflows] = useState<WorkflowInfo[]>([]);
  const [selectedWorkflowId, setSelectedWorkflowId] = useState("");
  const [workflowRuns, setWorkflowRuns] = useState<WorkflowRun[]>([]);
  const [registryPackages, setRegistryPackages] = useState<RegistryPackage[]>([]);
  const [selectedPkg, setSelectedPkg] = useState("");
  const [selectedPkgVersion, setSelectedPkgVersion] = useState("");
  const [projectPins, setProjectPins] = useState<ToolPin[]>([]);
  const [pinToolId, setPinToolId] = useState("");
  const [pinToolVersion, setPinToolVersion] = useState("");
  const [mirrorToPackageId, setMirrorToPackageId] = useState("");
  const [statusToSet, setStatusToSet] = useState("verified");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [deletingThreadIds, setDeletingThreadIds] = useState<Record<string, boolean>>({});
  const [deletingProjectIds, setDeletingProjectIds] = useState<Record<string, boolean>>({});
  const [deleteError, setDeleteError] = useState("");
  const isAdmin = String((import.meta as { env?: Record<string, string> }).env?.VITE_OMNI_DEV_MODE || "").toLowerCase() === "true" || import.meta.env.DEV;
  const sseRef = useRef<SseClient | null>(null);

  const orderedEvents = useMemo(() => [...events].sort((a, b) => a.seq - b.seq), [events]);
  const validProjectIds = useMemo(() => new Set(projects.map((p) => p.id)), [projects]);
  const validThreadIds = useMemo(() => new Set([...threads, ...uncategorizedThreads].map((t) => t.id)), [threads, uncategorizedThreads]);
  const validRunIds = useMemo(() => new Set(runs.map((r) => r.id)), [runs]);
  const normalizedProjectId = selectedProjectId && validProjectIds.has(selectedProjectId) ? selectedProjectId : "";
  const normalizedThreadId = selectedThreadId && validThreadIds.has(selectedThreadId) ? selectedThreadId : "";
  const normalizedRunId = selectedRunId && validRunIds.has(selectedRunId) ? selectedRunId : "";
  function logDataIntegrity(event: string, payload: Record<string, unknown>) {
    if (!debugDataIntegrity) return;
    console.debug(`[omni:data-integrity] ${event}`, payload);
  }
  // Restore saved selection from localStorage (no API call)
  // Note: stale IDs are harmless — they'll get cleared when API calls 404
  useEffect(() => {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      try {
        const parsed = JSON.parse(raw) as { projectId?: string; threadId?: string; runId?: string };
        setSelectedProjectId(parsed.projectId || "");
        setSelectedThreadId(parsed.threadId || "");
        setSelectedRunId(parsed.runId || "");
      } catch { /* corrupt storage — ignore */ }
    }
  }, []);

  // Gate all API calls on apiBaseUrl being loaded
  useEffect(() => {
    if (!apiBaseUrl) return;
    void refreshProjects();
    void loadUncategorizedThreads();
  }, [apiBaseUrl]);

  useEffect(() => {
    if (!me || !apiBaseUrl) return;
    void Promise.all([refreshProjects(), loadUncategorizedThreads()]);
  }, [me, apiBaseUrl]);

  useEffect(() => {
    if (selectedProjectId !== normalizedProjectId) setSelectedProjectId(normalizedProjectId);
    if (selectedThreadId !== normalizedThreadId) setSelectedThreadId(normalizedThreadId);
    if (selectedRunId !== normalizedRunId) setSelectedRunId(normalizedRunId);
  }, [selectedProjectId, selectedThreadId, selectedRunId, normalizedProjectId, normalizedThreadId, normalizedRunId]);

  useEffect(() => {
    logDataIntegrity("selection.persist.write", { key: STORAGE_KEY, projectId: normalizedProjectId, threadId: normalizedThreadId, runId: normalizedRunId });
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ projectId: normalizedProjectId, threadId: normalizedThreadId, runId: normalizedRunId }));
  }, [normalizedProjectId, normalizedThreadId, normalizedRunId]);

  useEffect(() => {
    if (!selectedProjectId || !apiBaseUrl) return;
    void Promise.all([refreshThreads(selectedProjectId), loadProjectPins(selectedProjectId)]);
  }, [selectedProjectId, apiBaseUrl]);

  useEffect(() => {
    if (!selectedThreadId || !apiBaseUrl) return;
    void refreshRuns(selectedThreadId);
  }, [selectedThreadId, apiBaseUrl]);

  useEffect(() => {
    if (!apiBaseUrl) return;
    void loadTools();
    void loadMcpServers();
  }, [apiBaseUrl]);

  useEffect(() => {
    if (!selectedRunId || !apiBaseUrl) return;
    Promise.all([loadEvents(selectedRunId), loadArtifacts(selectedRunId), loadSummary(selectedRunId), loadApprovals(selectedRunId), loadRunMetrics(selectedRunId), loadProvenance(selectedRunId), loadProvenanceGraph(selectedRunId)])
      .catch(() => {
        // Run doesn't exist (stale ID) — clear selection
        setSelectedRunId("");
        setEvents([]);
      });
  }, [selectedRunId, apiBaseUrl]);

  useEffect(() => {
    if (!apiBaseUrl) return;
    void loadMemoryItems();
    void loadWorkflows();
    void loadRegistryPackages();
    void loadToolMetrics();
    void bootstrapAuth();
  }, [apiBaseUrl]);

  useEffect(() => {
    if (!selectedRunId) return;
    const last = orderedEvents.length ? orderedEvents[orderedEvents.length - 1].seq : 0;
    sseRef.current?.close();
    let cursor = last;
    sseRef.current = createSseClient<EventEnvelope>(`${apiBaseUrl}/v1/runs/${selectedRunId}/events/stream`, {
      getCursor: () => cursor,
      setCursor: (v) => { cursor = v; },
      onEvent: (event) => {
        setEvents((prev) => (prev.some((p) => p.seq === event.seq || p.event_id === event.event_id) ? prev : [...prev, event]));
        if (event.kind === "artifact_ref") void loadArtifacts(selectedRunId);
      },
    });
    return () => { sseRef.current?.close(); sseRef.current = null; };
  }, [selectedRunId, apiBaseUrl]);

  useEffect(() => {
    const onOnline = () => setIsOnline(true);
    const onOffline = () => setIsOnline(false);
    window.addEventListener("online", onOnline);
    window.addEventListener("offline", onOffline);
    void refreshPendingActions();
    void refreshDeferredUploads();
    return () => {
      window.removeEventListener("online", onOnline);
      window.removeEventListener("offline", onOffline);
    };
  }, []);

  useEffect(() => {
    if (!isOnline || replayBusy) return;
    const timer = window.setInterval(() => {
      void replayQueue();
      void replayDeferredUploads();
    }, 2000);
    void replayQueue();
    void replayDeferredUploads();
    return () => window.clearInterval(timer);
  }, [isOnline, replayBusy, csrfToken]);

  // API helpers
  async function api<T>(path: string, init?: RequestInit): Promise<T> {
    const method = (init?.method || "GET").toUpperCase();
    const headers = new Headers(init?.headers || {});
    if (["POST", "PATCH", "DELETE"].includes(method) && csrfToken) {
      headers.set("X-Omni-CSRF", csrfToken);
    }
    const res = await fetch(`${apiBaseUrl}${path}`, { ...init, headers, credentials: "include" });
    if (!res.ok) throw new Error(await res.text());
    return res.json() as Promise<T>;
  }

  async function refreshPendingActions() { setPendingActions(await listPending()); }
  async function refreshDeferredUploads() { setDeferredUploads(await listPendingDeferredUploads() as DeferredUploadType[]); }
  function newIdempotencyKey() { return crypto.randomUUID(); }
  async function enqueueMutation(action: Omit<OfflineActionType, "id" | "created_at" | "status">) {
    await enqueueAction(action as any);
    await refreshPendingActions();
  }
  async function postWithIdempotency(path: string, body: unknown, idempotencyKey: string): Promise<Response> {
    const headers: Record<string, string> = { "Content-Type": "application/json", "X-Omni-Idempotency-Key": idempotencyKey };
    if (csrfToken) headers["X-Omni-CSRF"] = csrfToken;
    return fetch(`${apiBaseUrl}${path}`, { method: "POST", credentials: "include", headers, body: JSON.stringify(body) });
  }

  async function replayQueue() {
    if (!isOnline || replayBusy || !csrfToken) return;
    setReplayBusy(true);
    try {
      const items = await listPending();
      for (const item of items) {
        try {
          const res = await postWithIdempotency(item.endpoint, item.body, item.idempotency_key);
          if (res.ok) await markDone(item.id);
          else await markFailed(item.id, await res.text() || `HTTP ${res.status}`);
        } catch (e) {
          await markFailed(item.id, e instanceof Error ? e.message : String(e));
          break;
        }
      }
    } finally {
      setReplayBusy(false);
      await refreshPendingActions();
    }
  }

  async function uploadArtifactNow(file: Blob, meta: { run_id: string; kind: string; media_type: string; title?: string; purpose: string }, progressKey: string) {
    const init = await api<{ upload_id: string; artifact_id: string; part_size: number }>("/v1/artifacts/init", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kind: meta.kind, media_type: meta.media_type, title: meta.title || null, size_bytes: file.size, run_id: meta.run_id }),
    });
    const total = file.size;
    let sent = 0, partNo = 1;
    for (let offset = 0; offset < total; offset += init.part_size) {
      const chunk = file.slice(offset, Math.min(offset + init.part_size, total));
      const res = await fetch(`${apiBaseUrl}/v1/artifacts/${init.artifact_id}/parts/${partNo}?upload_id=${encodeURIComponent(init.upload_id)}`, {
        method: "PUT", credentials: "include",
        headers: csrfToken ? { "X-Omni-CSRF": csrfToken } : undefined, body: chunk,
      });
      if (!res.ok) throw new Error(await res.text());
      sent += chunk.size;
      setUploadProgress((p) => ({ ...p, [progressKey]: Math.round((sent / total) * 100) }));
      partNo++;
    }
    const fin = await api<{ artifact_id: string }>(`/v1/artifacts/${init.artifact_id}/finalize`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ upload_id: init.upload_id }),
    });
    await api(`/v1/runs/${meta.run_id}/artifacts/link`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ artifact_id: fin.artifact_id, purpose: meta.purpose }),
    });
    setUploadProgress((p) => ({ ...p, [progressKey]: 100 }));
  }

  async function replayDeferredUploads() {
    if (!isOnline || !csrfToken) return;
    const items = await listPendingDeferredUploads();
    for (const item of items) {
      try {
        await uploadArtifactNow(item.file, { run_id: item.run_id, kind: item.kind, media_type: item.media_type, title: item.title, purpose: item.purpose }, `deferred-${item.id}`);
        await markDeferredUploadDone(item.id);
      } catch (e) {
        await markDeferredUploadFailed(item.id, e instanceof Error ? e.message : String(e));
        break;
      }
    }
    await refreshDeferredUploads();
    if (selectedRunId) await loadArtifacts(selectedRunId);
  }

  async function discardPending(id: string) { await discardAction(id); await refreshPendingActions(); }
  async function discardUpload(id: string) { await discardDeferredUpload(id); await refreshDeferredUploads(); }

  async function bootstrapAuth() {
    try {
      const meRes = await fetch(`${apiBaseUrl}/v1/me`, { credentials: "include" });
      if (!meRes.ok) { setMe(null); setCsrfToken(""); return; }
      const meData = (await meRes.json()) as Me;
      setMe(meData);
      const csrf = await fetch(`${apiBaseUrl}/v1/auth/csrf`, { credentials: "include" });
      if (csrf.ok) setCsrfToken((await csrf.json() as { csrf_token: string }).csrf_token);
    } catch { setMe(null); setCsrfToken(""); }
  }

  async function handleLogin(username: string, password: string) {
    setLoginLoading(true);
    setLoginError("");
    try {
      const res = await fetch(`${apiBaseUrl}/v1/auth/login`, {
        method: "POST", credentials: "include", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password: password || undefined }),
      });
      if (!res.ok) {
        const errorText = await res.text();
        throw new Error(errorText || "Login failed");
      }
      await bootstrapAuth();
      await Promise.all([refreshProjects(), loadUncategorizedThreads()]);
    } catch (err) {
      setLoginError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoginLoading(false);
    }
  }

  async function handleRegister(username: string, password: string, displayName: string) {
    setLoginLoading(true);
    setLoginError("");
    try {
      const res = await fetch(`${apiBaseUrl}/v1/auth/register`, {
        method: "POST", credentials: "include", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password, display_name: displayName }),
      });
      if (!res.ok) {
        const errorText = await res.text();
        throw new Error(errorText || "Registration failed");
      }
      await bootstrapAuth();
      await Promise.all([refreshProjects(), loadUncategorizedThreads()]);
    } catch (err) {
      setLoginError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setLoginLoading(false);
    }
  }

  async function logout() {
    if (!csrfToken) return;
    await fetch(`${apiBaseUrl}/v1/auth/logout`, { method: "POST", credentials: "include", headers: { "X-Omni-CSRF": csrfToken } });
    setProjects([]); setThreads([]); setUncategorizedThreads([]); setRuns([]); setSelectedProjectId(""); setSelectedThreadId(""); setSelectedRunId(""); setEvents([]);
    setCsrfToken(""); setMe(null);
  }

  async function refreshProjects() { setProjects((await api<{ projects: Project[] }>("/v1/projects")).projects); }
  async function refreshThreads(projectId: string) { setThreads((await api<{ threads: Thread[] }>(`/v1/projects/${projectId}/threads`)).threads); }
  async function loadUncategorizedThreads() {
    try {
      const allThreads = (await api<{ threads: Thread[] }>("/v1/threads")).threads;
      // Filter to only uncategorized threads (those without a project_id)
      setUncategorizedThreads(allThreads.filter(t => !t.project_id));
    } catch { setUncategorizedThreads([]); }
  }
  async function refreshRuns(threadId: string) {
    const data = await api<{ runs: Run[] }>(`/v1/threads/${threadId}/runs`);
    setRuns(data.runs);
    // Auto-select the latest run, or create one if none exist
    if (data.runs.length > 0) {
      const latest = data.runs[data.runs.length - 1];
      if (!selectedRunId || !data.runs.some(r => r.id === selectedRunId)) {
        setSelectedRunId(latest.id);
      }
    } else {
      // No runs yet — auto-create one so the chat is immediately usable
      try {
        logDataIntegrity("run.autocreate.trigger", { threadId, reason: "thread has no runs" });
        const r = await api<Run>(`/v1/threads/${threadId}/runs`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status: "active", pins: defaultPins }) });
        setRuns([r]);
        setSelectedRunId(r.id);
        setEvents([]);
      } catch {
        // Silently fail — user can still see the welcome screen
      }
    }
  }
  async function loadEvents(runId: string) { setEvents((await api<{ events: EventEnvelope[] }>(`/v1/runs/${runId}/events?after_seq=0`)).events); }
  async function loadArtifacts(runId: string) { setArtifacts((await api<{ artifacts: ArtifactRef[] }>(`/v1/runs/${runId}/artifacts`)).artifacts); }
  async function loadSummary(runId: string) { setSummary(await api<RunSummary>(`/v1/runs/${runId}/summary`)); }
  async function loadMe() { setMe(await api<Me>("/v1/me")); }
  async function loadRunMetrics(runId: string) { setRunMetrics(await api<RunMetrics>(`/v1/runs/${runId}/metrics`)); }
  async function loadToolMetrics() { setToolMetrics((await api<{ tools: ToolMetricRow[] }>("/v1/tools/metrics")).tools); }
  async function loadProvenance(runId: string) { setProvenance(await api<ProvenanceSummary>(`/v1/runs/${runId}/provenance`)); }
  async function loadProvenanceGraph(runId: string, caps?: Partial<ProvenanceCaps>) {
    const resolved = { ...provenanceCaps, ...(caps || {}) };
    const qs = new URLSearchParams({ max_depth: String(resolved.max_depth), node_cap: String(resolved.node_cap), edge_cap: String(resolved.edge_cap) });
    try {
      const data = await api<ProvenanceGraph>(`/v1/runs/${runId}/provenance/graph?${qs.toString()}`);
      setProvenanceGraph(data);
      setProvenanceGraphError("");
      if (data.truncated && (data.truncation?.node_cap_hit || data.truncation?.edge_cap_hit)) setProvenanceViewMode("list");
    } catch (err) {
      setProvenanceGraphError(err instanceof Error ? err.message : "graph fetch failed");
      setProvenanceViewMode("list");
    }
  }
  async function loadProvenanceWhy(artifactNodeId: string) {
    if (!selectedRunId || !artifactNodeId) { setSelectedProvPaths([]); setSelectedProvTruncated(false); return; }
    const artifactId = artifactNodeId.startsWith("artifact:") ? artifactNodeId.slice("artifact:".length) : artifactNodeId;
    const data = await api<{ paths: ProvenanceWhyPath[]; truncated: boolean }>(`/v1/runs/${selectedRunId}/provenance/why?artifact_id=${encodeURIComponent(artifactId)}&max_paths=5&max_depth=8`);
    setSelectedProvPaths(data.paths);
    setSelectedProvTruncated(data.truncated);
  }
  function exportProvenanceGraph() {
    if (!provenanceGraph) return;
    const blob = new Blob([JSON.stringify(provenanceGraph, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url; a.download = `provenance-${provenanceGraph.run_id}.json`; a.click();
    URL.revokeObjectURL(url);
  }
  async function loadTools() { setTools((await api<{ tools: ToolRow[] }>("/v1/tools")).tools); }
  async function loadApprovals(runId: string) { setApprovals((await api<{ approvals: Approval[] }>(`/v1/runs/${runId}/approvals`)).approvals); }
  async function loadMcpServers() { setMcpServers((await api<{ servers: McpServer[] }>("/v1/mcp/servers")).servers); }
  async function loadMemoryItems() { setMemoryItems((await api<{ items: MemoryItem[] }>("/v1/memory/items")).items); }
  async function loadWorkflows() { setWorkflows((await api<{ workflows: WorkflowInfo[] }>("/v1/workflows")).workflows); }
  async function loadRegistryPackages() { setRegistryPackages((await api<{ packages: RegistryPackage[] }>("/v1/registry/packages")).packages); }
  async function loadProjectPins(projectId: string) { setProjectPins((await api<{ pins: ToolPin[] }>(`/v1/projects/${projectId}/tools/pins`)).pins); }
  async function loadWorkflowRuns() { if (!selectedRunId) return; setWorkflowRuns((await api<{ workflow_runs: WorkflowRun[] }>(`/v1/runs/${selectedRunId}/workflow_runs`)).workflow_runs); }
  async function refreshMcpCatalog() {
    if (!selectedMcpServerId) return;
    await api(`/v1/mcp/servers/${selectedMcpServerId}/catalog/refresh`, { method: "POST" });
    const tools = await api<{ tools: Array<{ name: string }> }>(`/v1/mcp/servers/${selectedMcpServerId}/tools`);
    setMcpTools(tools.tools);
    if (tools.tools[0]?.name) setMcpToolName(tools.tools[0].name);
  }

  async function createProject() {
    logDataIntegrity("project.create.trigger", { existingProjectCount: projects.length });
    const p = await api<Project>("/v1/projects", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: `Project ${projects.length + 1}` }) });
    await refreshProjects();
    setSelectedProjectId(p.id);
    setSelectedThreadId(""); setSelectedRunId(""); setThreads([]); setRuns([]);
  }
  async function createThread() {
    try {
      // Create uncategorized thread (no project)
      const t = await api<Thread>("/v1/threads", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title: `Chat ${(uncategorizedThreads.length || 0) + 1}` }) });
      await loadUncategorizedThreads();
      setSelectedProjectId("");
      setSelectedThreadId(t.id);
      // Auto-create a run so the chat interface is immediately usable
      try {
        logDataIntegrity("run.autocreate.trigger", { threadId: t.id, reason: "new thread created" });
        const r = await api<Run>(`/v1/threads/${t.id}/runs`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status: "active", pins: defaultPins }) });
        setRuns([r]);
        setSelectedRunId(r.id);
        setEvents([]);
      } catch {
        setSelectedRunId("");
        setRuns([]);
      }
    } catch (err) {
      console.error("Failed to create thread:", err);
    }
  }
  async function createRun() {
    const r = await api<Run>(`/v1/threads/${selectedThreadId}/runs`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status: "active", pins: defaultPins }) });
    await refreshRuns(selectedThreadId);
    setSelectedRunId(r.id);
  }
  async function deleteThread(threadId: string) {
    if (deletingThreadIds[threadId]) return;
    setDeleteError("");
    setDeletingThreadIds((prev) => ({ ...prev, [threadId]: true }));
    logDataIntegrity("thread.delete.before", {
      threadId,
      selectedThreadId,
      selectedProjectId,
      threadCount: threads.length + uncategorizedThreads.length,
    });
    try {
      await api(`/v1/threads/${threadId}`, { method: "DELETE" });
      const wasSelected = selectedThreadId === threadId;
      setThreads(prev => prev.filter(t => t.id !== threadId));
      setUncategorizedThreads(prev => prev.filter(t => t.id !== threadId));
      if (wasSelected) {
        setSelectedThreadId("");
        setSelectedRunId("");
        setRuns([]);
        setEvents([]);
      }
      await Promise.all([
        refreshProjects(),
        loadUncategorizedThreads(),
        selectedProjectId ? refreshThreads(selectedProjectId) : Promise.resolve(),
      ]);
      logDataIntegrity("thread.delete.after", { threadId, wasSelected });
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setDeleteError(`Failed to delete chat: ${message}`);
      logDataIntegrity("thread.delete.error", { threadId, message });
    } finally {
      setDeletingThreadIds((prev) => {
        const next = { ...prev };
        delete next[threadId];
        return next;
      });
    }
  }
  async function deleteProject(projectId: string) {
    if (deletingProjectIds[projectId]) return;
    setDeleteError("");
    setDeletingProjectIds((prev) => ({ ...prev, [projectId]: true }));
    const affectedThreadIds = new Set(threads.filter(t => t.project_id === projectId).map(t => t.id));
    const selectedThreadWasDeleted = affectedThreadIds.has(selectedThreadId);
    logDataIntegrity("project.delete.before", {
      projectId,
      selectedProjectId,
      selectedThreadId,
      selectedRunId,
      projectCount: projects.length,
      affectedThreadCount: affectedThreadIds.size,
    });
    try {
      await api(`/v1/projects/${projectId}`, { method: "DELETE" });
      setProjects(prev => prev.filter(p => p.id !== projectId));
      setThreads(prev => prev.filter(t => t.project_id !== projectId));
      if (selectedProjectId === projectId || selectedThreadWasDeleted) {
        setSelectedProjectId("");
        setSelectedThreadId("");
        setSelectedRunId("");
        setRuns([]);
        setEvents([]);
      }
      await Promise.all([refreshProjects(), loadUncategorizedThreads()]);
      logDataIntegrity("project.delete.after", { projectId, selectedThreadWasDeleted });
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setDeleteError(`Failed to delete project: ${message}`);
      logDataIntegrity("project.delete.error", { projectId, message });
    } finally {
      setDeletingProjectIds((prev) => {
        const next = { ...prev };
        delete next[projectId];
        return next;
      });
    }
  }
  async function installPackage() {
    if (!selectedProjectId || !selectedRunId || !selectedPkg || !selectedPkgVersion) return;
    await api(`/v1/projects/${selectedProjectId}/tools/install`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ package_id: selectedPkg, version: selectedPkgVersion, run_id: selectedRunId }) });
    await Promise.all([loadTools(), loadProjectPins(selectedProjectId), loadApprovals(selectedRunId), loadEvents(selectedRunId)]);
  }
  async function uninstallPinned(toolId: string) {
    if (!selectedProjectId || !selectedRunId) return;
    await api(`/v1/projects/${selectedProjectId}/tools/uninstall`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ tool_id: toolId, run_id: selectedRunId }) });
    await Promise.all([loadTools(), loadProjectPins(selectedProjectId), loadEvents(selectedRunId)]);
  }
  async function setPin() {
    if (!selectedProjectId || !selectedRunId || !pinToolId || !pinToolVersion) return;
    await api(`/v1/projects/${selectedProjectId}/tools/pins`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ tool_id: pinToolId, tool_version: pinToolVersion, run_id: selectedRunId }) });
    await Promise.all([loadProjectPins(selectedProjectId), loadEvents(selectedRunId)]);
  }
  async function verifyPackage() {
    if (!selectedPkg || !selectedPkgVersion || !selectedRunId) return;
    await api(`/v1/registry/packages/${selectedPkg}/${selectedPkgVersion}/verify`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ run_id: selectedRunId }) });
    await Promise.all([loadRegistryPackages(), loadEvents(selectedRunId)]);
  }
  async function setPackageStatus() {
    if (!selectedPkg || !selectedPkgVersion || !selectedRunId) return;
    await api(`/v1/registry/packages/${selectedPkg}/${selectedPkgVersion}/status`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ to_status: statusToSet, run_id: selectedRunId }) });
    await Promise.all([loadRegistryPackages(), loadEvents(selectedRunId)]);
  }
  async function mirrorPackage() {
    if (!selectedPkg || !selectedPkgVersion || !selectedRunId || !mirrorToPackageId) return;
    await api(`/v1/registry/packages/${selectedPkg}/${selectedPkgVersion}/mirror`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ to_package_id: mirrorToPackageId, run_id: selectedRunId }) });
    await loadRegistryPackages();
  }

  async function sendChat(e: FormEvent) {
    e.preventDefault();
    if (!selectedRunId || !chatText.trim()) return;
    const text = chatText.trim();
    const body = { kind: "user_message", actor: "user", payload: { text }, privacy: { redact_level: "none", contains_secrets: false }, pins: defaultPins };
    const idem = newIdempotencyKey();
    setEvents((prev) => [...prev, { event_id: `pending-${idem}`, run_id: selectedRunId, thread_id: "", project_id: selectedProjectId, seq: (prev[prev.length - 1]?.seq || 0) + 1, ts: new Date().toISOString(), kind: "user_message", payload: { text }, actor: "user" } as EventEnvelope]);
    await enqueueMutation({ method: "POST", endpoint: `/v1/runs/${selectedRunId}/events`, body, idempotency_key: idem, scope: { project_id: selectedProjectId, run_id: selectedRunId } });
    setChatText("");
    await api(`/v1/runs/${selectedRunId}/agent_stub`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ user_text: text, mode: agentMode ? "agent" : "simple" }) });
    await loadSummary(selectedRunId);
  }

  async function saveEditorVersion() {
    if (!selectedRunId) return;
    await api(`/v1/runs/${selectedRunId}/editor/documents`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title: docTitle, media_type: "text/markdown", content_text: docText }) });
    await loadArtifacts(selectedRunId);
    await loadSummary(selectedRunId);
  }
  async function uploadArtifactFromFile(file: File) {
    if (!selectedRunId) return;
    const meta = { run_id: selectedRunId, kind: "blob", media_type: file.type || "application/octet-stream", title: file.name, purpose: "upload" };
    if (!isOnline) { await enqueueDeferredUpload({ file, file_name: file.name, ...meta }); await refreshDeferredUploads(); return; }
    try {
      await uploadArtifactNow(file, meta, `live-${file.name}`);
      await loadArtifacts(selectedRunId);
    } catch { await enqueueDeferredUpload({ file, file_name: file.name, ...meta }); await refreshDeferredUploads(); }
  }
  async function loadVersion() {
    if (!loadArtifactId) return;
    const data = await api<{ content_text?: string; title?: string }>(`/v1/artifacts/${loadArtifactId}`);
    setDocText(data.content_text || "");
    if (data.title) setDocTitle(data.title);
    if (selectedRunId) await api(`/v1/runs/${selectedRunId}/events`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ kind: "editor_action", actor: "system", payload: { action: "version_loaded", title: data.title || docTitle, artifact_id: loadArtifactId, media_type: "text/markdown" }, privacy: { redact_level: "none", contains_secrets: false }, pins: defaultPins }) });
  }
  async function invokeTool() {
    if (!selectedRunId) return;
    const parsed = JSON.parse(invokeInputs) as Record<string, unknown>;
    await api(`/v1/runs/${selectedRunId}/tools/invoke`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ tool_id: invokeToolId, inputs: parsed }) });
    await Promise.all([loadEvents(selectedRunId), loadSummary(selectedRunId), loadApprovals(selectedRunId), loadRunMetrics(selectedRunId), loadToolMetrics()]);
  }
  async function decideApproval(approvalId: string, action: "approve" | "deny") {
    if (!selectedRunId) return;
    await api(`/v1/runs/${selectedRunId}/approvals/${approvalId}/${action}`, { method: "POST" });
    await Promise.all([loadEvents(selectedRunId), loadSummary(selectedRunId), loadApprovals(selectedRunId)]);
  }
  async function registerMcpServer() {
    const created = await api<McpServer>("/v1/mcp/servers", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ scope_type: "workspace", name: "mcp", transport: "http", endpoint_url: mcpEndpoint }) });
    setSelectedMcpServerId(created.server_id);
    await loadMcpServers();
  }
  async function tryMcpTool() {
    if (!selectedRunId || !selectedMcpServerId) return;
    const args = JSON.parse(mcpArgs) as Record<string, unknown>;
    await api(`/v1/runs/${selectedRunId}/mcp/${selectedMcpServerId}/try_tool`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: mcpToolName, arguments: args }) });
    await loadEvents(selectedRunId);
  }
  async function pinMcpTool() {
    if (!selectedMcpServerId) return;
    await api(`/v1/mcp/servers/${selectedMcpServerId}/pin_tool`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ tool_name: mcpToolName, tool_id: `mcp.${mcpToolName}`, version: "1.0.0" }) });
    await loadTools();
  }
  async function createMemory() {
    const body = { type: memoryType, scope_type: selectedThreadId ? "thread" : "workspace", scope_id: selectedThreadId || null, title: memoryTitle || null, content: memoryContent, tags: [], importance: 0.5, privacy: { redact_level: "none", contains_secrets: false, do_not_store: false }, provenance: { source_kind: "manual", project_id: selectedProjectId || null, thread_id: selectedThreadId || null, run_id: selectedRunId || null } };
    const idem = newIdempotencyKey();
    setMemoryItems((prev) => [...prev, { memory_id: `pending-${idem}`, type: memoryType, scope_type: body.scope_type, scope_id: body.scope_id, title: memoryTitle || undefined, content: memoryContent, updated_at: new Date().toISOString() }]);
    await enqueueMutation({ method: "POST", endpoint: "/v1/memory/items", body, idempotency_key: idem, scope: { project_id: selectedProjectId || undefined, run_id: selectedRunId || undefined } });
    setMemoryContent("");
    await loadMemoryItems();
  }
  async function deleteMemory(memoryId: string) { await api(`/v1/memory/items/${memoryId}`, { method: "DELETE" }); await loadMemoryItems(); }
  async function searchMemory() {
    const res = await api<{ composed_context: string }>("/v1/memory/search", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ query: memoryQuery, scope_type: selectedThreadId ? "thread" : "workspace", scope_id: selectedThreadId || null, top_k: 5, budget_chars: memoryBudget }) });
    setMemoryPreview(res.composed_context);
  }
  async function promoteEventToMemory(eventId: string) {
    if (!selectedRunId) return;
    await api(`/v1/runs/${selectedRunId}/memory/promote`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ source_event_id: eventId, type: "episodic", scope_type: selectedThreadId ? "thread" : "workspace", scope_id: selectedThreadId || null, title: "Promoted chat" }) });
    await loadMemoryItems();
  }
  async function promoteArtifactToMemory(artifactId: string) {
    if (!selectedRunId) return;
    await api(`/v1/runs/${selectedRunId}/memory/promote`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ source_artifact_id: artifactId, type: "procedural", scope_type: selectedThreadId ? "thread" : "workspace", scope_id: selectedThreadId || null, title: "Promoted artifact" }) });
    await loadMemoryItems();
  }
  async function startResearch() {
    if (!selectedRunId) return;
    const r = await api<{ report_artifact_id: string }>(`/v1/runs/${selectedRunId}/research/start`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ query: researchQuery, mode: "tool_driven", top_k: 2 }) });
    const src = await api<{ sources: ResearchSource[] }>(`/v1/runs/${selectedRunId}/research/sources`);
    setResearchSources(src.sources);
    const report = await api<{ content_text: string }>(`/v1/artifacts/${r.report_artifact_id}`);
    setResearchReport(report.content_text);
    await loadEvents(selectedRunId);
  }
  async function defineWorkflow() {
    const graph = JSON.parse(workflowGraphJson);
    await api("/v1/workflows", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: graph.name || "wf", version: graph.version || "1", graph }) });
    await loadWorkflows();
  }
  async function startWorkflow() {
    if (!selectedRunId || !selectedWorkflowId) return;
    const wf = workflows.find((w) => w.workflow_id === selectedWorkflowId);
    if (!wf) return;
    await api(`/v1/runs/${selectedRunId}/workflows/${wf.workflow_id}/${wf.version}/start`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ inputs: {} }) });
    await Promise.all([loadWorkflowRuns(), loadEvents(selectedRunId)]);
  }

  // Login screen - use new LandingPage component
  if (!me) {
    return (
      <LandingPage
        onLogin={handleLogin}
        onRegister={handleRegister}
        isLoading={loginLoading}
        error={loginError}
      />
    );
  }

  // Right sidebar migration map:
  // Tools/Approvals -> Tools tab
  // Memory -> Memory tab
  // Marketplace/Pins/Admin -> Marketplace tab
  // Main App
  return (
    <Shell
      sidebarCollapsed={sidebarCollapsed}
      onExpandSidebar={() => setSidebarCollapsed(false)}
      leftSidebar={
        <LeftSidebar
          projects={projects}
          threads={threads}
          uncategorizedThreads={uncategorizedThreads}
          runs={runs}
          selectedProjectId={selectedProjectId}
          selectedThreadId={selectedThreadId}
          selectedRunId={selectedRunId}
          projectUnread={projectUnread}
          onSelectProject={(id) => { setSelectedProjectId(id); setSelectedThreadId(""); setSelectedRunId(""); }}
          onSelectThread={(id) => {
            // Check if this is an uncategorized thread — if so, clear project selection
            const isUncategorized = uncategorizedThreads.some(t => t.id === id);
            if (isUncategorized) setSelectedProjectId("");
            setSelectedThreadId(id);
            setSelectedRunId("");
          }}
          onSelectRun={setSelectedRunId}
          onCreateProject={createProject}
          onCreateThread={createThread}
          onCreateRun={createRun}
          onNewChat={() => { void createThread(); }}
          onSearchChats={() => { /* TODO: Open search */ }}
          onImages={() => { /* TODO: Navigate to images */ }}
          onPlugins={() => { /* TODO: Navigate to plugins */ }}
          onDeepResearch={() => { /* TODO: Navigate to deep research */ }}
          onMcpBrowser={() => setActiveTab("MCP Browser")}
          onOpenTools={() => setActiveTab("Tools")}
          onOpenMemory={() => setActiveTab("Memory")}
          onOpenMarketplace={() => setActiveTab("Marketplace")}
          onRenameThread={(threadId, newTitle) => {
            setThreads(prev => prev.map(t => t.id === threadId ? { ...t, title: newTitle } : t));
            setUncategorizedThreads(prev => prev.map(t => t.id === threadId ? { ...t, title: newTitle } : t));
            // TODO: backend PATCH /v1/threads/:id
          }}
          onMoveThread={(threadId, projectId) => {
            // Move from uncategorized to a project
            const thread = uncategorizedThreads.find(t => t.id === threadId) || threads.find(t => t.id === threadId);
            if (thread) {
              setUncategorizedThreads(prev => prev.filter(t => t.id !== threadId));
              setThreads(prev => {
                const exists = prev.some(t => t.id === threadId);
                if (exists) return prev.map(t => t.id === threadId ? { ...t, project_id: projectId } : t);
                return [...prev, { ...thread, project_id: projectId }];
              });
            }
            // TODO: backend PATCH /v1/threads/:id
          }}
          onRemoveFromProject={(threadId) => {
            // Move from project to uncategorized
            const thread = threads.find(t => t.id === threadId);
            if (thread) {
              setThreads(prev => prev.filter(t => t.id !== threadId));
              setUncategorizedThreads(prev => [...prev, { ...thread, project_id: "" }]);
            }
            // TODO: backend PATCH /v1/threads/:id
          }}
          onArchiveThread={(threadId) => {
            setThreads(prev => prev.filter(t => t.id !== threadId));
            setUncategorizedThreads(prev => prev.filter(t => t.id !== threadId));
            if (selectedThreadId === threadId) { setSelectedThreadId(""); setSelectedRunId(""); }
            // TODO: backend PATCH /v1/threads/:id { archived_at: ... }
          }}
          onDeleteThread={async (threadId) => {
            if (!confirm("Delete this chat? This cannot be undone.")) return;
            await deleteThread(threadId);
          }}
          onRenameProject={(projectId, newName) => {
            setProjects(prev => prev.map(p => p.id === projectId ? { ...p, name: newName } : p));
            // TODO: backend PATCH /v1/projects/:id
          }}
          onDeleteProject={async (projectId) => {
            if (!confirm("Delete this project and all its threads? This cannot be undone.")) return;
            await deleteProject(projectId);
          }}
          deletingThreadIds={deletingThreadIds}
          deletingProjectIds={deletingProjectIds}
          deleteError={deleteError}
          onCollapseSidebar={() => setSidebarCollapsed(true)}
          onUpdateUser={async (data) => {
            if (!csrfToken) return;
            await api("/v1/me", {
              method: "PATCH",
              headers: { "Content-Type": "application/json", "X-Omni-CSRF": csrfToken },
              body: JSON.stringify(data),
            });
            await bootstrapAuth();
          }}
          isAdmin={isAdmin}
          onLogout={logout}
          me={me}
          isOnline={isOnline}
        />
      }
      centerPanel={
        <div className="center-content" style={{ display: "flex", flexDirection: "column", height: "100%" }}>
          {/* Toolbar — replaces old tab bar */}
          <div className="center-toolbar">
            <div className="center-toolbar-left">
              {selectedRunId ? (
                <span className="center-toolbar-title">
                  {threads.find(t => t.id === selectedThreadId)?.title || "Conversation"}
                </span>
              ) : (
                <span className="center-toolbar-title">OmniAI</span>
              )}
            </div>
            <div className="center-toolbar-right">
              <button
                className={`toolbar-btn ${activeTab === "Chat" ? "active" : ""}`}
                onClick={() => setActiveTab("Chat")}
                title="Chat"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                </svg>
              </button>
              <button
                className={`toolbar-btn ${activeTab === "Editor" ? "active" : ""}`}
                onClick={() => setActiveTab("Editor")}
                title="Editor"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                  <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
                </svg>
              </button>
              <button
                className={`toolbar-btn ${activeTab === "Dashboard" ? "active" : ""}`}
                onClick={() => setActiveTab("Dashboard")}
                title="Dashboard"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <rect x="3" y="3" width="7" height="7" />
                  <rect x="14" y="3" width="7" height="7" />
                  <rect x="14" y="14" width="7" height="7" />
                  <rect x="3" y="14" width="7" height="7" />
                </svg>
              </button>
            </div>
          </div>

          {/* Panel Content */}
          <div style={{ flex: 1, overflow: "hidden" }}>
            {activeTab === "Chat" && (
              <ChatPanel
                events={events}
                chatText={chatText}
                agentMode={agentMode}
                selectedRunId={selectedRunId}
                onSendMessage={sendChat}
                onTextChange={setChatText}
                onModeChange={setAgentMode}
                onPromoteToMemory={promoteEventToMemory}
              />
            )}
            {activeTab === "Editor" && (
              <EditorPanel
                docTitle={docTitle}
                docText={docText}
                artifacts={artifacts}
                loadArtifactId={loadArtifactId}
                selectedRunId={selectedRunId}
                onTitleChange={setDocTitle}
                onTextChange={setDocText}
                onSave={saveEditorVersion}
                onLoadArtifact={setLoadArtifactId}
                onFileUpload={uploadArtifactFromFile}
                onPromoteToMemory={promoteArtifactToMemory}
              />
            )}
            {activeTab === "Dashboard" && (
              <DashboardPanel
                summary={summary}
                runMetrics={runMetrics}
                provenance={provenance}
                provenanceGraph={provenanceGraph}
                provenanceError={provenanceGraphError}
                selectedProvArtifact={selectedProvArtifact}
                selectedProvPaths={selectedProvPaths}
                selectedProvTruncated={selectedProvTruncated}
                provenanceViewMode={provenanceViewMode}
                provenanceCaps={provenanceCaps}
                artifacts={artifacts}
                researchQuery={researchQuery}
                researchSources={researchSources}
                researchReport={researchReport}
                workflowGraphJson={workflowGraphJson}
                workflows={workflows}
                selectedWorkflowId={selectedWorkflowId}
                workflowRuns={workflowRuns}
                selectedRunId={selectedRunId}
                onStartResearch={startResearch}
                onResearchQueryChange={setResearchQuery}
                onDefineWorkflow={defineWorkflow}
                onWorkflowGraphChange={setWorkflowGraphJson}
                onStartWorkflow={startWorkflow}
                onLoadWorkflowRuns={loadWorkflowRuns}
                onSelectWorkflow={setSelectedWorkflowId}
                onExportProvenance={exportProvenanceGraph}
                onRefetchProvenance={() => selectedRunId && loadProvenanceGraph(selectedRunId)}
                onProvenanceCapsChange={(caps) => setProvenanceCaps((prev) => ({ ...prev, ...caps }))}
                onProvenanceViewModeChange={setProvenanceViewMode}
                onArtifactSelect={(id) => { setSelectedProvArtifact(id); void loadProvenanceWhy(id); }}
              />
            )}
            {activeTab === "MCP Browser" && (
              <McpBrowserPanel
                mcpServers={mcpServers}
                selectedMcpServerId={selectedMcpServerId}
                mcpTools={mcpTools}
                mcpToolName={mcpToolName}
                mcpArgs={mcpArgs}
                mcpEndpoint={mcpEndpoint}
                selectedRunId={selectedRunId}
                onRegisterMcp={registerMcpServer}
                onEndpointChange={setMcpEndpoint}
                onMcpServerSelect={setSelectedMcpServerId}
                onRefreshMcpCatalog={refreshMcpCatalog}
                onMcpToolSelect={setMcpToolName}
                onMcpArgsChange={setMcpArgs}
                onTryMcpTool={tryMcpTool}
                onPinMcpTool={pinMcpTool}
              />
            )}
            {activeTab === "Tools" && (
              <ToolsPanel
                tools={tools}
                approvals={approvals}
                invokeToolId={invokeToolId}
                invokeInputs={invokeInputs}
                selectedRunId={selectedRunId}
                onInvokeTool={invokeTool}
                onToolIdChange={setInvokeToolId}
                onInputsChange={setInvokeInputs}
                onDecideApproval={decideApproval}
              />
            )}
            {activeTab === "Memory" && (
              <MemoryPanel
                memoryItems={memoryItems}
                memoryType={memoryType}
                memoryTitle={memoryTitle}
                memoryContent={memoryContent}
                memoryQuery={memoryQuery}
                memoryBudget={memoryBudget}
                memoryPreview={memoryPreview}
                onCreateMemory={createMemory}
                onDeleteMemory={deleteMemory}
                onSearchMemory={searchMemory}
                onMemoryTypeChange={setMemoryType}
                onMemoryTitleChange={setMemoryTitle}
                onMemoryContentChange={setMemoryContent}
                onMemoryQueryChange={setMemoryQuery}
                onMemoryBudgetChange={setMemoryBudget}
              />
            )}
            {activeTab === "Marketplace" && (
              <RegistryPanel
                registryPackages={registryPackages}
                selectedPkg={selectedPkg}
                selectedPkgVersion={selectedPkgVersion}
                projectPins={projectPins}
                pinToolId={pinToolId}
                pinToolVersion={pinToolVersion}
                mirrorToPackageId={mirrorToPackageId}
                statusToSet={statusToSet}
                isAdmin={isAdmin}
                selectedProjectId={selectedProjectId}
                selectedRunId={selectedRunId}
                onInstallPackage={installPackage}
                onSelectPackage={(p) => { setSelectedPkg(p); setSelectedPkgVersion(registryPackages.find((pkg) => pkg.package_id === p)?.version || ""); }}
                onPackageVersionChange={setSelectedPkgVersion}
                onSetPin={setPin}
                onUninstallPinned={uninstallPinned}
                onPinToolIdChange={setPinToolId}
                onPinToolVersionChange={setPinToolVersion}
                onVerifyPackage={verifyPackage}
                onSetPackageStatus={setPackageStatus}
                onMirrorPackage={mirrorPackage}
                onMirrorToChange={setMirrorToPackageId}
                onStatusToSetChange={setStatusToSet}
              />
            )}
          </div>
        </div>
      }
    />
  );
}
