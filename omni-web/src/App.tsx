import { FormEvent, Suspense, lazy, useEffect, useMemo, useRef, useState } from "react";
import { createSseClient, type SseClient } from "./sse";
import { discardAction, enqueueAction, listPending, markDone, markFailed } from "./offlineQueue";
import { discardDeferredUpload, enqueueDeferredUpload, listPendingDeferredUploads, markDeferredUploadDone, markDeferredUploadFailed } from "./offlineUploads";
import { SystemConfigPanel } from "./system/SystemConfigPanel";
import { useSystemConfig } from "./system/useSystemConfig";
import { Shell } from "./components/layout/Shell";
import { LeftSidebar } from "./components/left-sidebar/LeftSidebar";
import { ChatPanel } from "./components/center-panel/ChatPanel";
import { EditorPanel } from "./components/center-panel/EditorPanel";
import { DashboardPanel } from "./components/center-panel/DashboardPanel";
import { RightSidebar } from "./components/right-sidebar/RightSidebar";
import { LandingPage } from "./components/auth/LandingPage";
import type {
  Project, Thread, Run, RunSummary, ArtifactRef, EventEnvelope, ToolRow, Approval, McpServer,
  MemoryItem, ResearchSource, WorkflowInfo, WorkflowRun, RegistryPackage, ToolPin, RunMetrics,
  ToolMetricRow, ProvenanceSummary, ProvenanceGraph, ProvenanceWhyPath, Me, Member, CommentRow,
  ActivityRow, NotificationRow, ProvenanceCaps
} from "./types";
import type { OfflineAction as OfflineActionType, DeferredUpload as DeferredUploadType } from "./types";

const ProvenanceGraphView = lazy(() => import("./provenance/ProvenanceGraphView").then((m) => ({ default: m.ProvenanceGraphView })));

const DEFAULT_API_BASE_URL = "";
const STORAGE_KEY = "omniai.phase1.context";
const defaultPins = { model: { provider: "stub", model_id: "stub-model", params: {}, seed: null }, tools: [], runtime: { executor_version: "v0" } };

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
  const [runs, setRuns] = useState<Run[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [selectedThreadId, setSelectedThreadId] = useState("");
  const [selectedRunId, setSelectedRunId] = useState("");
  const [activeTab, setActiveTab] = useState<"Chat" | "Editor" | "Dashboard">("Chat");
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
  const [members, setMembers] = useState<Member[]>([]);
  const [newMemberId, setNewMemberId] = useState("");
  const [newMemberRole, setNewMemberRole] = useState("viewer");
  const [comments, setComments] = useState<CommentRow[]>([]);
  const [activity, setActivity] = useState<ActivityRow[]>([]);
  const [projectUnread, setProjectUnread] = useState<Record<string, number>>({});
  const [notifications, setNotifications] = useState<NotificationRow[]>([]);
  const [notificationUnreadCount, setNotificationUnreadCount] = useState(0);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const { opsOpen, toggleOps, loadSystemConfig, panelProps: systemConfigPanelProps } = useSystemConfig(apiBaseUrl);
  const [isOnline, setIsOnline] = useState<boolean>(navigator.onLine);
  const [pendingActions, setPendingActions] = useState<OfflineActionType[]>([]);
  const [replayBusy, setReplayBusy] = useState(false);
  const [deferredUploads, setDeferredUploads] = useState<DeferredUploadType[]>([]);
  const [uploadProgress, setUploadProgress] = useState<Record<string, number>>({});
  const [commentTargetType, setCommentTargetType] = useState<"run" | "event" | "artifact">("run");
  const [commentTargetId, setCommentTargetId] = useState("");
  const [commentBody, setCommentBody] = useState("");
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
  const [reportReason, setReportReason] = useState("malicious");
  const [reportDetails, setReportDetails] = useState("");
  const [mirrorToPackageId, setMirrorToPackageId] = useState("");
  const [statusToSet, setStatusToSet] = useState("verified");
  const [traceKind, setTraceKind] = useState("");
  const [traceToolId, setTraceToolId] = useState("");
  const [traceErrorsOnly, setTraceErrorsOnly] = useState(false);
  const [traceSearch, setTraceSearch] = useState("");
  const isAdmin = String((import.meta as { env?: Record<string, string> }).env?.VITE_OMNI_DEV_MODE || "").toLowerCase() === "true" || import.meta.env.DEV;
  const sseRef = useRef<SseClient | null>(null);
  const activitySseRef = useRef<SseClient | null>(null);
  const notificationsSseRef = useRef<SseClient | null>(null);
  const lastActivitySeqRef = useRef(0);
  const lastNotificationSeqRef = useRef(0);

  const orderedEvents = useMemo(() => [...events].sort((a, b) => a.seq - b.seq), [events]);
  const filteredEvents = useMemo(() => orderedEvents.filter((e) => {
    if (traceKind && e.kind !== traceKind) return false;
    if (traceErrorsOnly && !["tool_error", "system_event", "workflow_node_failed"].includes(e.kind)) return false;
    if (traceToolId && String(e.payload?.tool_id || "") !== traceToolId) return false;
    if (traceSearch && !JSON.stringify(e.payload).toLowerCase().includes(traceSearch.toLowerCase())) return false;
    return true;
  }), [orderedEvents, traceKind, traceToolId, traceErrorsOnly, traceSearch]);

  // Effects
  useEffect(() => {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as { projectId?: string; threadId?: string; runId?: string };
      setSelectedProjectId(parsed.projectId || "");
      setSelectedThreadId(parsed.threadId || "");
      setSelectedRunId(parsed.runId || "");
    }
    void refreshProjects();
  }, []);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ projectId: selectedProjectId, threadId: selectedThreadId, runId: selectedRunId }));
  }, [selectedProjectId, selectedThreadId, selectedRunId]);

  useEffect(() => {
    if (!selectedProjectId) return;
    void Promise.all([refreshThreads(selectedProjectId), loadProjectPins(selectedProjectId)]);
  }, [selectedProjectId]);

  useEffect(() => {
    if (!selectedThreadId) return;
    void refreshRuns(selectedThreadId);
  }, [selectedThreadId]);

  useEffect(() => {
    void loadTools();
    void loadMcpServers();
  }, []);

  useEffect(() => {
    if (!selectedRunId) return;
    void Promise.all([loadEvents(selectedRunId), loadArtifacts(selectedRunId), loadSummary(selectedRunId), loadApprovals(selectedRunId), loadRunMetrics(selectedRunId), loadProvenance(selectedRunId), loadProvenanceGraph(selectedRunId)]);
  }, [selectedRunId]);

  useEffect(() => {
    void loadMemoryItems();
    void loadWorkflows();
    void loadRegistryPackages();
    void loadToolMetrics();
    void bootstrapAuth();
  }, []);

  useEffect(() => {
    if (!me) return;
    void Promise.all([loadNotifications(), loadNotificationUnreadCount()]);
  }, [me]);

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
    if (!selectedProjectId) return;
    void Promise.all([loadMembers(selectedProjectId), loadActivity(selectedProjectId)]);
  }, [selectedProjectId]);

  useEffect(() => {
    if (!selectedProjectId) return;
    void loadComments(selectedProjectId);
  }, [selectedProjectId, selectedRunId]);

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
      await refreshProjects();
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
      await refreshProjects();
    } catch (err) {
      setLoginError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setLoginLoading(false);
    }
  }

  async function logout() {
    if (!csrfToken) return;
    await fetch(`${apiBaseUrl}/v1/auth/logout`, { method: "POST", credentials: "include", headers: { "X-Omni-CSRF": csrfToken } });
    setProjects([]); setThreads([]); setRuns([]); setSelectedProjectId(""); setSelectedThreadId(""); setSelectedRunId(""); setEvents([]);
    setNotifications([]); setNotificationUnreadCount(0); setCsrfToken(""); setMe(null);
  }

  async function refreshProjects() { setProjects((await api<{ projects: Project[] }>("/v1/projects")).projects); }
  async function refreshThreads(projectId: string) { setThreads((await api<{ threads: Thread[] }>(`/v1/projects/${projectId}/threads`)).threads); }
  async function refreshRuns(threadId: string) { setRuns((await api<{ runs: Run[] }>(`/v1/threads/${threadId}/runs`)).runs); }
  async function loadEvents(runId: string) { setEvents((await api<{ events: EventEnvelope[] }>(`/v1/runs/${runId}/events?after_seq=0`)).events); }
  async function loadArtifacts(runId: string) { setArtifacts((await api<{ artifacts: ArtifactRef[] }>(`/v1/runs/${runId}/artifacts`)).artifacts); }
  async function loadSummary(runId: string) { setSummary(await api<RunSummary>(`/v1/runs/${runId}/summary`)); }
  async function loadMe() { setMe(await api<Me>("/v1/me")); }
  async function loadMembers(projectId: string) { setMembers((await api<{ members: Member[] }>(`/v1/projects/${projectId}/members`)).members); }
  async function loadComments(projectId: string) { setComments((await api<{ comments: CommentRow[] }>(`/v1/projects/${projectId}/comments${selectedRunId ? `?run_id=${encodeURIComponent(selectedRunId)}` : ""}`)).comments); }
  async function loadActivity(projectId: string) {
    const data = await api<{ activity: ActivityRow[] }>(`/v1/projects/${projectId}/activity?limit=50`);
    setActivity(data.activity);
    if (data.activity.length) lastActivitySeqRef.current = Math.max(...data.activity.map((a) => Number(a.activity_seq || 0)));
    const unread = await api<{ unread_count: number }>(`/v1/projects/${projectId}/activity/unread`);
    setProjectUnread((prev) => ({ ...prev, [projectId]: unread.unread_count }));
  }
  async function loadNotifications() { setNotifications((await api<{ notifications: NotificationRow[] }>("/v1/notifications?limit=50")).notifications); }
  async function loadNotificationUnreadCount() { setNotificationUnreadCount((await api<{ unread_count: number }>("/v1/notifications/unread_count")).unread_count); }
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
    const p = await api<Project>("/v1/projects", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: `Project ${projects.length + 1}` }) });
    await refreshProjects();
    setSelectedProjectId(p.id);
    setSelectedThreadId(""); setSelectedRunId(""); setThreads([]); setRuns([]);
  }
  async function createThread() {
    const t = await api<Thread>(`/v1/projects/${selectedProjectId}/threads`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title: `Thread ${threads.length + 1}` }) });
    await refreshThreads(selectedProjectId);
    setSelectedThreadId(t.id); setSelectedRunId(""); setRuns([]);
  }
  async function createRun() {
    const r = await api<Run>(`/v1/threads/${selectedThreadId}/runs`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status: "active", pins: defaultPins }) });
    await refreshRuns(selectedThreadId);
    setSelectedRunId(r.id);
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
  async function addMember() {
    if (!selectedProjectId || !newMemberId) return;
    await api(`/v1/projects/${selectedProjectId}/members`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ user_id: newMemberId, role: newMemberRole }) });
    setNewMemberId("");
    await Promise.all([loadMembers(selectedProjectId), loadActivity(selectedProjectId)]);
  }
  async function createComment() {
    if (!selectedProjectId || !commentTargetId || !commentBody.trim()) return;
    const body = { run_id: selectedRunId || null, target_type: commentTargetType, target_id: commentTargetId, body: commentBody };
    const idem = newIdempotencyKey();
    setComments((prev) => [...prev, { comment_id: `pending-${idem}`, project_id: selectedProjectId, run_id: selectedRunId || null, target_type: commentTargetType, target_id: commentTargetId, author_id: me?.user_id || "me", body: commentBody, created_at: new Date().toISOString() }]);
    await enqueueMutation({ method: "POST", endpoint: `/v1/projects/${selectedProjectId}/comments`, body, idempotency_key: idem, scope: { project_id: selectedProjectId, run_id: selectedRunId || undefined } });
    setCommentBody("");
  }
  async function deleteComment(commentId: string) {
    if (!selectedProjectId) return;
    await api(`/v1/projects/${selectedProjectId}/comments/${commentId}`, { method: "DELETE" });
    await Promise.all([loadComments(selectedProjectId), loadActivity(selectedProjectId)]);
  }
  async function reportPackage() {
    if (!selectedPkg || !selectedPkgVersion || !selectedRunId) return;
    await api(`/v1/registry/packages/${selectedPkg}/${selectedPkgVersion}/report`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ reporter: "ui", reason_code: reportReason, details: reportDetails || null, run_id: selectedRunId }) });
    await Promise.all([loadRegistryPackages(), loadEvents(selectedRunId)]);
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

  // Main App
  return (
    <Shell
      leftSidebar={
        <LeftSidebar
          projects={projects}
          threads={threads}
          runs={runs}
          selectedProjectId={selectedProjectId}
          selectedThreadId={selectedThreadId}
          selectedRunId={selectedRunId}
          projectUnread={projectUnread}
          onSelectProject={(id) => { setSelectedProjectId(id); setSelectedThreadId(""); setSelectedRunId(""); }}
          onSelectThread={(id) => { setSelectedThreadId(id); setSelectedRunId(""); }}
          onSelectRun={setSelectedRunId}
          onCreateProject={createProject}
          onCreateThread={createThread}
          onCreateRun={createRun}
          isAdmin={isAdmin}
          onLogout={logout}
          me={me}
          isOnline={isOnline}
        />
      }
      centerPanel={
        <div className="center-content" style={{ display: "flex", flexDirection: "column", height: "100%" }}>
          {/* Tabs */}
          <div className="tabs" style={{ padding: "var(--space-md)" }}>
            {(["Chat", "Editor", "Dashboard"] as const).map((t) => (
              <button key={t} className={`tab ${activeTab === t ? "active" : ""}`} onClick={() => setActiveTab(t)}>
                {t}
              </button>
            ))}
          </div>

          {/* Panel Content */}
          <div style={{ flex: 1, overflow: "auto" }}>
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
                onAddComment={(eventId) => { setCommentTargetType("event"); setCommentTargetId(eventId); }}
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
          </div>
        </div>
      }
      rightSidebar={
        <RightSidebar
          notifications={notifications}
          notificationUnreadCount={notificationUnreadCount}
          notificationsOpen={notificationsOpen}
          onToggleNotifications={() => setNotificationsOpen((v) => !v)}
          onMarkNotificationsRead={() => {}}
          onLoadNotifications={loadNotifications}
          tools={tools}
          approvals={approvals}
          toolMetrics={toolMetrics}
          invokeToolId={invokeToolId}
          invokeInputs={invokeInputs}
          onInvokeTool={invokeTool}
          onToolIdChange={setInvokeToolId}
          onInputsChange={setInvokeInputs}
          onDecideApproval={decideApproval}
          mcpServers={mcpServers}
          selectedMcpServerId={selectedMcpServerId}
          mcpTools={mcpTools}
          mcpToolName={mcpToolName}
          mcpArgs={mcpArgs}
          mcpEndpoint={mcpEndpoint}
          onRegisterMcp={registerMcpServer}
          onEndpointChange={setMcpEndpoint}
          onMcpServerSelect={setSelectedMcpServerId}
          onRefreshMcpCatalog={refreshMcpCatalog}
          onMcpToolSelect={setMcpToolName}
          onMcpArgsChange={setMcpArgs}
          onTryMcpTool={tryMcpTool}
          onPinMcpTool={pinMcpTool}
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
          registryPackages={registryPackages}
          selectedPkg={selectedPkg}
          selectedPkgVersion={selectedPkgVersion}
          projectPins={projectPins}
          pinToolId={pinToolId}
          pinToolVersion={pinToolVersion}
          reportReason={reportReason}
          reportDetails={reportDetails}
          mirrorToPackageId={mirrorToPackageId}
          statusToSet={statusToSet}
          isAdmin={isAdmin}
          onInstallPackage={installPackage}
          onSelectPackage={(p) => { setSelectedPkg(p); setSelectedPkgVersion(registryPackages.find((pkg) => pkg.package_id === p)?.version || ""); }}
          onPackageVersionChange={setSelectedPkgVersion}
          onSetPin={setPin}
          onUninstallPinned={uninstallPinned}
          onPinToolIdChange={setPinToolId}
          onPinToolVersionChange={setPinToolVersion}
          onReportPackage={reportPackage}
          onVerifyPackage={verifyPackage}
          onSetPackageStatus={setPackageStatus}
          onMirrorPackage={mirrorPackage}
          onReportReasonChange={setReportReason}
          onReportDetailsChange={setReportDetails}
          onMirrorToChange={setMirrorToPackageId}
          onStatusToSetChange={setStatusToSet}
          traceKind={traceKind}
          traceToolId={traceToolId}
          traceErrorsOnly={traceErrorsOnly}
          traceSearch={traceSearch}
          filteredEvents={filteredEvents}
          onTraceKindChange={setTraceKind}
          onTraceToolIdChange={setTraceToolId}
          onTraceErrorsOnlyChange={setTraceErrorsOnly}
          onTraceSearchChange={setTraceSearch}
          comments={comments}
          commentTargetType={commentTargetType}
          commentTargetId={commentTargetId}
          commentBody={commentBody}
          onCreateComment={createComment}
          onDeleteComment={deleteComment}
          onCommentTargetTypeChange={setCommentTargetType}
          onCommentTargetIdChange={setCommentTargetId}
          onCommentBodyChange={setCommentBody}
          activity={activity}
          members={members}
          newMemberId={newMemberId}
          newMemberRole={newMemberRole}
          onMarkActivitySeen={() => selectedProjectId && api(`/v1/projects/${selectedProjectId}/activity/mark_seen`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ seq: lastActivitySeqRef.current }) })}
          onAddMember={addMember}
          onNewMemberIdChange={setNewMemberId}
          onNewMemberRoleChange={setNewMemberRole}
          pendingActions={pendingActions}
          deferredUploads={deferredUploads}
          uploadProgress={uploadProgress}
          isOnline={isOnline}
          onReplayQueue={replayQueue}
          onReplayUploads={replayDeferredUploads}
          onDiscardPending={discardPending}
          onDiscardUpload={discardUpload}
          selectedProjectId={selectedProjectId}
          selectedRunId={selectedRunId}
        />
      }
    />
  );
}
