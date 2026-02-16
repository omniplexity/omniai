export type OfflineAction = {
  id: string;
  idempotency_key: string;
  method: "POST";
  endpoint: string;
  body: unknown;
  created_at: string;
  status: "pending" | "failed" | "done";
  last_error?: string;
  scope?: { project_id?: string; run_id?: string };
};

const DB_NAME = "omni_offline_v1";
const STORE = "actions";
const SECRET_KEYS = new Set(["token", "api_key", "secret", "password"]);

function sanitizeForStorage(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(sanitizeForStorage);
  if (value && typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      if (SECRET_KEYS.has(k.toLowerCase())) {
        out[k] = "***";
      } else {
        out[k] = sanitizeForStorage(v);
      }
    }
    return out;
  }
  return value;
}

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE)) {
        const store = db.createObjectStore(STORE, { keyPath: "id" });
        store.createIndex("status", "status", { unique: false });
        store.createIndex("created_at", "created_at", { unique: false });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function tx<T>(mode: IDBTransactionMode, fn: (store: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const t = db.transaction(STORE, mode);
    const store = t.objectStore(STORE);
    const req = fn(store);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
    t.oncomplete = () => db.close();
  });
}

export async function enqueueAction(action: Omit<OfflineAction, "id" | "created_at" | "status">): Promise<OfflineAction> {
  const row: OfflineAction = {
    ...action,
    body: sanitizeForStorage(action.body),
    id: crypto.randomUUID(),
    created_at: new Date().toISOString(),
    status: "pending",
  };
  await tx("readwrite", (s) => s.add(row));
  return row;
}

export async function listActions(): Promise<OfflineAction[]> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const t = db.transaction(STORE, "readonly");
    const req = t.objectStore(STORE).getAll();
    req.onsuccess = () => {
      const rows = (req.result || []) as OfflineAction[];
      rows.sort((a, b) => a.created_at.localeCompare(b.created_at));
      resolve(rows);
    };
    req.onerror = () => reject(req.error);
    t.oncomplete = () => db.close();
  });
}

export async function listPending(): Promise<OfflineAction[]> {
  const rows = await listActions();
  return rows.filter((r) => r.status === "pending" || r.status === "failed");
}

export async function markDone(id: string): Promise<void> {
  const row = await tx("readonly", (s) => s.get(id));
  if (!row) return;
  await tx("readwrite", (s) => s.put({ ...(row as OfflineAction), status: "done", last_error: undefined }));
}

export async function markFailed(id: string, error: string): Promise<void> {
  const row = await tx("readonly", (s) => s.get(id));
  if (!row) return;
  await tx("readwrite", (s) => s.put({ ...(row as OfflineAction), status: "failed", last_error: error.slice(0, 500) }));
}

export async function discardAction(id: string): Promise<void> {
  await tx("readwrite", (s) => s.delete(id));
}
