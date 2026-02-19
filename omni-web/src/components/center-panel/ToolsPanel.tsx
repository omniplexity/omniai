import { Approval, ToolRow } from "../../types";

interface ToolsPanelProps {
  tools: ToolRow[];
  approvals: Approval[];
  invokeToolId: string;
  invokeInputs: string;
  selectedRunId: string;
  onInvokeTool: () => void;
  onToolIdChange: (id: string) => void;
  onInputsChange: (inputs: string) => void;
  onDecideApproval: (id: string, action: "approve" | "deny") => void;
}

export function ToolsPanel({
  tools,
  approvals,
  invokeToolId,
  invokeInputs,
  selectedRunId,
  onInvokeTool,
  onToolIdChange,
  onInputsChange,
  onDecideApproval,
}: ToolsPanelProps) {
  const pendingApprovals = approvals.filter((a) => a.status === "pending");
  return (
    <div className="dashboard-container">
      <div className="section-header">
        <span className="section-title">Tools</span>
      </div>
      <div className="section-content">
        <select className="input mb-sm" value={invokeToolId} onChange={(e) => onToolIdChange(e.target.value)}>
          {tools.map((t) => (
            <option key={`${t.tool_id}-${t.version}`} value={t.tool_id}>{t.tool_id}@{t.version}</option>
          ))}
        </select>
        <textarea className="input mb-sm" rows={3} placeholder='{"query": "..."}' value={invokeInputs} onChange={(e) => onInputsChange(e.target.value)} />
        <button className="btn btn-primary mb-sm" onClick={onInvokeTool} disabled={!selectedRunId}>Invoke</button>

        {pendingApprovals.length > 0 && (
          <>
            <div className="text-sm font-medium mb-sm">Pending Approvals</div>
            {pendingApprovals.map((a) => (
              <div key={a.approval_id} className="card mb-sm">
                <div className="card-body p-sm">
                  <div className="text-sm">{a.tool_id}@{a.tool_version}</div>
                  <div className="flex gap-xs mt-sm">
                    <button className="btn btn-success btn-sm" onClick={() => onDecideApproval(a.approval_id, "approve")}>Approve</button>
                    <button className="btn btn-danger btn-sm" onClick={() => onDecideApproval(a.approval_id, "deny")}>Deny</button>
                  </div>
                </div>
              </div>
            ))}
          </>
        )}
      </div>
    </div>
  );
}
