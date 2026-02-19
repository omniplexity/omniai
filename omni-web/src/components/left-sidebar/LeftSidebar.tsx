import { useState, useRef, useEffect } from "react";
import { Project, Thread, Run } from "../../types";

interface LeftSidebarProps {
  projects: Project[];
  threads: Thread[];
  uncategorizedThreads?: Thread[];
  runs: Run[];
  selectedProjectId: string;
  selectedThreadId: string;
  selectedRunId: string;
  projectUnread: Record<string, number>;
  onSelectProject: (id: string) => void;
  onSelectThread: (id: string) => void;
  onSelectRun: (id: string) => void;
  onCreateProject: () => void;
  onCreateThread: () => void;
  onCreateRun: () => void;
  onNewChat: () => void;
  onSearchChats: () => void;
  onImages: () => void;
  onPlugins: () => void;
  onDeepResearch: () => void;
  onMcpBrowser: () => void;
  onOpenNotifications: () => void;
  onOpenTimeline: () => void;
  onOpenTools: () => void;
  onOpenMemory: () => void;
  onOpenMarketplace: () => void;
  onOpenComments: () => void;
  onOpenActivity: () => void;
  onOpenCollaboration: () => void;
  onOpenMetrics: () => void;
  onOpenArtifacts: () => void;
  onOpenOfflineQueue: () => void;
  onRenameThread: (threadId: string, newTitle: string) => void;
  onMoveThread: (threadId: string, projectId: string) => void;
  onRemoveFromProject: (threadId: string) => void;
  onArchiveThread: (threadId: string) => void;
  onDeleteThread: (threadId: string) => Promise<void>;
  onRenameProject: (projectId: string, newName: string) => void;
  onDeleteProject: (projectId: string) => Promise<void>;
  deletingThreadIds?: Record<string, boolean>;
  deletingProjectIds?: Record<string, boolean>;
  deleteError?: string;
  isAdmin: boolean;
  onLogout: () => void;
  onUpdateUser: (data: { display_name?: string; avatar_url?: string }) => void;
  me: { display_name: string; user_id: string; avatar_url?: string; username?: string } | null;
  isOnline: boolean;
  onCollapseSidebar?: () => void;
}

type ContextMenuState = {
  threadId?: string;
  projectId?: string;
  x: number;
  y: number;
} | null;

// Stable project colors
const PROJECT_COLORS = ["#58a6ff", "#3fb950", "#d29922", "#f778ba", "#bc8cff", "#f85149"];

export function LeftSidebar({
  projects,
  threads,
  uncategorizedThreads: uncategorizedThreadsProp,
  runs,
  selectedProjectId,
  selectedThreadId,
  selectedRunId,
  projectUnread,
  onSelectProject,
  onSelectThread,
  onSelectRun,
  onCreateProject,
  onCreateThread,
  onCreateRun,
  onNewChat,
  onSearchChats,
  onImages,
  onPlugins,
  onDeepResearch,
  onMcpBrowser,
  onOpenNotifications,
  onOpenTimeline,
  onOpenTools,
  onOpenMemory,
  onOpenMarketplace,
  onOpenComments,
  onOpenActivity,
  onOpenCollaboration,
  onOpenMetrics,
  onOpenArtifacts,
  onOpenOfflineQueue,
  onRenameThread,
  onMoveThread,
  onRemoveFromProject,
  onArchiveThread,
  onDeleteThread,
  onRenameProject,
  onDeleteProject,
  deletingThreadIds = {},
  deletingProjectIds = {},
  deleteError = "",
  isAdmin,
  onLogout,
  onUpdateUser,
  me,
  isOnline,
  onCollapseSidebar,
}: LeftSidebarProps) {
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [userProfileOpen, setUserProfileOpen] = useState(false);
  const [editDisplayName, setEditDisplayName] = useState("");
  const [editAvatarUrl, setEditAvatarUrl] = useState("");
  const [expandedProjects, setExpandedProjects] = useState<Record<string, boolean>>({});
  const [projectsExpanded, setProjectsExpanded] = useState(true);
  const [yourChatsExpanded, setYourChatsExpanded] = useState(true);
  const [contextMenu, setContextMenu] = useState<ContextMenuState>(null);
  const [renamingThreadId, setRenamingThreadId] = useState<string | null>(null);
  const [renamingProjectId, setRenamingProjectId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [moveMenuOpen, setMoveMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const contextMenuRef = useRef<HTMLDivElement>(null);
  const renameInputRef = useRef<HTMLInputElement>(null);
  const projectRenameInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (me) {
      setEditDisplayName(me.display_name);
      setEditAvatarUrl(me.avatar_url || "");
    }
  }, [me]);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setUserMenuOpen(false);
        setUserProfileOpen(false);
      }
      if (contextMenuRef.current && !contextMenuRef.current.contains(event.target as Node)) {
        setContextMenu(null);
        setMoveMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  useEffect(() => {
    if (renamingThreadId && renameInputRef.current) {
      renameInputRef.current.focus();
      renameInputRef.current.select();
    }
  }, [renamingThreadId]);

  useEffect(() => {
    if (renamingProjectId && projectRenameInputRef.current) {
      projectRenameInputRef.current.focus();
      projectRenameInputRef.current.select();
    }
  }, [renamingProjectId]);

  const toggleProject = (projectId: string) => {
    setExpandedProjects(prev => ({ ...prev, [projectId]: !prev[projectId] }));
  };

  const getProjectThreads = (projectId: string) => threads.filter(t => t.project_id === projectId);
  // Use passed uncategorizedThreads prop, or compute from threads if not provided
  const uncategorizedThreads = uncategorizedThreadsProp || threads.filter(t => !t.project_id);

  const handleSaveProfile = () => {
    onUpdateUser({ display_name: editDisplayName, avatar_url: editAvatarUrl || undefined });
    setUserProfileOpen(false);
    setUserMenuOpen(false);
  };

  const openThreadContextMenu = (e: React.MouseEvent, threadId: string) => {
    e.preventDefault();
    e.stopPropagation();
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
    const sidebarRect = (e.currentTarget as HTMLElement).closest(".left-sidebar")?.getBoundingClientRect();
    setContextMenu({
      threadId,
      x: rect.right - (sidebarRect?.left || 0),
      y: rect.top - (sidebarRect?.top || 0),
    });
    setMoveMenuOpen(false);
  };

  const openProjectContextMenu = (e: React.MouseEvent, projectId: string) => {
    e.preventDefault();
    e.stopPropagation();
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
    const sidebarRect = (e.currentTarget as HTMLElement).closest(".left-sidebar")?.getBoundingClientRect();
    setContextMenu({
      projectId,
      x: rect.right - (sidebarRect?.left || 0),
      y: rect.top - (sidebarRect?.top || 0),
    });
    setMoveMenuOpen(false);
  };

  const closeContextMenu = () => { setContextMenu(null); setMoveMenuOpen(false); };

  const handleRenameStart = () => {
    if (!contextMenu?.threadId) return;
    const thread = threads.find(t => t.id === contextMenu.threadId);
    setRenamingThreadId(contextMenu.threadId);
    setRenameValue(thread?.title || "");
    closeContextMenu();
  };

  const handleProjectRenameStart = () => {
    if (!contextMenu?.projectId) return;
    const project = projects.find(p => p.id === contextMenu.projectId);
    setRenamingProjectId(contextMenu.projectId);
    setRenameValue(project?.name || "");
    closeContextMenu();
  };

  const handleRenameSubmit = () => {
    if (renamingThreadId && renameValue.trim()) onRenameThread(renamingThreadId, renameValue.trim());
    setRenamingThreadId(null);
    setRenameValue("");
  };

  const handleProjectRenameSubmit = () => {
    if (renamingProjectId && renameValue.trim()) onRenameProject(renamingProjectId, renameValue.trim());
    setRenamingProjectId(null);
    setRenameValue("");
  };

  const handleRenameKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleRenameSubmit();
    else if (e.key === "Escape") { setRenamingThreadId(null); setRenameValue(""); }
  };

  const handleProjectRenameKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleProjectRenameSubmit();
    else if (e.key === "Escape") { setRenamingProjectId(null); setRenameValue(""); }
  };

  const getThreadProject = (threadId: string) => {
    const thread = threads.find(t => t.id === threadId);
    return thread?.project_id || null;
  };
  const deletingContextThread = contextMenu?.threadId ? Boolean(deletingThreadIds[contextMenu.threadId]) : false;
  const deletingContextProject = contextMenu?.projectId ? Boolean(deletingProjectIds[contextMenu.projectId]) : false;

  const renderThreadItem = (t: Thread) => {
    const isRenaming = renamingThreadId === t.id;
    return (
      <div key={t.id} className={`sb-thread ${t.id === selectedThreadId ? "sb-thread-active" : ""}`}>
        <button className="sb-thread-btn" onClick={() => onSelectThread(t.id)}>
          {isRenaming ? (
            <input
              ref={renameInputRef}
              className="thread-rename-input"
              value={renameValue}
              onChange={(e) => setRenameValue(e.target.value)}
              onBlur={handleRenameSubmit}
              onKeyDown={handleRenameKeyDown}
              onClick={(e) => e.stopPropagation()}
            />
          ) : (
            <span className="sb-thread-title">{t.title}</span>
          )}
        </button>
        {!isRenaming && (
          <button className="sb-thread-dots" onClick={(e) => openThreadContextMenu(e, t.id)} title="More options">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="5" r="1.5" />
              <circle cx="12" cy="12" r="1.5" />
              <circle cx="12" cy="19" r="1.5" />
            </svg>
          </button>
        )}
      </div>
    );
  };

  return (
    <div className="left-sidebar">
      {/* Top bar — Logo + actions */}
      <div className="sb-topbar">
        <div className="sb-logo">
          <img src="/favicon.svg" alt="OmniAI" className="sb-logo-img" />
        </div>
        <div className="sb-topbar-actions">
          <button className="sb-icon-btn" onClick={onNewChat} title="New chat">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
              <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
            </svg>
          </button>
          {onCollapseSidebar && (
            <button className="sb-icon-btn" onClick={onCollapseSidebar} title="Close sidebar">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                <line x1="9" y1="3" x2="9" y2="21" />
              </svg>
            </button>
          )}
        </div>
      </div>

      {/* Navigation items */}
      <nav className="sb-nav">
        <button className="sb-nav-item" onClick={onNewChat}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 5v14M5 12h14" />
          </svg>
          <span>New chat</span>
        </button>
        <button className="sb-nav-item" onClick={onSearchChats}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <span>Search chats</span>
        </button>
        <button className="sb-nav-item" onClick={onImages}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
            <circle cx="8.5" cy="8.5" r="1.5" />
            <polyline points="21 15 16 10 5 21" />
          </svg>
          <span>Images</span>
        </button>
        <button className="sb-nav-item" onClick={onPlugins}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="1" /><circle cx="19" cy="12" r="1" /><circle cx="5" cy="12" r="1" />
            <circle cx="12" cy="5" r="1" /><circle cx="12" cy="19" r="1" />
          </svg>
          <span>Apps</span>
        </button>
        <button className="sb-nav-item" onClick={onDeepResearch}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 2L2 7l10 5 10-5-10-5z" /><path d="M2 17l10 5 10-5" /><path d="M2 12l10 5 10-5" />
          </svg>
          <span>Deep research</span>
        </button>
        <button className="sb-nav-item" onClick={onMcpBrowser}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="16 18 22 12 16 6" /><polyline points="8 6 2 12 8 18" />
          </svg>
          <span>MCP Browser</span>
        </button>
        <button className="sb-nav-item" onClick={onOpenNotifications}><span>Notifications</span></button>
        <button className="sb-nav-item" onClick={onOpenTimeline}><span>Timeline</span></button>
        <button className="sb-nav-item" onClick={onOpenTools}><span>Tools</span></button>
        <button className="sb-nav-item" onClick={onOpenMemory}><span>Memory</span></button>
        <button className="sb-nav-item" onClick={onOpenMarketplace}><span>Marketplace</span></button>
        <button className="sb-nav-item" onClick={onOpenComments}><span>Comments</span></button>
        <button className="sb-nav-item" onClick={onOpenActivity}><span>Activity</span></button>
        <button className="sb-nav-item" onClick={onOpenCollaboration}><span>Collaboration</span></button>
        <button className="sb-nav-item" onClick={onOpenMetrics}><span>Tool Metrics</span></button>
        <button className="sb-nav-item" onClick={onOpenArtifacts}><span>Artifacts</span></button>
        <button className="sb-nav-item" onClick={onOpenOfflineQueue}><span>Offline Queue</span></button>
      </nav>
      {deleteError ? (
        <div role="alert" className="mt-sm" style={{ color: "#f85149", padding: "0 12px" }}>
          {deleteError}
        </div>
      ) : null}

      {/* Projects section */}
      <div className="sb-section">
        <button className="sb-section-header" onClick={() => setProjectsExpanded(!projectsExpanded)}>
          <span className="sb-section-label">Projects</span>
          <svg className={`sb-section-chevron ${projectsExpanded ? "open" : ""}`} width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M6 9l6 6 6-6" />
          </svg>
        </button>

        {projectsExpanded && (
          <div className="sb-section-body">
            {/* New project */}
            <button className="sb-nav-item sb-nav-item-subtle" onClick={onCreateProject}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
              </svg>
              <span>New project</span>
            </button>

            {/* Project list */}
            {projects.map((p, i) => {
              const color = PROJECT_COLORS[i % PROJECT_COLORS.length];
              const isExpanded = expandedProjects[p.id];
              const projThreads = getProjectThreads(p.id);
              const isRenamingProject = renamingProjectId === p.id;

              return (
                <div key={p.id} className="sb-project">
                  <div className={`sb-project-row ${p.id === selectedProjectId ? "sb-project-active" : ""}`}>
                    <button
                      className="sb-project-item"
                      onClick={() => { onSelectProject(p.id); toggleProject(p.id); }}
                    >
                      <span className="sb-project-icon" style={{ color }}>{"{ }"}</span>
                      {isRenamingProject ? (
                        <input
                          ref={projectRenameInputRef}
                          className="thread-rename-input"
                          value={renameValue}
                          onChange={(e) => setRenameValue(e.target.value)}
                          onBlur={handleProjectRenameSubmit}
                          onKeyDown={handleProjectRenameKeyDown}
                          onClick={(e) => e.stopPropagation()}
                        />
                      ) : (
                        <span className="sb-project-name">{p.name}</span>
                      )}
                      {projectUnread[p.id] ? <span className="sb-badge">{projectUnread[p.id]}</span> : null}
                    </button>
                    {!isRenamingProject && (
                      <button className="sb-project-dots" onClick={(e) => openProjectContextMenu(e, p.id)} title="More options">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <circle cx="12" cy="5" r="1.5" />
                          <circle cx="12" cy="12" r="1.5" />
                          <circle cx="12" cy="19" r="1.5" />
                        </svg>
                      </button>
                    )}
                  </div>

                  {isExpanded && projThreads.length > 0 && (
                    <div className="sb-project-threads">
                      <span className="sb-recent-label">Recent</span>
                      {projThreads.map(t => renderThreadItem(t))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Your Chats section - uncategorized threads */}
      <div className="sb-section">
        <button className="sb-section-header" onClick={() => setYourChatsExpanded(!yourChatsExpanded)}>
          <span className="sb-section-label">Your Chats</span>
          <svg className={`sb-section-chevron ${yourChatsExpanded ? "open" : ""}`} width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M6 9l6 6 6-6" />
          </svg>
        </button>
        {yourChatsExpanded && uncategorizedThreads.length > 0 && (
          <div className="sb-chats">
            {uncategorizedThreads.map(t => renderThreadItem(t))}
          </div>
        )}
      </div>

      {/* Thread Context Menu */}
      {contextMenu?.threadId && (
        <div
          ref={contextMenuRef}
          className="thread-context-menu"
          style={{ top: contextMenu.y, left: Math.min(contextMenu.x, 200) }}
        >
          <button className="context-menu-item" onClick={handleRenameStart}>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
              <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
            </svg>
            <span>Rename</span>
          </button>

          <div
            className="context-menu-submenu-trigger"
            onMouseEnter={() => setMoveMenuOpen(true)}
            onMouseLeave={() => setMoveMenuOpen(false)}
          >
            <button className="context-menu-item" onClick={() => setMoveMenuOpen(!moveMenuOpen)}>
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
              </svg>
              <span>Move to project</span>
              <svg className="context-menu-arrow" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M9 18l6-6-6-6" />
              </svg>
            </button>
            {moveMenuOpen && (
              <div className="context-flyout">
                <button className="context-menu-item" onClick={() => { onCreateProject(); closeContextMenu(); }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
                  </svg>
                  <span>New project</span>
                </button>
                <div className="context-menu-separator" />
                {projects.map((p, i) => {
                  const color = PROJECT_COLORS[i % PROJECT_COLORS.length];
                  const isCurrent = getThreadProject(contextMenu.threadId!) === p.id;
                  return (
                    <button
                      key={p.id}
                      className={`context-menu-item ${isCurrent ? "disabled" : ""}`}
                      onClick={() => { if (!isCurrent) { onMoveThread(contextMenu.threadId!, p.id); closeContextMenu(); } }}
                    >
                      <span className="project-color-icon" style={{ color }}>{"{ }"}</span>
                      <span>{p.name}</span>
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          <button className="context-menu-item" onClick={() => { onRemoveFromProject(contextMenu.threadId!); closeContextMenu(); }}>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
            <span>Remove from OmniAI</span>
          </button>

          <button className="context-menu-item" onClick={() => { onArchiveThread(contextMenu.threadId!); closeContextMenu(); }}>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="21 8 21 21 3 21 3 8" />
              <rect x="1" y="3" width="22" height="5" />
              <line x1="10" y1="12" x2="14" y2="12" />
            </svg>
            <span>Archive</span>
          </button>

          <button
            className="context-menu-item context-menu-item-danger"
            disabled={deletingContextThread}
            onClick={async () => {
              if (deletingContextThread) return;
              try {
                await onDeleteThread(contextMenu.threadId!);
              } finally {
                closeContextMenu();
              }
            }}
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="3 6 5 6 21 6" />
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
            </svg>
            <span>{deletingContextThread ? "Deleting..." : "Delete"}</span>
          </button>
        </div>
      )}

      {/* Project Context Menu */}
      {contextMenu?.projectId && (
        <div
          ref={contextMenuRef}
          className="thread-context-menu"
          style={{ top: contextMenu.y, left: Math.min(contextMenu.x, 200) }}
        >
          <button className="context-menu-item" onClick={handleProjectRenameStart}>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
              <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
            </svg>
            <span>Rename</span>
          </button>
          <button
            className="context-menu-item context-menu-item-danger"
            disabled={deletingContextProject}
            onClick={async () => {
              if (deletingContextProject) return;
              try {
                await onDeleteProject(contextMenu.projectId!);
              } finally {
                closeContextMenu();
              }
            }}
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="3 6 5 6 21 6" />
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
            </svg>
            <span>{deletingContextProject ? "Deleting..." : "Delete"}</span>
          </button>
        </div>
      )}

      {/* User section at bottom */}
      {me && (
        <div className="sb-user" ref={menuRef}>
          <button className="sb-user-trigger" onClick={() => setUserMenuOpen(!userMenuOpen)}>
            <div className="sb-user-avatar">
              {me.avatar_url ? (
                <img src={me.avatar_url} alt={me.display_name} />
              ) : (
                me.display_name.charAt(0).toUpperCase()
              )}
            </div>
            <div className="sb-user-info">
              <span className="sb-user-name">{me.display_name}</span>
              {isAdmin && <span className="sb-user-plan">Admin</span>}
              {!isAdmin && <span className="sb-user-plan">Free</span>}
            </div>
          </button>

          {userMenuOpen && (
            <div className="user-menu-dropdown user-menu-dropdown-up">
              <button className="menu-item menu-item-user" onClick={() => setUserProfileOpen(!userProfileOpen)}>
                <div className="avatar avatar-sm">
                  {editAvatarUrl ? <img src={editAvatarUrl} alt={editDisplayName} /> : editDisplayName.charAt(0).toUpperCase()}
                </div>
                <div className="user-info">
                  <span className="user-display-name-bold">{editDisplayName}</span>
                  <span className="user-username">@{me.username || me.user_id}</span>
                </div>
                <svg className={`chevron ${userProfileOpen ? "open" : ""}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M9 18l6-6-6-6" />
                </svg>
              </button>

              {userProfileOpen && (
                <div className="user-profile-form">
                  <div className="form-group">
                    <label className="input-label">Display Name</label>
                    <input type="text" className="input" value={editDisplayName} onChange={(e) => setEditDisplayName(e.target.value)} placeholder="Display name" />
                  </div>
                  <div className="form-group">
                    <label className="input-label">Avatar URL</label>
                    <input type="text" className="input" value={editAvatarUrl} onChange={(e) => setEditAvatarUrl(e.target.value)} placeholder="https://..." />
                  </div>
                  <button className="btn btn-primary btn-sm w-full" onClick={handleSaveProfile}>Save Changes</button>
                </div>
              )}

              <div className="menu-divider"></div>
              <button className="menu-item" onClick={() => setUserMenuOpen(false)}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" /></svg>
                Settings
              </button>
              <button className="menu-item" onClick={() => setUserMenuOpen(false)}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9z" /></svg>
                Personalization
              </button>
              <div className="menu-divider"></div>
              <button className="menu-item menu-item-danger" onClick={() => { setUserMenuOpen(false); onLogout(); }}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><polyline points="16 17 21 12 16 7" /><line x1="21" y1="12" x2="9" y2="12" /></svg>
                Logout
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
