import { useEffect, useState } from "preact/hooks";
import { dismissToast, toastStore } from "./toastStore";

export function ToastCenter() {
  const [state, setState] = useState(toastStore.get());

  useEffect(() => toastStore.subscribe(() => setState(toastStore.get())), []);

  if (!state.toasts.length) return null;

  return (
    <div class="toastCenter" aria-live="polite" data-testid="toast-center">
      {state.toasts.map((toast) => (
        <div class="toastCard" role="status" data-testid="toast-item" key={toast.id}>
          <div class="toastMessage">{toast.message}</div>
          {toast.backendCode || toast.requestId ? (
            <div class="toastMeta mono" data-testid="toast-meta">
              {toast.backendCode ? <span>code={toast.backendCode}</span> : null}
              {toast.requestId ? <span>request_id={toast.requestId}</span> : null}
            </div>
          ) : null}
          <button class="btn toastDismiss" onClick={() => dismissToast(toast.id)} aria-label="Dismiss notification">
            Dismiss
          </button>
        </div>
      ))}
    </div>
  );
}
