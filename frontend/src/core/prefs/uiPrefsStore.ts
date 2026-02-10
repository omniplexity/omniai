import { createStore } from "../state/store";

export type UiPrefs = {
  // null = auto (backend decides)
  providerId: string | null;
  modelId: string | null;

  temperature: number; // 0..2
  topP: number;        // 0..1
  maxTokens: number;   // 1..8192 (clamped)

  // Phase 5: panel dock UI state (non-sensitive)
  panelDockOpen: boolean;
  activePanel: "memory" | "knowledge" | "voice" | "tools";
};

const STORAGE_KEY = "omniai.uiPrefs.v1";

const DEFAULTS: UiPrefs = {
  providerId: null,
  modelId: null,
  temperature: 0.7,
  topP: 1.0,
  maxTokens: 1024,
  panelDockOpen: false,
  activePanel: "memory"
};

function clamp(n: number, lo: number, hi: number) {
  return Math.max(lo, Math.min(hi, n));
}

function sanitize(p: Partial<UiPrefs>): UiPrefs {
  return {
    providerId: typeof p.providerId === "string" ? p.providerId : null,
    modelId: typeof p.modelId === "string" ? p.modelId : null,
    temperature: clamp(Number(p.temperature ?? DEFAULTS.temperature), 0, 2),
    topP: clamp(Number(p.topP ?? DEFAULTS.topP), 0, 1),
    maxTokens: clamp(Math.floor(Number(p.maxTokens ?? DEFAULTS.maxTokens)), 1, 8192),
    panelDockOpen: Boolean(p.panelDockOpen ?? DEFAULTS.panelDockOpen),
    activePanel:
      p.activePanel === "memory" || p.activePanel === "knowledge" || p.activePanel === "voice" || p.activePanel === "tools"
        ? p.activePanel
        : DEFAULTS.activePanel
  };
}

function load(): UiPrefs {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULTS;
    const parsed = JSON.parse(raw) as Partial<UiPrefs>;
    return sanitize({ ...DEFAULTS, ...parsed });
  } catch {
    return DEFAULTS;
  }
}

function save(v: UiPrefs) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(v));
  } catch {
    // ignore (storage may be disabled)
  }
}

export const uiPrefsStore = createStore<UiPrefs>(load());

export function setPrefs(partial: Partial<UiPrefs>) {
  const next = sanitize({ ...uiPrefsStore.get(), ...partial });
  uiPrefsStore.set(next);
  save(next);
}

export function resetPrefs() {
  uiPrefsStore.set(DEFAULTS);
  save(DEFAULTS);
}
