const STORAGE_KEY = "omniai.chat.ui.v1";

type PersistedState = {
  selectedConversationId: string | null;
  draftsByConversation: Record<string, string>;
  lastRunByConversation: Record<string, string>;
};

const EMPTY_STATE: PersistedState = {
  selectedConversationId: null,
  draftsByConversation: {},
  lastRunByConversation: {},
};

export function loadUiPersistence(): PersistedState {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...EMPTY_STATE };
    const parsed = JSON.parse(raw) as Partial<PersistedState>;
    return {
      selectedConversationId:
        typeof parsed.selectedConversationId === "string" ? parsed.selectedConversationId : null,
      draftsByConversation:
        parsed.draftsByConversation && typeof parsed.draftsByConversation === "object"
          ? parsed.draftsByConversation
          : {},
      lastRunByConversation:
        parsed.lastRunByConversation && typeof parsed.lastRunByConversation === "object"
          ? parsed.lastRunByConversation
          : {},
    };
  } catch {
    return { ...EMPTY_STATE };
  }
}

export function saveSelectedConversation(id: string | null): void {
  const next = loadUiPersistence();
  next.selectedConversationId = id;
  persist(next);
}

export function saveDraft(conversationId: string, text: string): void {
  const next = loadUiPersistence();
  next.draftsByConversation[conversationId] = text;
  persist(next);
}

export function getDraft(conversationId: string): string {
  return loadUiPersistence().draftsByConversation[conversationId] ?? "";
}

export function saveLastRun(conversationId: string, runId: string): void {
  const next = loadUiPersistence();
  next.lastRunByConversation[conversationId] = runId;
  persist(next);
}

function persist(next: PersistedState): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    // Non-fatal in private mode/storage restricted contexts.
  }
}

