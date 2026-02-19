import { McpServer } from "../../types";

interface McpBrowserPanelProps {
  mcpServers: McpServer[];
  selectedMcpServerId: string;
  mcpTools: { name: string }[];
  mcpToolName: string;
  mcpArgs: string;
  mcpEndpoint: string;
  selectedRunId: string;
  onRegisterMcp: () => void;
  onEndpointChange: (url: string) => void;
  onMcpServerSelect: (id: string) => void;
  onRefreshMcpCatalog: () => void;
  onMcpToolSelect: (name: string) => void;
  onMcpArgsChange: (args: string) => void;
  onTryMcpTool: () => void;
  onPinMcpTool: () => void;
}

export function McpBrowserPanel({
  mcpServers,
  selectedMcpServerId,
  mcpTools,
  mcpToolName,
  mcpArgs,
  mcpEndpoint,
  selectedRunId,
  onRegisterMcp,
  onEndpointChange,
  onMcpServerSelect,
  onRefreshMcpCatalog,
  onMcpToolSelect,
  onMcpArgsChange,
  onTryMcpTool,
  onPinMcpTool,
}: McpBrowserPanelProps) {
  return (
    <div className="dashboard-container">
      <div className="section-header">
        <div className="flex items-center gap-md">
          <span className="section-title">MCP Browser</span>
        </div>
      </div>
      <div className="card" style={{ maxWidth: "640px" }}>
        <div className="card-body">
          <input
            type="text"
            className="input mb-sm"
            placeholder="MCP Endpoint"
            value={mcpEndpoint}
            onChange={(e) => onEndpointChange(e.target.value)}
          />
          <button className="btn btn-secondary btn-sm mb-sm" onClick={onRegisterMcp}>
            Register Server
          </button>
          <select
            className="input mb-sm"
            value={selectedMcpServerId}
            onChange={(e) => onMcpServerSelect(e.target.value)}
          >
            <option value="">Select server...</option>
            {mcpServers.map((s) => (
              <option key={s.server_id} value={s.server_id}>
                {s.name} ({s.status})
              </option>
            ))}
          </select>
          <button
            className="btn btn-ghost btn-sm mb-sm"
            onClick={onRefreshMcpCatalog}
            disabled={!selectedMcpServerId}
          >
            Refresh Catalog
          </button>
          <select
            className="input mb-sm"
            value={mcpToolName}
            onChange={(e) => onMcpToolSelect(e.target.value)}
            disabled={!selectedMcpServerId}
          >
            {mcpTools.map((t) => (
              <option key={t.name} value={t.name}>{t.name}</option>
            ))}
          </select>
          <textarea
            className="input mb-sm"
            rows={2}
            placeholder='{"text": "hello"}'
            value={mcpArgs}
            onChange={(e) => onMcpArgsChange(e.target.value)}
            disabled={!selectedMcpServerId}
          />
          <div className="flex gap-xs">
            <button
              className="btn btn-primary btn-sm"
              onClick={onTryMcpTool}
              disabled={!selectedRunId || !selectedMcpServerId}
            >
              Try
            </button>
            <button
              className="btn btn-secondary btn-sm"
              onClick={onPinMcpTool}
              disabled={!selectedMcpServerId}
            >
              Pin
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
