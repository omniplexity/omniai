import { createStore } from "../core/state/store";

export type Toast = {
  id: string;
  message: string;
  backendCode?: string | null;
  requestId?: string | null;
};

type ToastState = {
  toasts: Toast[];
};

export const toastStore = createStore<ToastState>({ toasts: [] });

function nextId(): string {
  return `toast_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
}

export function pushToast(toast: Omit<Toast, "id">): string {
  const id = nextId();
  toastStore.patch({
    toasts: [...toastStore.get().toasts, { id, ...toast }],
  });
  return id;
}

export function dismissToast(id: string): void {
  toastStore.patch({
    toasts: toastStore.get().toasts.filter((t) => t.id !== id),
  });
}

export function clearToasts(): void {
  toastStore.set({ toasts: [] });
}
