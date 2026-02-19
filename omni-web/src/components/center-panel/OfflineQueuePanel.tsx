import { DeferredUpload, OfflineAction } from "../../types";

interface OfflineQueuePanelProps {
  pendingActions: OfflineAction[];
  deferredUploads: DeferredUpload[];
  uploadProgress: Record<string, number>;
  isOnline: boolean;
  onReplayQueue: () => void;
  onReplayUploads: () => void;
  onDiscardPending: (id: string) => void;
  onDiscardUpload: (id: string) => void;
}

export function OfflineQueuePanel({
  pendingActions,
  deferredUploads,
  uploadProgress,
  isOnline,
  onReplayQueue,
  onReplayUploads,
  onDiscardPending,
  onDiscardUpload,
}: OfflineQueuePanelProps) {
  return (
    <div className="dashboard-container">
      <div className="section-header"><span className="section-title">Offline Queue ({pendingActions.length})</span></div>
      <div className="section-content">
        <button className="btn btn-sm btn-secondary w-full mb-sm" onClick={onReplayQueue} disabled={!isOnline}>Retry Now</button>
        <div className="list" style={{ maxHeight: "220px", overflowY: "auto" }}>
          {pendingActions.slice(0, 50).map((a) => (
            <div key={a.id} className="list-item">
              <div className="list-item-content">
                <div className="list-item-title text-xs">[{a.status}] {a.endpoint}</div>
                {a.last_error && <div className="list-item-subtitle text-xs text-error">{a.last_error.slice(0, 80)}</div>}
              </div>
              <button className="btn btn-ghost btn-sm" onClick={() => onDiscardPending(a.id)}>×</button>
            </div>
          ))}
        </div>

        <div className="mt-md">
          <div className="text-sm font-medium mb-sm">Deferred Uploads</div>
          <button className="btn btn-sm btn-secondary w-full mb-sm" onClick={onReplayUploads} disabled={!isOnline}>Retry Uploads</button>
          <div className="list" style={{ maxHeight: "220px", overflowY: "auto" }}>
            {deferredUploads.slice(0, 50).map((u) => (
              <div key={u.id} className="list-item">
                <div className="list-item-content">
                  <div className="list-item-title text-xs">{u.file_name} [{u.status}]</div>
                  {uploadProgress[`deferred-${u.id}`] !== undefined && <div className="list-item-subtitle text-xs">{uploadProgress[`deferred-${u.id}`]}%</div>}
                </div>
                <button className="btn btn-ghost btn-sm" onClick={() => onDiscardUpload(u.id)}>×</button>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
