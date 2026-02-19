import { Member } from "../../types";

interface CollaborationPanelProps {
  members: Member[];
  newMemberId: string;
  newMemberRole: string;
  selectedProjectId: string;
  onAddMember: () => void;
  onNewMemberIdChange: (id: string) => void;
  onNewMemberRoleChange: (role: string) => void;
}

export function CollaborationPanel({
  members,
  newMemberId,
  newMemberRole,
  selectedProjectId,
  onAddMember,
  onNewMemberIdChange,
  onNewMemberRoleChange,
}: CollaborationPanelProps) {
  return (
    <div className="dashboard-container">
      <div className="section-header"><span className="section-title">Collaboration</span></div>
      <div className="section-content">
        <div className="list mb-sm">
          {members.map((m) => (
            <div key={m.user_id} className="list-item">
              <div className="list-item-content"><div className="list-item-title">{m.display_name || m.user_id} <span className="badge badge-default ml-xs">{m.role}</span></div></div>
            </div>
          ))}
        </div>
        <div className="flex gap-xs mb-sm">
          <input type="text" className="input" placeholder="user id" value={newMemberId} onChange={(e) => onNewMemberIdChange(e.target.value)} />
          <select className="input" value={newMemberRole} onChange={(e) => onNewMemberRoleChange(e.target.value)} style={{ width: "100px" }}>
            <option value="viewer">viewer</option><option value="editor">editor</option><option value="owner">owner</option>
          </select>
        </div>
        <button className="btn btn-secondary btn-sm" onClick={onAddMember} disabled={!selectedProjectId}>Add Member</button>
      </div>
    </div>
  );
}
