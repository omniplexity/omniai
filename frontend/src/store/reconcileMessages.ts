import type { ChatMessage } from "./chatStore";
import type { ConversationMessage } from "../backend/ConversationApi";
import type { RunState } from "./runStore";

type ReconcileParams = {
  localMessages: ChatMessage[];
  serverMessages: ConversationMessage[];
  runState: RunState;
  nowMs?: number;
};

export function reconcileMessages(params: ReconcileParams): ChatMessage[] {
  const nowMs = params.nowMs ?? Date.now();
  const server = params.serverMessages.map((m) => ({
    id: m.id,
    role: m.role,
    content: m.content,
    timestamp: m.created_at,
  })) as ChatMessage[];

  const localEventSeqByBackendId = buildLocalEventSeqByBackendId(params.runState);
  const localEventSeqBySignature = buildLocalEventSeqBySignature(params.localMessages, params.runState);
  const serverOrder = new Map<string, number>();
  server.forEach((item, idx) => serverOrder.set(item.id, idx));
  server.sort((a, b) => {
    const seqA = localEventSeqByBackendId.get(a.id) ?? localEventSeqBySignature.get(sig(a.role, a.content));
    const seqB = localEventSeqByBackendId.get(b.id) ?? localEventSeqBySignature.get(sig(b.role, b.content));
    if (seqA !== undefined && seqB !== undefined && seqA !== seqB) return seqA - seqB;
    return (serverOrder.get(a.id) ?? 0) - (serverOrder.get(b.id) ?? 0);
  });

  const serverIds = new Set(server.map((m) => m.id));
  const serverSig = new Set(server.map((m) => sig(m.role, m.content)));

  const pendingTail: ChatMessage[] = [];
  for (const local of params.localMessages) {
    const meta = params.runState.messageMetaById[local.id];
    if (!meta) continue;
    if (meta.backendMessageId && serverIds.has(meta.backendMessageId)) continue;
    const isPending = Boolean(meta.pending);
    const runStatus = params.runState.runsById[meta.runId]?.status;
    const keepFailed =
      runStatus === "error" || runStatus === "cancelled";
    if (keepFailed) {
      if (!serverSig.has(sig(local.role, local.content))) {
        pendingTail.push(local);
      }
      continue;
    }
    if (!isPending) continue;
    const age = nowMs - Date.parse(local.timestamp);
    if (age > 5 * 60 * 1000) continue;
    if (serverSig.has(sig(local.role, local.content))) continue;
    pendingTail.push(local);
  }

  return [...server, ...pendingTail];
}

function buildLocalEventSeqByBackendId(runState: RunState): Map<string, number> {
  const out = new Map<string, number>();
  for (const meta of Object.values(runState.messageMetaById)) {
    if (!meta.backendMessageId || meta.eventSeq === undefined) continue;
    const prev = out.get(meta.backendMessageId);
    if (prev === undefined || meta.eventSeq < prev) out.set(meta.backendMessageId, meta.eventSeq);
  }
  return out;
}

function buildLocalEventSeqBySignature(localMessages: ChatMessage[], runState: RunState): Map<string, number> {
  const out = new Map<string, number>();
  for (const local of localMessages) {
    const meta = runState.messageMetaById[local.id];
    if (!meta || meta.backendMessageId || meta.eventSeq === undefined) continue;
    const key = sig(local.role, local.content);
    const prev = out.get(key);
    if (prev === undefined || meta.eventSeq < prev) out.set(key, meta.eventSeq);
  }
  return out;
}

function sig(role: string, content: string): string {
  const norm = content.replace(/\s+/g, " ").trim().toLowerCase();
  return `${role}:${norm}`;
}
