import { useEffect, useMemo, useRef, useState } from "preact/hooks";
import type { JSX } from "preact";
import { MessageBubble } from "../components/MessageBubble";
import { useChatStore } from "../store/chatStore";
import { runStore, useRunStore } from "../store/runStore";
import { useConversationStore } from "../store/conversationStore";
import { createChatAdapter } from "../backend/createChatAdapter";
import type { ChatApiAdapter } from "../backend/ChatApiAdapter";
import { toUiError } from "../backend/errors";
import { navigate } from "../core/router/hashRouter";
import { ConversationHttp } from "../backend/ConversationHttp";
import { getRuntimeConfig } from "../config/runtimeConfig";
import { reconcileMessages } from "../store/reconcileMessages";
import { emitClientEvent } from "../telemetry/clientEvents";
import { getDraft, loadUiPersistence, saveDraft, saveLastRun, saveSelectedConversation } from "../store/persistence";
import { hydrateAuth } from "../core/auth/authStore";

const conversationApi = new ConversationHttp();
const ROW_HEIGHT = 88;
const OVERSCAN = 8;

export function MainLayout(props: { threadId?: string }) {
  const { state, actions } = useChatStore();
  const { state: runState, actions: runActions } = useRunStore();
  const { state: convState, actions: convActions } = useConversationStore();
  const adapter = useMemo<ChatApiAdapter>(() => createChatAdapter(), []);
  const runtimeCfg = useMemo(() => getRuntimeConfig(), []);
  const [draft, setDraft] = useState("");
  const [scrollTop, setScrollTop] = useState(0);
  const [viewportHeight, setViewportHeight] = useState(700);

  const listRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);

  const canSend = useMemo(() => {
    const trimmed = draft.trim();
    return !state.isStreaming && trimmed.length > 0 && !!convState.activeConversationId;
  }, [draft, state.isStreaming, convState.activeConversationId]);

  const total = state.messages.length;
  const startIdx = Math.max(0, Math.floor(scrollTop / ROW_HEIGHT) - OVERSCAN);
  const visibleCount = Math.ceil(viewportHeight / ROW_HEIGHT) + OVERSCAN * 2;
  const endIdx = Math.min(total, startIdx + visibleCount);
  const topSpacer = startIdx * ROW_HEIGHT;
  const bottomSpacer = Math.max(0, (total - endIdx) * ROW_HEIGHT);
  const visibleMessages = state.messages.slice(startIdx, endIdx);

  useEffect(() => {
    const el = listRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [state.messages.length, state.streamingAssistantId, state.messages]);

  useEffect(() => {
    const el = listRef.current;
    if (!el) return;
    const onScroll = () => {
      setScrollTop(el.scrollTop);
      setViewportHeight(el.clientHeight);
    };
    onScroll();
    el.addEventListener("scroll", onScroll);
    window.addEventListener("resize", onScroll);
    return () => {
      el.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
    };
  }, []);

  useEffect(() => {
    void initializeConversations(props.threadId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [props.threadId]);

  useEffect(() => {
    if (!convState.activeConversationId) return;
    saveSelectedConversation(convState.activeConversationId);
  }, [convState.activeConversationId]);

  useEffect(() => {
    const id = convState.activeConversationId;
    if (!id) return;
    saveDraft(id, draft);
  }, [draft, convState.activeConversationId]);

  useEffect(() => {
    if (convState.loading) return;
    inputRef.current?.focus();
  }, [convState.loading, convState.activeConversationId]);

  async function initializeConversations(routeThreadId?: string) {
    convActions.setLoading(true);
    try {
      const persisted = loadUiPersistence();
      const list = await conversationApi.listConversations();
      convActions.setConversations(list);
      let targetId = routeThreadId ?? persisted.selectedConversationId ?? null;
      if (targetId && !list.some((c) => c.id === targetId)) targetId = null;
      if (!targetId && list.length > 0) targetId = list[0]?.id ?? null;
      if (!targetId) {
        const created = await conversationApi.createConversation({ title: "New Conversation" });
        convActions.addConversation(created);
        targetId = created.id;
      }
      convActions.setActiveConversationId(targetId);
      if (targetId) {
        await loadConversationMessages(targetId);
        setDraft(getDraft(targetId));
        if (routeThreadId !== targetId) navigate(`/chat/${targetId}`);
      }
    } catch {
      // Keep shell usable even if conversation bootstrap fails.
    } finally {
      convActions.setLoading(false);
    }
  }

  async function loadConversationMessages(conversationId: string) {
    const serverMessages = await conversationApi.getMessages({ conversationId });
    const merged = reconcileMessages({
      localMessages: state.messages,
      serverMessages,
      runState: runStore.getState(),
    });
    actions.setMessages(merged);
  }

  async function onSelectConversation(conversationId: string) {
    if (state.isStreaming) return;
    convActions.setActiveConversationId(conversationId);
    setDraft(getDraft(conversationId));
    navigate(`/chat/${conversationId}`);
    await loadConversationMessages(conversationId);
  }

  async function onNewConversation() {
    if (state.isStreaming) return;
    const created = await conversationApi.createConversation({ title: "New Conversation" });
    convActions.addConversation(created);
    convActions.setActiveConversationId(created.id);
    actions.reset();
    setDraft("");
    navigate(`/chat/${created.id}`);
  }

  async function onSend() {
    const text = draft.trim();
    const activeConversationId = convState.activeConversationId;
    if (!text || state.isStreaming || !activeConversationId) return;

    setDraft("");
    const userMessageId = actions.addUserMessage(text);
    const requestSnapshot = [...state.messages, { role: "user" as const, content: text }].map((m) => ({
      role: m.role,
      content: m.content,
    }));
    const runId = runActions.createRun({
      requestMessages: requestSnapshot,
      conversationId: activeConversationId,
      sourceMessageId: userMessageId,
    });
    runActions.markMessagePending(userMessageId, true, runId);
    await runStream({
      runId,
      conversationId: activeConversationId,
      input: text,
      sourceMessageId: userMessageId,
    });
  }

  async function onRetry() {
    if (state.isStreaming || !runState.lastRunId) return;
    const prior = runState.runsById[runState.lastRunId];
    if (!prior?.conversationId) return;

    const runId = runActions.createRun({
      requestMessages: prior.requestMessages,
      retryOfRunId: prior.id,
      conversationId: prior.conversationId,
      sourceMessageId: prior.sourceMessageId,
    });

    if (prior.sourceMessageId) {
      await runStream({
        runId,
        conversationId: prior.conversationId,
        input: "",
        retryFromMessageId: prior.sourceMessageId,
      });
      return;
    }
    const lastLocalUserId = [...state.messages]
      .reverse()
      .find((m) => m.role === "user")?.id;
    const mappedBackendId = lastLocalUserId
      ? runState.messageMetaById[lastLocalUserId]?.backendMessageId ?? null
      : null;
    if (mappedBackendId) {
      await runStream({
        runId,
        conversationId: prior.conversationId,
        input: "",
        retryFromMessageId: mappedBackendId,
      });
      return;
    }

    const fallbackInput =
      [...prior.requestMessages].reverse().find((m) => m.role === "user")?.content ?? "";
    await runStream({
      runId,
      conversationId: prior.conversationId,
      input: fallbackInput,
    });
  }

  async function runStream(params: {
    runId: string;
    conversationId: string;
    input: string;
    retryFromMessageId?: string;
    sourceMessageId?: string;
  }) {
    const controller = new AbortController();
    actions.setAbortController(controller);
    runActions.attachConversationId(params.runId, params.conversationId);
    if (params.sourceMessageId) runActions.attachSourceMessageId(params.runId, params.sourceMessageId);

    const assistantMsgId = actions.startAssistantMessage("");
    runActions.startRun(params.runId, assistantMsgId);
    emitClientEvent({ type: "run_start", runId: params.runId, conversationId: params.conversationId });
    let firstDeltaEmitted = false;
    let watchdogTimedOut = false;
    const timeoutMs = 20000;
    const batchMs = 33;
    let queuedDelta = "";
    let flushTimer: number | null = null;
    let watchdog: number | null = null;
    const flushQueuedDelta = () => {
      if (!queuedDelta) return;
      actions.appendAssistantDelta(assistantMsgId, queuedDelta);
      queuedDelta = "";
    };
    const scheduleFlush = () => {
      if (flushTimer !== null) return;
      flushTimer = window.setTimeout(() => {
        flushTimer = null;
        flushQueuedDelta();
      }, batchMs);
    };
    const armWatchdog = () => {
      if (watchdog !== null) window.clearTimeout(watchdog);
      watchdog = window.setTimeout(() => {
        watchdogTimedOut = true;
        controller.abort();
      }, timeoutMs);
    };
    armWatchdog();

    try {
      const created = await adapter.createRun({
        conversationId: params.conversationId,
        input: params.input,
        retryFromMessageId: params.retryFromMessageId,
        signal: controller.signal,
      });
      runActions.attachBackendRunId(params.runId, created.runId);
      emitClientEvent({
        type: "run_start",
        runId: params.runId,
        backendRunId: created.runId,
        conversationId: params.conversationId,
      });

      for await (const chunk of adapter.streamRun({ runId: created.runId, signal: controller.signal })) {
        armWatchdog();
        if (chunk.type === "delta") {
          runActions.markDelta(params.runId);
          if (!firstDeltaEmitted) {
            firstDeltaEmitted = true;
            emitClientEvent({
              type: "run_first_delta",
              runId: params.runId,
              backendRunId: created.runId,
              conversationId: params.conversationId,
            });
          }
          queuedDelta += chunk.delta;
          scheduleFlush();
        } else if (chunk.type === "meta") {
          const meta = chunk.meta;
          if (meta.backendRunId) runActions.attachBackendRunId(params.runId, meta.backendRunId);
          if (meta.conversationId) runActions.attachConversationId(params.runId, meta.conversationId);
          if (typeof meta.eventSeq === "number") {
            runActions.attachEventSeq(params.runId, meta.eventSeq);
            if (params.sourceMessageId) runActions.attachMessageEventSeq(params.sourceMessageId, meta.eventSeq);
            runActions.attachMessageEventSeq(assistantMsgId, meta.eventSeq);
          }
          if (meta.sourceMessageId) {
            runActions.attachSourceMessageId(params.runId, meta.sourceMessageId);
            if (params.sourceMessageId) {
              runActions.attachMessageBackendId(params.sourceMessageId, meta.sourceMessageId);
            }
          }
          if (meta.resultMessageId) {
            runActions.attachResultMessageId(params.runId, meta.resultMessageId);
            runActions.attachMessageBackendId(assistantMsgId, meta.resultMessageId);
          }
        } else if (chunk.type === "done") {
          flushQueuedDelta();
          actions.finalizeAssistantMessage(assistantMsgId);
          runActions.markDone(params.runId);
          saveLastRun(params.conversationId, params.runId);
          emitClientEvent({
            type: "run_done",
            runId: params.runId,
            backendRunId: created.runId,
            conversationId: params.conversationId,
          });
          await loadConversationMessages(params.conversationId);
        }
      }
    } catch (err) {
      flushQueuedDelta();
      const uiError = watchdogTimedOut
        ? toUiError(new Error("Stream timed out waiting for events."))
        : toUiError(err);
      actions.replaceMessageContent(assistantMsgId, `⚠️ [${uiError.code}] ${uiError.message}`);
      if (uiError.code === "E_CANCELLED") {
        runActions.markCancelled(params.runId);
        emitClientEvent({
          type: "run_cancel",
          runId: params.runId,
          conversationId: params.conversationId,
        });
      } else {
        if (uiError.code === "E_AUTH") {
          // Canonical auth-state sync path is `/v1/meta` via hydrateAuth.
          void hydrateAuth();
        }
        runActions.markError(params.runId, uiError.code, uiError.message);
        emitClientEvent({
          type: "run_error",
          runId: params.runId,
          conversationId: params.conversationId,
          code: uiError.code,
        });
      }
      actions.finalizeAssistantMessage(assistantMsgId);
    } finally {
      if (flushTimer !== null) window.clearTimeout(flushTimer);
      if (watchdog !== null) window.clearTimeout(watchdog);
      actions.setAbortController(null);
    }
  }

  async function onCancel() {
    const activeRunId = runState.activeRunId;
    const activeRun = activeRunId ? runState.runsById[activeRunId] : null;
    actions.cancelStream();
    if (activeRunId) runActions.markCancelled(activeRunId);
    if (activeRunId) {
      emitClientEvent({
        type: "run_cancel",
        runId: activeRunId,
        backendRunId: activeRun?.backendRunId,
        conversationId: activeRun?.conversationId,
      });
    }

    const flags = getRuntimeConfig().FEATURE_FLAGS ?? {};
    if (!activeRun?.backendRunId || !flags.SERVER_CANCEL) return;
    try {
      await adapter.cancelRun({ runId: activeRun.backendRunId });
    } catch {
      // best-effort server cancel
    }
  }

  function onKeyDown(e: JSX.TargetedKeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Escape" && state.isStreaming) {
      e.preventDefault();
      void onCancel();
      return;
    }
    if ((e.key === "Enter" && !e.shiftKey) || ((e.ctrlKey || e.metaKey) && e.key === "Enter")) {
      e.preventDefault();
      void onSend();
    }
  }

  const showAuthHint = getHint(runState, "E_AUTH");
  const showCsrfHint = getHint(runState, "E_CSRF");

  return (
    <div style={styles.shell}>
      <style>{css}</style>

      <header style={styles.nav}>
        <div style={styles.brand}>
          <div style={styles.logoBox} aria-hidden="true">
            ◼
          </div>
          <div>
            <div style={styles.title}>OmniAI</div>
            <div style={styles.subtitle}>Chat (Phase 4)</div>
          </div>
        </div>

        <div style={styles.navRight}>
          <div style={styles.badge} data-testid="run-status">
            {state.isStreaming ? "Streaming" : "Idle"}
          </div>
          <button
            style={{
              ...styles.sendBtn,
              height: 32,
              padding: "0 10px",
              fontWeight: 600,
              opacity: state.isStreaming ? 1 : 0.55,
              cursor: state.isStreaming ? "pointer" : "not-allowed",
            }}
            onClick={() => void onCancel()}
            disabled={!state.isStreaming}
            aria-label="Cancel stream"
            title="Cancel stream"
            data-testid="cancel-btn"
          >
            Cancel
          </button>
        </div>
      </header>

      <main style={styles.main}>
        <aside style={styles.leftRail} aria-label="Conversations">
          <div style={styles.railCard}>
            <div style={styles.railTitle}>Conversations</div>
            <button style={{ ...styles.sendBtn, width: "100%", height: 34 }} onClick={() => void onNewConversation()}>
              New
            </button>
            <div style={styles.convList} data-testid="conversation-list">
              {convState.items.map((c) => (
                <button
                  key={c.id}
                  style={{
                    ...styles.convItem,
                    background:
                      convState.activeConversationId === c.id
                        ? "rgba(80,140,255,0.18)"
                        : "rgba(255,255,255,0.04)",
                  }}
                  onClick={() => void onSelectConversation(c.id)}
                  data-testid="conversation-item"
                >
                  {c.title || c.id}
                </button>
              ))}
            </div>
          </div>
        </aside>

        <section style={styles.chatPanel} aria-label="Chat transcript">
          <div
            ref={listRef}
            style={styles.transcript}
            data-testid="transcript"
            role="log"
            aria-live="polite"
            aria-relevant="additions text"
          >
            {topSpacer > 0 ? <div style={{ height: topSpacer }} aria-hidden="true" /> : null}
            {visibleMessages.map((m) => (
              <MessageBubble key={m.id} message={m} />
            ))}
            {bottomSpacer > 0 ? <div style={{ height: bottomSpacer }} aria-hidden="true" /> : null}
          </div>

          <div style={styles.composerWrap}>
            <div style={styles.composer}>
              <textarea
                ref={inputRef}
                style={styles.textarea}
                value={draft}
                onInput={(e) => setDraft((e.target as HTMLTextAreaElement).value)}
                onKeyDown={onKeyDown}
                placeholder="Message OmniAI…"
                rows={1}
                aria-label="Message input"
                disabled={state.isStreaming || convState.loading}
                data-testid="composer-input"
              />
              <button
                style={{
                  ...styles.sendBtn,
                  opacity: canSend ? 1 : 0.55,
                  cursor: canSend ? "pointer" : "not-allowed",
                }}
                onClick={() => void onSend()}
                disabled={!canSend}
                aria-label="Send"
                title="Send"
                data-testid="send-btn"
              >
                Send
              </button>
              <button
                style={{
                  ...styles.sendBtn,
                  opacity: runState.lastRunId && !state.isStreaming ? 1 : 0.55,
                  cursor: runState.lastRunId && !state.isStreaming ? "pointer" : "not-allowed",
                }}
                onClick={() => void onRetry()}
                disabled={!runState.lastRunId || state.isStreaming}
                aria-label="Retry"
                title="Retry last request"
                data-testid="retry-btn"
              >
                Retry
              </button>
            </div>
            <div style={styles.hint}>
              Enter to send - Shift+Enter for newline
              {showAuthHint ? (
                <button
                  style={styles.authHintBtn}
                  onClick={() => navigate("/login")}
                  aria-label="Sign in again"
                  data-testid="auth-hint"
                >
                  Sign in again
                </button>
              ) : null}
              {showCsrfHint ? (
                <button
                  style={styles.authHintBtn}
                  onClick={() => window.location.reload()}
                  aria-label="Refresh page"
                  data-testid="csrf-hint"
                >
                  Refresh page
                </button>
              ) : null}
            </div>
          </div>
        </section>

        <aside style={styles.rightRail} aria-label="Run inspector">
          <div style={styles.railCard}>
            <div style={styles.railTitle}>Inspector</div>
            <div style={styles.railItem}>Active run: {runState.activeRunId ?? "none"}</div>
            <div style={styles.railItem}>Last run: {runState.lastRunId ?? "none"}</div>
            {runtimeCfg.BUILD_INFO ? (
              <details style={{ marginTop: 10 }}>
                <summary style={{ cursor: "pointer", fontSize: 12, opacity: 0.8 }}>
                  Build Info
                </summary>
                <div style={styles.railItem}>SHA: {runtimeCfg.BUILD_INFO.build_sha ?? "n/a"}</div>
                <div style={styles.railItem}>
                  Built: {runtimeCfg.BUILD_INFO.build_timestamp ?? "n/a"}
                </div>
                <div style={styles.railItem}>
                  Config hash: {runtimeCfg.BUILD_INFO.runtime_config_hash ?? "n/a"}
                </div>
              </details>
            ) : null}
          </div>
        </aside>
      </main>
    </div>
  );
}

function getHint(runState: ReturnType<typeof useRunStore>["state"], code: string): boolean {
  if (!runState.lastRunId) return false;
  const run = runState.runsById[runState.lastRunId];
  return run?.errorCode === code;
}

const styles: Record<string, JSX.CSSProperties> = {
  shell: {
    height: "100%",
    minHeight: 0,
    display: "flex",
    flexDirection: "column",
    background: "#0b0d10",
    color: "#e9eef5",
    fontFamily:
      'ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, "Helvetica Neue", Arial',
  },
  nav: {
    flex: "0 0 auto",
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "12px 14px",
    borderBottom: "1px solid rgba(255,255,255,0.08)",
    background: "rgba(14,18,24,0.9)",
    backdropFilter: "blur(10px)",
  },
  brand: { display: "flex", gap: 10, alignItems: "center" },
  logoBox: {
    width: 28,
    height: 28,
    borderRadius: 8,
    display: "grid",
    placeItems: "center",
    background: "rgba(255,255,255,0.08)",
    border: "1px solid rgba(255,255,255,0.12)",
    fontSize: 12,
  },
  title: { fontWeight: 650, fontSize: 14, lineHeight: 1.1 },
  subtitle: { fontSize: 12, opacity: 0.7, lineHeight: 1.1, marginTop: 2 },
  navRight: { display: "flex", alignItems: "center", gap: 10 },
  badge: {
    fontSize: 12,
    padding: "6px 10px",
    borderRadius: 999,
    border: "1px solid rgba(255,255,255,0.12)",
    background: "rgba(255,255,255,0.06)",
  },
  main: {
    flex: "1 1 auto",
    minHeight: 0,
    display: "grid",
    gridTemplateColumns: "260px minmax(360px, 1fr) 260px",
    gap: 12,
    padding: 12,
  },
  leftRail: { minHeight: 0 },
  rightRail: { minHeight: 0 },
  railCard: {
    border: "1px solid rgba(255,255,255,0.10)",
    background: "rgba(255,255,255,0.04)",
    borderRadius: 14,
    padding: 12,
    height: "100%",
    minHeight: 0,
  },
  railTitle: { fontSize: 12, fontWeight: 650, opacity: 0.85, marginBottom: 10 },
  railItem: { fontSize: 12, opacity: 0.75, padding: "6px 0" },
  convList: {
    marginTop: 8,
    display: "flex",
    flexDirection: "column",
    gap: 6,
    maxHeight: "calc(100% - 48px)",
    overflowY: "auto",
  },
  convItem: {
    textAlign: "left",
    border: "1px solid rgba(255,255,255,0.12)",
    color: "#e9eef5",
    borderRadius: 8,
    padding: "8px 10px",
    cursor: "pointer",
  },
  chatPanel: {
    minHeight: 0,
    border: "1px solid rgba(255,255,255,0.10)",
    background: "rgba(255,255,255,0.03)",
    borderRadius: 16,
    display: "flex",
    flexDirection: "column",
    overflow: "hidden",
  },
  transcript: {
    flex: "1 1 auto",
    minHeight: 0,
    overflowY: "auto",
    padding: 14,
    display: "flex",
    flexDirection: "column",
    gap: 10,
  },
  composerWrap: {
    flex: "0 0 auto",
    borderTop: "1px solid rgba(255,255,255,0.08)",
    padding: 12,
    background: "rgba(12,14,18,0.85)",
    backdropFilter: "blur(10px)",
  },
  composer: {
    display: "flex",
    gap: 10,
    alignItems: "flex-end",
  },
  textarea: {
    flex: "1 1 auto",
    resize: "none",
    maxHeight: 180,
    minHeight: 44,
    padding: "10px 12px",
    borderRadius: 12,
    border: "1px solid rgba(255,255,255,0.12)",
    background: "rgba(255,255,255,0.05)",
    color: "#e9eef5",
    outline: "none",
    lineHeight: 1.35,
  },
  sendBtn: {
    flex: "0 0 auto",
    height: 44,
    padding: "0 14px",
    borderRadius: 12,
    border: "1px solid rgba(255,255,255,0.12)",
    background: "rgba(255,255,255,0.08)",
    color: "#e9eef5",
    fontWeight: 650,
  },
  hint: { marginTop: 8, fontSize: 12, opacity: 0.65 },
  authHintBtn: {
    marginLeft: 10,
    border: "1px solid rgba(255,255,255,0.2)",
    borderRadius: 8,
    background: "transparent",
    color: "#e9eef5",
    fontSize: 12,
    padding: "4px 8px",
    cursor: "pointer",
  },
};

const css = `
*::-webkit-scrollbar { width: 10px; height: 10px; }
*::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.14); border-radius: 999px; }
*::-webkit-scrollbar-track { background: rgba(255,255,255,0.04); }
textarea { overflow: auto; }

@media (max-width: 980px) {
  main { grid-template-columns: 1fr !important; }
  aside { display: none !important; }
}
`;
