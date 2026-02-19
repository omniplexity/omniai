import { ArtifactRef } from "../../types";

interface ArtifactsPanelProps {
  artifacts: ArtifactRef[];
}

export function ArtifactsPanel({ artifacts }: ArtifactsPanelProps) {
  return (
    <div className="dashboard-container">
      <div className="section-header"><span className="section-title">Artifacts</span></div>
      <div className="section-content">
        <div className="list" style={{ maxHeight: "420px", overflowY: "auto" }}>
          {artifacts.map((a) => (
            <div key={a.artifact_id} className="list-item">
              <div className="list-item-content">
                <div className="list-item-title text-xs">{a.title || a.artifact_id.slice(0, 12)}</div>
                <div className="list-item-subtitle text-xs">{a.size_bytes}b</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
