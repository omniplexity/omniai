export type DeferredUpload = {
  id: string;
  file: Blob;
  file_name: string;
  kind: string;
  media_type: string;
  title?: string;
  run_id: string;
  purpose: string;
  created_at: string;
  status: "pending" | "failed" | "done";
  last_error?: string;
};

const DB_NAME = "omni_offline_uploads_v1";
const STORE = "uploads";

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE)) {
        const s = db.createObjectStore(STORE, { keyPath: "id" });
        s.createIndex("status", "status", { unique: false });
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
    const req = fn(t.objectStore(STORE));
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
    t.oncomplete = () => db.close();
  });
}

export async function enqueueDeferredUpload(row: Omit<DeferredUpload, "id" | "created_at" | "status">): Promise<DeferredUpload> {
  const full: DeferredUpload = { ...row, id: crypto.randomUUID(), created_at: new Date().toISOString(), status: "pending" };
  await tx("readwrite", (s) => s.add(full));
  return full;
}

export async function listDeferredUploads(): Promise<DeferredUpload[]> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const t = db.transaction(STORE, "readonly");
    const req = t.objectStore(STORE).getAll();
    req.onsuccess = () => resolve(((req.result || []) as DeferredUpload[]).sort((a, b) => a.created_at.localeCompare(b.created_at)));
    req.onerror = () => reject(req.error);
    t.oncomplete = () => db.close();
  });
}

export async function listPendingDeferredUploads(): Promise<DeferredUpload[]> {
  const rows = await listDeferredUploads();
  return rows.filter((r) => r.status === "pending" || r.status === "failed");
}

export async function markDeferredUploadDone(id: string): Promise<void> {
  const row = await tx("readonly", (s) => s.get(id));
  if (!row) return;
  await tx("readwrite", (s) => s.put({ ...(row as DeferredUpload), status: "done", last_error: undefined }));
}

export async function markDeferredUploadFailed(id: string, error: string): Promise<void> {
  const row = await tx("readonly", (s) => s.get(id));
  if (!row) return;
  await tx("readwrite", (s) => s.put({ ...(row as DeferredUpload), status: "failed", last_error: error.slice(0, 500) }));
}

export async function discardDeferredUpload(id: string): Promise<void> {
  await tx("readwrite", (s) => s.delete(id));
}

