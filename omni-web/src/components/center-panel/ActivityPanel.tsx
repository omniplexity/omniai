import { ActivityRow } from "../../types";

interface ActivityPanelProps {
  activity: ActivityRow[];
}

export function ActivityPanel({ activity }: ActivityPanelProps) {
  return (
    <div className="dashboard-container">
      <div className="section-header"><span className="section-title">Activity</span></div>
      <div className="section-content">
        <div className="list" style={{ maxHeight: "420px", overflowY: "auto" }}>
          {activity.slice(0, 100).map((a) => (
            <div key={a.activity_id} className="list-item">
              <div className="list-item-content">
                <div className="list-item-title text-xs">{a.kind}</div>
                <div className="list-item-subtitle text-xs">{a.ref_type}:{a.ref_id} by {a.actor_id}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
