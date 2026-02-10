import { useEffect, useMemo, useState } from "preact/hooks";
import { Banner } from "../components/Banner";
import { MessageList } from "../components/MessageList";
import { ChatComposer } from "../components/ChatComposer";
import { ChatController } from "../core/chat/chatController";
import type { ChatMessage, ChatRequest, ChatStreamEvent } from "../core/chat/types";
import {
  chatStore,
  getThreadState,
  setThreadStreaming,
  setThreadError,
  appendMessage,
  patchMessage,
  migrateThread
} from "../core/chat/chatStore";
import { tryLoadMessages } from "../core/chat/chatApi";
import { navigate } from "../core/router/hashRouter";
import { uiPrefsStore, setPrefs } from "../core/prefs/uiPrefsStore";
import { getFlags } from "../core/config/featureFlags";
import { PanelDock } from "../components/PanelDock";

// If you already have a uuid helper from earlier phases, use it instead.
function uuidv4(): string {
  const c = globalThis.crypto as any;
  if (c?.randomUUID) return c.randomUUID();
  const bytes = new Uint8Array(16);
  c.getRandomValues(bytes);
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`;
}

function normalizeHistory(raw: any[]): ChatMessage[] {
  // Best-effort mapping.
  return raw
    .map((x: any) => ({
      id: String(x?.id ?? uuidv4()),
      role: (x?.role ?? x?.author ?? "assistant") as any,
      content: String(x?.content ?? x?.text ?? ""),
      createdAt: Number(x?.createdAt ?? x?.created_at ?? Date.now()),
      status: "done" as const
    }))
    .filter((m) => m.content.length > 0);
}

export function ChatRoute(props: { threadId?: string }) {
  const ctrl = useMemo(() => new ChatController(), []);
  const threadId = props.threadId ?? "new";

  const [state, setState] = useState(getThreadState(threadId));
  useEffect(() => chatStore.subscribe(() => setState(getThreadState(threadId))), [threadId]);

  const [prefs, setLocalPrefs] = useState(uiPrefsStore.get());
  useEffect(() => uiPrefsStore.subscribe(() => setLocalPrefs(uiPrefsStore.get())), []);

  const flags = getFlags();
  const anyPanels = flags.memoryPanel || flags.knowledgePanel || flags.voice || flags.tools;

  // Load history best-effort when navigating to an existing thread.
  useEffect(() => {
    if (!props.threadId) return;
    (async () => {
      const raw = await tryLoadMessages(props.threadId);
      if (raw) {
        const msgs = normalizeHistory(raw);
        // Replace only if store currently empty (avoid clobbering fresh local state).
        if (getThreadState(props.threadId).messages.length === 0) {
          // direct set via helper
          const s = getThreadState(props.threadId);
          // reuse store helper
          // eslint-disable-next-line @typescript-eslint/no-unused-vars
          const _ = s;
          // minimal:
          chatStore.patch({
            byThread: {
              ...chatStore.get().byThread,
              [props.threadId]: { ...getThreadState(props.threadId), messages: msgs }
            }
          });
        }
      }
    })().catch(() => {});
  }, [props.threadId]);

  async function onSend(text: string) {
    const userId = uuidv4();
    const asstId = uuidv4();

    appendMessage(threadId, {
      id: userId,
      role: "user",
      content: text,
      createdAt: Date.now(),
      status: "done"
    });

    appendMessage(threadId, {
      id: asstId,
      role: "assistant",
      content: "",
      createdAt: Date.now(),
      status: "streaming"
    });

    setThreadStreaming(threadId, true);

    const req: ChatRequest = {
      conversation_id: props.threadId, // undefined if new
      input: text,
      client_request_id: uuidv4(),

      // Phase 4: include provider/model/settings
      provider: prefs.providerId ?? undefined,
      model: prefs.modelId ?? undefined,
      settings: {
        temperature: prefs.temperature,
        top_p: prefs.topP,
        max_tokens: prefs.maxTokens
      }
    };

    await ctrl.send(req, {
      onEvent: (ev: ChatStreamEvent) => {
        if (ev.type === "meta" && ev.conversation_id && !props.threadId) {
          // Backend created a thread; migrate local "new" state and navigate.
          migrateThread("new", ev.conversation_id);
          navigate(`/chat/${ev.conversation_id}`);
          return;
        }

        if (ev.type === "delta") {
          // Delta: append to assistant bubble
          const cur = getThreadState(threadId).messages.find((m) => m.id === asstId);
          patchMessage(threadId, asstId, { content: (cur?.content ?? "") + ev.text, status: "streaming" });
          return;
        }

        if (ev.type === "full") {
          // Full message: replace content (not append) - marks end of assistant response
          patchMessage(threadId, asstId, { content: ev.content, status: "streaming" });
          return;
        }

        if (ev.type === "error") {
          patchMessage(threadId, asstId, { status: "error", content: `Error: ${ev.message}` });
          setThreadError(threadId, ev.message);
          return;
        }

        if (ev.type === "stopped") {
          // Stopped: user cancelled, distinct from error
          patchMessage(threadId, asstId, { status: "stopped" });
          setThreadError(threadId);
          return;
        }

        if (ev.type === "done") {
          patchMessage(threadId, asstId, { status: "done" });
          setThreadStreaming(threadId, false);
          return;
        }
      },
      onClosed: () => {
        setThreadStreaming(threadId, false);
      }
    });
  }

  function onStop() {
    ctrl.cancel();
    setThreadStreaming(threadId, false);
  }

  async function onRetry() {
    // Reuse the most recent assistant error/stopped bubble if present.
    const msgs = getThreadState(threadId).messages;
    const lastAsst = [...msgs].reverse().find((m) => m.role === "assistant");
    if (!lastAsst) return;

    // Get conversation ID from props or state
    const convId = props.threadId || threadId;
    if (!convId || convId === "new") {
      // Can't retry without a conversation
      return;
    }

    patchMessage(threadId, lastAsst.id, { content: "", status: "streaming" });
    setThreadStreaming(threadId, true);

    // Call retry with conversation_id and message_id for /v1/chat/retry
    await ctrl.retry(convId, lastAsst.id, {
      onEvent: (ev) => {
        if (ev.type === "delta") {
          const cur = getThreadState(threadId).messages.find((m) => m.id === lastAsst.id);
          patchMessage(threadId, lastAsst.id, { content: (cur?.content ?? "") + ev.text, status: "streaming" });
        } else if (ev.type === "error") {
          if (ev.message === "stopped") {
            patchMessage(threadId, lastAsst.id, { status: "stopped" });
            setThreadError(threadId);
          } else {
            patchMessage(threadId, lastAsst.id, { status: "error", content: `Error: ${ev.message}` });
            setThreadError(threadId, ev.message);
          }
        } else if (ev.type === "done") {
          patchMessage(threadId, lastAsst.id, { status: "done" });
          setThreadStreaming(threadId, false);
        }
      },
      onClosed: () => setThreadStreaming(threadId, false)
    });
  }

  return (
    <div class={`chatShell ${prefs.panelDockOpen && anyPanels ? "withDock" : ""}`}>
      {state.lastError ? <Banner kind="error" text={state.lastError} /> : null}

      {anyPanels ? (
        <div class="chatTopRow">
          <button
            class="btn"
            onClick={() => setPrefs({ panelDockOpen: !prefs.panelDockOpen })}
            aria-label="Toggle panels"
          >
            {prefs.panelDockOpen ? "Hide panels" : "Show panels"}
          </button>
        </div>
      ) : null}

      <MessageList messages={state.messages} />
      <ChatComposer streaming={state.streaming} onSend={onSend} onStop={onStop} onRetry={onRetry} />

      {anyPanels ? <PanelDock conversationId={props.threadId ?? null} /> : null}
    </div>
  );
}
