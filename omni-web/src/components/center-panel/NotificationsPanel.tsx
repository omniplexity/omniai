import { NotificationRow } from "../../types";

interface NotificationsPanelProps {
  notifications: NotificationRow[];
  notificationUnreadCount: number;
  onMarkNotificationsRead: (payload: { notification_ids?: string[]; up_to_seq?: number }) => void;
}

export function NotificationsPanel({ notifications, notificationUnreadCount, onMarkNotificationsRead }: NotificationsPanelProps) {
  return (
    <div className="dashboard-container">
      <div className="section-header">
        <span className="section-title">Notifications ({notificationUnreadCount})</span>
      </div>
      <div className="section-content">
        <button
          className="btn btn-sm btn-secondary w-full mb-sm"
          onClick={() => onMarkNotificationsRead({ up_to_seq: Math.max(...notifications.map((n) => n.notification_seq), 0) })}
        >
          Mark All Read
        </button>
        <div className="list">
          {notifications.slice(0, 50).map((n) => (
            <div key={n.notification_id} className="list-item">
              <div className="list-item-content">
                <div className="list-item-title">
                  <span className={`badge badge-${n.read_at ? "default" : "primary"}`}>{n.read_at ? "read" : "unread"}</span>
                </div>
                <div className="list-item-subtitle">{String(n.payload?.summary || n.kind)}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
