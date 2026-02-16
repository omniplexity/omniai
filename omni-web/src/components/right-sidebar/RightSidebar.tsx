import { useState, useEffect } from "react";
import { ToolRow, Approval, McpServer, MemoryItem, RegistryPackage, ToolPin, ToolMetricRow, ArtifactRef, CommentRow, ActivityRow, NotificationRow, OfflineAction, DeferredUpload, Member } from "../../types";

interface RightSidebarProps {
  // Notifications
  notifications: NotificationRow[];
  notificationUnreadCount: number;
  notificationsOpen: boolean;
  onToggleNotifications: () => void;
  onMarkNotificationsRead: (payload: { notification_ids?: string[]; up_to_seq?: number }) => void;
  onLoadNotifications: () => void;
  
  // Tools
  tools: ToolRow[];
  approvals: Approval[];
  toolMetrics: ToolMetricRow[];
  invokeToolId: string;
  invokeInputs: string;
  onInvokeTool: () => void;
  onToolIdChange: (id: string) => void;
  onInputsChange: (inputs: string) => void;
  onDecideApproval: (id: string, action: "approve" | "deny") => void;
  
  // MCP
  mcpServers: McpServer[];
  selectedMcpServerId: string;
  mcpTools: { name: string }[];
  mcpToolName: string;
  mcpArgs: string;
  mcpEndpoint: string;
  onRegisterMcp: () => void;
  onEndpointChange: (url: string) => void;
  onMcpServerSelect: (id: string) => void;
  onRefreshMcpCatalog: () => void;
  onMcpToolSelect: (name: string) => void;
  onMcpArgsChange: (args: string) => void;
  onTryMcpTool: () => void;
  onPinMcpTool: () => void;
  
  // Memory
  memoryItems: MemoryItem[];
  memoryType: string;
  memoryTitle: string;
  memoryContent: string;
  memoryQuery: string;
  memoryBudget: number;
  memoryPreview: string;
  onCreateMemory: () => void;
  onDeleteMemory: (id: string) => void;
  onSearchMemory: () => void;
  onMemoryTypeChange: (type: string) => void;
  onMemoryTitleChange: (title: string) => void;
  onMemoryContentChange: (content: string) => void;
  onMemoryQueryChange: (query: string) => void;
  onMemoryBudgetChange: (budget: number) => void;
  
  // Marketplace
  registryPackages: RegistryPackage[];
  selectedPkg: string;
  selectedPkgVersion: string;
  projectPins: ToolPin[];
  pinToolId: string;
  pinToolVersion: string;
  reportReason: string;
  reportDetails: string;
  mirrorToPackageId: string;
  statusToSet: string;
  isAdmin: boolean;
  onInstallPackage: () => void;
  onSelectPackage: (pkg: string) => void;
  onPackageVersionChange: (version: string) => void;
  onSetPin: () => void;
  onUninstallPinned: (toolId: string) => void;
  onPinToolIdChange: (id: string) => void;
  onPinToolVersionChange: (version: string) => void;
  onReportPackage: () => void;
  onVerifyPackage: () => void;
  onSetPackageStatus: () => void;
  onMirrorPackage: () => void;
  onReportReasonChange: (reason: string) => void;
  onReportDetailsChange: (details: string) => void;
  onMirrorToChange: (id: string) => void;
  onStatusToSetChange: (status: string) => void;
  
  // Timeline & Events
  traceKind: string;
  traceToolId: string;
  traceErrorsOnly: boolean;
  traceSearch: string;
  filteredEvents: any[];
  onTraceKindChange: (kind: string) => void;
  onTraceToolIdChange: (toolId: string) => void;
  onTraceErrorsOnlyChange: (errorsOnly: boolean) => void;
  onTraceSearchChange: (search: string) => void;
  
  // Comments
  comments: CommentRow[];
  commentTargetType: "run" | "event" | "artifact";
  commentTargetId: string;
  commentBody: string;
  onCreateComment: () => void;
  onDeleteComment: (id: string) => void;
  onCommentTargetTypeChange: (type: "run" | "event" | "artifact") => void;
  onCommentTargetIdChange: (id: string) => void;
  onCommentBodyChange: (body: string) => void;
  
  // Activity
  activity: ActivityRow[];
  members: Member[];
  newMemberId: string;
  newMemberRole: string;
  onMarkActivitySeen: () => void;
  onAddMember: () => void;
  onNewMemberIdChange: (id: string) => void;
  onNewMemberRoleChange: (role: string) => void;
  
  // Offline
  pendingActions: OfflineAction[];
  deferredUploads: DeferredUpload[];
  uploadProgress: Record<string, number>;
  isOnline: boolean;
  onReplayQueue: () => void;
  onReplayUploads: () => void;
  onDiscardPending: (id: string) => void;
  onDiscardUpload: (id: string) => void;
  
  selectedProjectId: string;
  selectedRunId: string;
}

// Section configuration
interface SectionConfig {
  id: string;
  title: string;
  icon?: React.ReactNode;
  badge?: string | number;
}

export function RightSidebar({
  notifications,
  notificationUnreadCount,
  notificationsOpen,
  onToggleNotifications,
  onMarkNotificationsRead,
  onLoadNotifications,
  tools,
  approvals,
  toolMetrics,
  invokeToolId,
  invokeInputs,
  onInvokeTool,
  onToolIdChange,
  onInputsChange,
  onDecideApproval,
  mcpServers,
  selectedMcpServerId,
  mcpTools,
  mcpToolName,
  mcpArgs,
  mcpEndpoint,
  onRegisterMcp,
  onEndpointChange,
  onMcpServerSelect,
  onRefreshMcpCatalog,
  onMcpToolSelect,
  onMcpArgsChange,
  onTryMcpTool,
  onPinMcpTool,
  memoryItems,
  memoryType,
  memoryTitle,
  memoryContent,
  memoryQuery,
  memoryBudget,
  memoryPreview,
  onCreateMemory,
  onDeleteMemory,
  onSearchMemory,
  onMemoryTypeChange,
  onMemoryTitleChange,
  onMemoryContentChange,
  onMemoryQueryChange,
  onMemoryBudgetChange,
  registryPackages,
  selectedPkg,
  selectedPkgVersion,
  projectPins,
  pinToolId,
  pinToolVersion,
  reportReason,
  reportDetails,
  mirrorToPackageId,
  statusToSet,
  isAdmin,
  onInstallPackage,
  onSelectPackage,
  onPackageVersionChange,
  onSetPin,
  onUninstallPinned,
  onPinToolIdChange,
  onPinToolVersionChange,
  onReportPackage,
  onVerifyPackage,
  onSetPackageStatus,
  onMirrorPackage,
  onReportReasonChange,
  onReportDetailsChange,
  onMirrorToChange,
  onStatusToSetChange,
  traceKind,
  traceToolId,
  traceErrorsOnly,
  traceSearch,
  filteredEvents,
  onTraceKindChange,
  onTraceToolIdChange,
  onTraceErrorsOnlyChange,
  onTraceSearchChange,
  comments,
  commentTargetType,
  commentTargetId,
  commentBody,
  onCreateComment,
  onDeleteComment,
  onCommentTargetTypeChange,
  onCommentTargetIdChange,
  onCommentBodyChange,
  activity,
  members,
  newMemberId,
  newMemberRole,
  onMarkActivitySeen,
  onAddMember,
  onNewMemberIdChange,
  onNewMemberRoleChange,
  pendingActions,
  deferredUploads,
  uploadProgress,
  isOnline,
  onReplayQueue,
  onReplayUploads,
  onDiscardPending,
  onDiscardUpload,
  selectedProjectId,
  selectedRunId,
}: RightSidebarProps) {
  // Initialize collapsed state from localStorage
  const [collapsedSections, setCollapsedSections] = useState<Record<string, boolean>>(() => {
    const saved = localStorage.getItem('rightbar-collapsed');
    return saved ? JSON.parse(saved) : {
      notifications: false,
      timeline: false,
      tools: true,
      mcp: true,
      memory: true,
      marketplace: true,
      comments: true,
      activity: true,
      collaboration: true,
      metrics: true,
      artifacts: true,
      offline: true,
    };
  });

  // Save collapsed state to localStorage
  useEffect(() => {
    localStorage.setItem('rightbar-collapsed', JSON.stringify(collapsedSections));
  }, [collapsedSections]);

  const toggleSection = (sectionId: string) => {
    setCollapsedSections(prev => ({
      ...prev,
      [sectionId]: !prev[sectionId]
    }));
  };

  // Section header component
  const SectionHeader = ({ id, title, icon, badge }: SectionConfig) => (
    <div className="section-header" onClick={() => toggleSection(id)}>
      <span className="section-title">
        {icon}
        {title}
        {badge !== undefined && <span className="badge badge-primary ml-xs">{badge}</span>}
      </span>
      <svg className="chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M6 9l6 6 6-6" />
      </svg>
    </div>
  );

  return (
    <div className="right-sidebar">
      {/* Notifications */}
      <div className={`section ${collapsedSections.notifications ? 'collapsed' : ''}`}>
        <SectionHeader 
          id="notifications" 
          title="Notifications" 
          badge={notificationUnreadCount}
          icon={
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
              <path d="M13.73 21a2 2 0 0 1-3.46 0" />
            </svg>
          }
        />
        {!collapsedSections.notifications && (
          <div className="section-content">
            <button 
              className="btn btn-sm btn-secondary w-full mb-sm"
              onClick={() => onMarkNotificationsRead({ up_to_seq: Math.max(...notifications.map(n => n.notification_seq), 0) })}
            >
              Mark All Read
            </button>
            <div className="list">
              {notifications.slice(0, 10).map((n) => (
                <div key={n.notification_id} className="list-item">
                  <div className="list-item-content">
                    <div className="list-item-title">
                      <span className={`badge badge-${n.read_at ? "default" : "primary"}`}>
                        {n.read_at ? "read" : "unread"}
                      </span>
                    </div>
                    <div className="list-item-subtitle">
                      {String(n.payload?.summary || n.kind)}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Run Timeline */}
      <div className={`section ${collapsedSections.timeline ? 'collapsed' : ''}`}>
        <SectionHeader 
          id="timeline" 
          title="Timeline"
          icon={
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <polyline points="12 6 12 12 16 14" />
            </svg>
          }
        />
        {!collapsedSections.timeline && (
          <div className="section-content">
            <div className="flex gap-xs mb-sm">
              <input
                type="text"
                className="input"
                placeholder="Kind filter"
                value={traceKind}
                onChange={(e) => onTraceKindChange(e.target.value)}
              />
              <input
                type="text"
                className="input"
                placeholder="Tool filter"
                value={traceToolId}
                onChange={(e) => onTraceToolIdChange(e.target.value)}
              />
            </div>
            <label className="checkbox-label mb-sm">
              <input
                type="checkbox"
                checked={traceErrorsOnly}
                onChange={(e) => onTraceErrorsOnlyChange(e.target.checked)}
              />
              Errors only
            </label>
            <input
              type="text"
              className="input mb-sm"
              placeholder="Search payload..."
              value={traceSearch}
              onChange={(e) => onTraceSearchChange(e.target.value)}
            />
            <div className="list" style={{ maxHeight: "200px", overflowY: "auto" }}>
              {filteredEvents.slice(0, 20).map((e) => (
                <div key={e.seq} className="list-item">
                  <div className="list-item-content">
                    <div className="list-item-title">
                      <span className="badge badge-default">#{e.seq}</span> {e.kind}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Tools */}
      <div className={`section ${collapsedSections.tools ? 'collapsed' : ''}`}>
        <SectionHeader 
          id="tools" 
          title="Tools"
          icon={
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
            </svg>
          }
        />
        {!collapsedSections.tools && (
          <div className="section-content">
            <select
              className="input mb-sm"
              value={invokeToolId}
              onChange={(e) => onToolIdChange(e.target.value)}
            >
              {tools.map((t) => (
                <option key={`${t.tool_id}-${t.version}`} value={t.tool_id}>
                  {t.tool_id}@{t.version}
                </option>
              ))}
            </select>
            <textarea
              className="input mb-sm"
              rows={3}
              placeholder='{"query": "..."}'
              value={invokeInputs}
              onChange={(e) => onInputsChange(e.target.value)}
            />
            <button 
              className="btn btn-primary w-full"
              onClick={onInvokeTool}
              disabled={!selectedRunId}
            >
              Invoke
            </button>
            
            {/* Approvals */}
            {approvals.filter((a) => a.status === "pending").length > 0 && (
              <div className="mt-md">
                <div className="text-sm font-medium mb-sm">Pending Approvals</div>
                {approvals.filter((a) => a.status === "pending").map((a) => (
                  <div key={a.approval_id} className="card mb-sm">
                    <div className="card-body p-sm">
                      <div className="text-sm">{a.tool_id}@{a.tool_version}</div>
                      <div className="flex gap-xs mt-sm">
                        <button 
                          className="btn btn-success btn-sm"
                          onClick={() => onDecideApproval(a.approval_id, "approve")}
                        >
                          Approve
                        </button>
                        <button 
                          className="btn btn-danger btn-sm"
                          onClick={() => onDecideApproval(a.approval_id, "deny")}
                        >
                          Deny
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* MCP Browser */}
      <div className={`section ${collapsedSections.mcp ? 'collapsed' : ''}`}>
        <SectionHeader id="mcp" title="MCP Browser" />
        {!collapsedSections.mcp && (
          <div className="section-content">
            <input
              type="text"
              className="input mb-sm"
              placeholder="MCP Endpoint"
              value={mcpEndpoint}
              onChange={(e) => onEndpointChange(e.target.value)}
            />
            <button className="btn btn-secondary btn-sm w-full mb-sm" onClick={onRegisterMcp}>
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
              className="btn btn-ghost btn-sm w-full mb-sm"
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
        )}
      </div>

      {/* Memory */}
      <div className={`section ${collapsedSections.memory ? 'collapsed' : ''}`}>
        <SectionHeader 
          id="memory" 
          title="Memory"
          icon={
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 3v18M3 12h18" />
            </svg>
          }
        />
        {!collapsedSections.memory && (
          <div className="section-content">
            <select
              className="input mb-sm"
              value={memoryType}
              onChange={(e) => onMemoryTypeChange(e.target.value)}
            >
              <option value="episodic">Episodic</option>
              <option value="semantic">Semantic</option>
              <option value="procedural">Procedural</option>
            </select>
            <input
              type="text"
              className="input mb-sm"
              placeholder="Title"
              value={memoryTitle}
              onChange={(e) => onMemoryTitleChange(e.target.value)}
            />
            <textarea
              className="input mb-sm"
              rows={2}
              placeholder="Content..."
              value={memoryContent}
              onChange={(e) => onMemoryContentChange(e.target.value)}
            />
            <button className="btn btn-primary btn-sm w-full mb-sm" onClick={onCreateMemory}>
              Create
            </button>
            
            <input
              type="text"
              className="input mb-sm"
              placeholder="Search..."
              value={memoryQuery}
              onChange={(e) => onMemoryQueryChange(e.target.value)}
            />
            <div className="flex gap-xs items-center mb-sm">
              <span className="text-sm text-secondary">Budget:</span>
              <input
                type="number"
                className="input"
                value={memoryBudget}
                onChange={(e) => onMemoryBudgetChange(Number(e.target.value))}
                style={{ width: "80px" }}
              />
              <button className="btn btn-ghost btn-sm" onClick={onSearchMemory}>
                Search
              </button>
            </div>
            {memoryPreview && (
              <pre className="text-xs mb-sm" style={{ whiteSpace: "pre-wrap", maxHeight: "100px", overflowY: "auto" }}>
                {memoryPreview}
              </pre>
            )}
            
            <div className="list" style={{ maxHeight: "150px", overflowY: "auto" }}>
              {memoryItems.map((m) => (
                <div key={m.memory_id} className="list-item">
                  <div className="list-item-content">
                    <div className="list-item-title">
                      <span className="badge badge-default">{m.type}</span>
                      {m.title || m.content.slice(0, 20)}
                    </div>
                  </div>
                  <button 
                    className="btn btn-ghost btn-sm"
                    onClick={() => onDeleteMemory(m.memory_id)}
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Marketplace */}
      <div className={`section ${collapsedSections.marketplace ? 'collapsed' : ''}`}>
        <SectionHeader id="marketplace" title="Marketplace" />
        {!collapsedSections.marketplace && (
          <div className="section-content">
            <select
              className="input mb-sm"
              value={selectedPkg}
              onChange={(e) => onSelectPackage(e.target.value)}
            >
              <option value="">Select package...</option>
              {registryPackages.map((p) => (
                <option key={`${p.package_id}-${p.version}`} value={p.package_id}>
                  {p.package_id}@{p.version} [{p.tier}/{p.status}]
                </option>
              ))}
            </select>
            <input
              type="text"
              className="input mb-sm"
              placeholder="Version"
              value={selectedPkgVersion}
              onChange={(e) => onPackageVersionChange(e.target.value)}
            />
            <button 
              className="btn btn-primary btn-sm w-full mb-sm"
              onClick={onInstallPackage}
              disabled={!selectedRunId || !selectedProjectId || !selectedPkg}
            >
              Install
            </button>
            
            {/* Project Pins */}
            <div className="mt-md mb-sm">
              <div className="text-sm font-medium mb-sm">Project Pins</div>
              <div className="list">
                {projectPins.map((p) => (
                  <div key={p.tool_id} className="list-item">
                    <div className="list-item-content">
                      <div className="list-item-title">{p.tool_id}@{p.tool_version}</div>
                    </div>
                    <button 
                      className="btn btn-ghost btn-sm"
                      onClick={() => onUninstallPinned(p.tool_id)}
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
              <div className="flex gap-xs mt-sm">
                <input
                  type="text"
                  className="input"
                  placeholder="tool_id"
                  value={pinToolId}
                  onChange={(e) => onPinToolIdChange(e.target.value)}
                />
                <input
                  type="text"
                  className="input"
                  placeholder="version"
                  value={pinToolVersion}
                  onChange={(e) => onPinToolVersionChange(e.target.value)}
                  style={{ width: "80px" }}
                />
              </div>
              <button 
                className="btn btn-secondary btn-sm w-full"
                onClick={onSetPin}
                disabled={!selectedProjectId || !selectedRunId}
              >
                Set Pin
              </button>
            </div>
            
            {/* Admin Controls */}
            {isAdmin && (
              <div className="mt-md">
                <div className="text-sm font-medium mb-sm">Admin</div>
                <div className="flex gap-xs mb-sm">
                  <button 
                    className="btn btn-success btn-sm"
                    onClick={onVerifyPackage}
                    disabled={!selectedRunId || !selectedPkg}
                  >
                    Verify
                  </button>
                  <input
                    type="text"
                    className="input"
                    placeholder="status"
                    value={statusToSet}
                    onChange={(e) => onStatusToSetChange(e.target.value)}
                    style={{ width: "80px" }}
                  />
                  <button 
                    className="btn btn-secondary btn-sm"
                    onClick={onSetPackageStatus}
                    disabled={!selectedRunId || !selectedPkg}
                  >
                    Set
                  </button>
                </div>
                <div className="flex gap-xs">
                  <input
                    type="text"
                    className="input"
                    placeholder="mirror to..."
                    value={mirrorToPackageId}
                    onChange={(e) => onMirrorToChange(e.target.value)}
                  />
                  <button 
                    className="btn btn-ghost btn-sm"
                    onClick={onMirrorPackage}
                    disabled={!selectedRunId || !selectedPkg || !mirrorToPackageId}
                  >
                    Mirror
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Comments */}
      <div className={`section ${collapsedSections.comments ? 'collapsed' : ''}`}>
        <SectionHeader id="comments" title="Comments" />
        {!collapsedSections.comments && (
          <div className="section-content">
            <div className="flex gap-xs mb-sm">
              <select
                className="input"
                value={commentTargetType}
                onChange={(e) => onCommentTargetTypeChange(e.target.value as "run" | "event" | "artifact")}
              >
                <option value="run">run</option>
                <option value="event">event</option>
                <option value="artifact">artifact</option>
              </select>
              <input
                type="text"
                className="input"
                placeholder="target id"
                value={commentTargetId}
                onChange={(e) => onCommentTargetIdChange(e.target.value)}
              />
            </div>
            <textarea
              className="input mb-sm"
              rows={2}
              placeholder="Comment..."
              value={commentBody}
              onChange={(e) => onCommentBodyChange(e.target.value)}
            />
            <button 
              className="btn btn-primary btn-sm w-full mb-sm"
              onClick={onCreateComment}
              disabled={!selectedProjectId}
            >
              Add Comment
            </button>
            <div className="list">
              {comments.map((c) => (
                <div key={c.comment_id} className="list-item">
                  <div className="list-item-content">
                    <div className="list-item-title">{c.author_id}: {c.body}</div>
                  </div>
                  <button 
                    className="btn btn-ghost btn-sm"
                    onClick={() => onDeleteComment(c.comment_id)}
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Activity */}
      <div className={`section ${collapsedSections.activity ? 'collapsed' : ''}`}>
        <SectionHeader id="activity" title="Activity" />
        {!collapsedSections.activity && (
          <div className="section-content">
            <div className="list" style={{ maxHeight: "150px", overflowY: "auto" }}>
              {activity.slice(0, 10).map((a) => (
                <div key={a.activity_id} className="list-item">
                  <div className="list-item-content">
                    <div className="list-item-title text-xs">{a.kind}</div>
                    <div className="list-item-subtitle text-xs">
                      {a.ref_type}:{a.ref_id} by {a.actor_id}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Collaboration */}
      <div className={`section ${collapsedSections.collaboration ? 'collapsed' : ''}`}>
        <SectionHeader id="collaboration" title="Collaboration" />
        {!collapsedSections.collaboration && (
          <div className="section-content">
            <div className="list mb-sm">
              {members.map((m) => (
                <div key={m.user_id} className="list-item">
                  <div className="list-item-content">
                    <div className="list-item-title">
                      {m.display_name || m.user_id}
                      <span className="badge badge-default ml-xs">{m.role}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
            <div className="flex gap-xs mb-sm">
              <input
                type="text"
                className="input"
                placeholder="user id"
                value={newMemberId}
                onChange={(e) => onNewMemberIdChange(e.target.value)}
              />
              <select
                className="input"
                value={newMemberRole}
                onChange={(e) => onNewMemberRoleChange(e.target.value)}
                style={{ width: "100px" }}
              >
                <option value="viewer">viewer</option>
                <option value="editor">editor</option>
                <option value="owner">owner</option>
              </select>
            </div>
            <button 
              className="btn btn-secondary btn-sm w-full"
              onClick={onAddMember}
              disabled={!selectedProjectId}
            >
              Add Member
            </button>
          </div>
        )}
      </div>

      {/* Tool Metrics */}
      <div className={`section ${collapsedSections.metrics ? 'collapsed' : ''}`}>
        <SectionHeader id="metrics" title="Tool Metrics" />
        {!collapsedSections.metrics && (
          <div className="section-content">
            <div className="list" style={{ maxHeight: "150px", overflowY: "auto" }}>
              {toolMetrics.map((t) => (
                <div key={`${t.tool_id}-${t.tool_version}`} className="list-item">
                  <div className="list-item-content">
                    <div className="list-item-title text-xs">
                      {t.tool_id}@{t.tool_version}
                    </div>
                    <div className="list-item-subtitle text-xs">
                      calls: {t.calls} | errors: {t.errors} | lat: {t.last_latency_ms ?? "n/a"}ms
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Artifacts */}
      <div className={`section ${collapsedSections.artifacts ? 'collapsed' : ''}`}>
        <SectionHeader id="artifacts" title="Artifacts" />
        {!collapsedSections.artifacts && (
          <div className="section-content">
            <div className="list" style={{ maxHeight: "150px", overflowY: "auto" }}>
              {[] /* artifacts would be passed in if needed */.map((a: any) => (
                <div key={a.artifact_id} className="list-item">
                  <div className="list-item-content">
                    <div className="list-item-title text-xs">
                      {a.title || a.artifact_id.slice(0, 12)}
                    </div>
                    <div className="list-item-subtitle text-xs">
                      {a.size_bytes}b
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Offline Queue */}
      <div className={`section ${collapsedSections.offline ? 'collapsed' : ''}`}>
        <SectionHeader 
          id="offline" 
          title="Offline Queue" 
          badge={pendingActions.length}
          icon={
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
              <polyline points="22 4 12 14.01 9 11.01" />
            </svg>
          }
        />
        {!collapsedSections.offline && (
          <div className="section-content">
            <button 
              className="btn btn-sm btn-secondary w-full mb-sm"
              onClick={onReplayQueue}
              disabled={!isOnline}
            >
              Retry Now
            </button>
            <div className="list" style={{ maxHeight: "100px", overflowY: "auto" }}>
              {pendingActions.slice(0, 5).map((a) => (
                <div key={a.id} className="list-item">
                  <div className="list-item-content">
                    <div className="list-item-title text-xs">
                      [{a.status}] {a.endpoint}
                    </div>
                    {a.last_error && (
                      <div className="list-item-subtitle text-xs text-error">
                        {a.last_error.slice(0, 40)}
                      </div>
                    )}
                  </div>
                  <button 
                    className="btn btn-ghost btn-sm"
                    onClick={() => onDiscardPending(a.id)}
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
            
            {/* Deferred Uploads */}
            <div className="mt-md">
              <div className="text-sm font-medium mb-sm">Deferred Uploads</div>
              <button 
                className="btn btn-sm btn-secondary w-full mb-sm"
                onClick={onReplayUploads}
                disabled={!isOnline}
              >
                Retry Uploads
              </button>
              <div className="list" style={{ maxHeight: "100px", overflowY: "auto" }}>
                {deferredUploads.slice(0, 5).map((u) => (
                  <div key={u.id} className="list-item">
                    <div className="list-item-content">
                      <div className="list-item-title text-xs">
                        {u.file_name} [{u.status}]
                      </div>
                      {uploadProgress[`deferred-${u.id}`] !== undefined && (
                        <div className="list-item-subtitle text-xs">
                          {uploadProgress[`deferred-${u.id}`]}%
                        </div>
                      )}
                    </div>
                    <button 
                      className="btn btn-ghost btn-sm"
                      onClick={() => onDiscardUpload(u.id)}
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
