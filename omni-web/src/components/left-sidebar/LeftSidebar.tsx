import { useState, useRef, useEffect } from "react";
import { Project, Thread, Run } from "../../types";

interface LeftSidebarProps {
  projects: Project[];
  threads: Thread[];
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
  isAdmin: boolean;
  onLogout: () => void;
  onUpdateUser: (data: { display_name?: string; avatar_url?: string }) => void;
  me: { display_name: string; user_id: string; avatar_url?: string; username?: string } | null;
  isOnline: boolean;
}

export function LeftSidebar({
  projects,
  threads,
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
  isAdmin,
  onLogout,
  onUpdateUser,
  me,
  isOnline,
}: LeftSidebarProps) {
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [userProfileOpen, setUserProfileOpen] = useState(false);
  const [editDisplayName, setEditDisplayName] = useState("");
  const [editAvatarUrl, setEditAvatarUrl] = useState("");
  const [expandedProjects, setExpandedProjects] = useState<Record<string, boolean>>({});
  const menuRef = useRef<HTMLDivElement>(null);

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
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const toggleProject = (projectId: string) => {
    setExpandedProjects(prev => ({
      ...prev,
      [projectId]: !prev[projectId]
    }));
  };

  const getProjectThreads = (projectId: string) => {
    return threads.filter(t => t.project_id === projectId);
  };

  const uncategorizedThreads = threads.filter(t => !t.project_id);

  const handleSaveProfile = () => {
    onUpdateUser({
      display_name: editDisplayName,
      avatar_url: editAvatarUrl || undefined
    });
    setUserProfileOpen(false);
    setUserMenuOpen(false);
  };

  const navItems = [
    { id: "new-chat", label: "New Chat", icon: "+", onClick: onNewChat },
    { id: "search-chats", label: "Search Chats", icon: "⌘K", onClick: onSearchChats },
    { id: "images", label: "Images", icon: "🖼", onClick: onImages },
    { id: "plugins", label: "Plugins", icon: "🔌", onClick: onPlugins },
    { id: "deep-research", label: "Deep Research", icon: "🔬", onClick: onDeepResearch },
    { id: "mcp-browser", label: "MCP Browser", icon: "⚡", onClick: onMcpBrowser },
  ];

  return (
    <div className="left-sidebar">
      <div className="header">
        <div className="header-title">
          <div className="logo-container">
            <img src="/favicon.svg" alt="OmniAI" className="logo-img" />
          </div>
          <span>OmniAI</span>
        </div>
        <div className="header-actions">
          <div className="status-indicator">
            <span className={`status-dot ${isOnline ? "" : "offline"}`}></span>
            <span>{isOnline ? "Online" : "Offline"}</span>
          </div>
        </div>
      </div>

      <div className="nav-stubs">
        {navItems.map((item) => (
          <button
            key={item.id}
            className="nav-stub-btn"
            onClick={item.onClick}
          >
            <span className="nav-stub-icon">{item.icon}</span>
            <span className="nav-stub-label">{item.label}</span>
          </button>
        ))}
      </div>

      <div className="section section-projects">
        <div className="section-header">
          <span className="section-title">Projects</span>
          <button className="btn btn-sm btn-ghost" onClick={onCreateProject}>+</button>
        </div>
        <div className="section-content">
          <div className="nav-tree">
            {projects.map((p) => (
              <div key={p.id} className="project-folder">
                <button
                  className={`nav-item project-folder-header ${p.id === selectedProjectId ? "active" : ""}`}
                  onClick={() => toggleProject(p.id)}
                >
                  <svg className={`chevron ${expandedProjects[p.id] ? "expanded" : ""}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M9 18l6-6-6-6" />
                  </svg>
                  <svg className="folder-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M3 3h18v18H3zM3 9h18M9 21V9" />
                  </svg>
                  <span>{p.name}</span>
                  {projectUnread[p.id] ? <span className="badge">{projectUnread[p.id]}</span> : null}
                </button>
                {expandedProjects[p.id] && (
                  <div className="project-threads">
                    {getProjectThreads(p.id).map((t) => (
                      <button
                        key={t.id}
                        className={`nav-item nav-item-nested ${t.id === selectedThreadId ? "active" : ""}`}
                        onClick={() => onSelectThread(t.id)}
                      >
                        <svg className="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                        </svg>
                        <span>{t.title}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="section section-chats">
        <div className="section-header">
          <span className="section-title">Your Chats</span>
          <button className="btn btn-sm btn-ghost" onClick={onCreateThread}>+</button>
        </div>
        <div className="section-content">
          <div className="nav-tree">
            {uncategorizedThreads.map((t) => (
              <button
                key={t.id}
                className={`nav-item ${t.id === selectedThreadId ? "active" : ""}`}
                onClick={() => onSelectThread(t.id)}
              >
                <svg className="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                </svg>
                <span>{t.title}</span>
              </button>
            ))}
          </div>
        </div>
      </div>

      {me && (
        <div className="section section-user-menu" ref={menuRef}>
          <button 
            className="user-menu-trigger"
            onClick={() => setUserMenuOpen(!userMenuOpen)}
          >
            <div className="avatar avatar-lg">
              {me.avatar_url ? (
                <img src={me.avatar_url} alt={me.display_name} />
              ) : (
                me.display_name.charAt(0).toUpperCase()
              )}
            </div>
            <div className="user-info">
              <span className="user-display-name">{me.display_name}</span>
              <span className="user-username">@{me.username || me.user_id}</span>
            </div>
            {isAdmin && <span className="badge badge-primary">Admin</span>}
            <svg className={`chevron ${userMenuOpen ? "open" : ""}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M6 9l6 6 6-6" />
            </svg>
          </button>
          
          {userMenuOpen && (
            <div className="user-menu-dropdown user-menu-dropdown-up">
              <button 
                className="menu-item menu-item-user"
                onClick={() => setUserProfileOpen(!userProfileOpen)}
              >
                <div className="avatar avatar-sm">
                  {editAvatarUrl ? (
                    <img src={editAvatarUrl} alt={editDisplayName} />
                  ) : (
                    editDisplayName.charAt(0).toUpperCase()
                  )}
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
                    <input
                      type="text"
                      className="input"
                      value={editDisplayName}
                      onChange={(e) => setEditDisplayName(e.target.value)}
                      placeholder="Display name"
                    />
                  </div>
                  <div className="form-group">
                    <label className="input-label">Avatar URL</label>
                    <input
                      type="text"
                      className="input"
                      value={editAvatarUrl}
                      onChange={(e) => setEditAvatarUrl(e.target.value)}
                      placeholder="https://..."
                    />
                  </div>
                  <button 
                    className="btn btn-primary btn-sm w-full"
                    onClick={handleSaveProfile}
                  >
                    Save Changes
                  </button>
                </div>
              )}

              <div className="menu-divider"></div>

              <button className="menu-item" onClick={() => { setUserMenuOpen(false); }}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="3" />
                  <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
                </svg>
                Settings
              </button>
              <button className="menu-item" onClick={() => { setUserMenuOpen(false); }}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9z" />
                </svg>
                Personalization
              </button>
              <button className="menu-item" onClick={() => { setUserMenuOpen(false); }}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="10" />
                  <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
                  <line x1="12" y1="17" x2="12.01" y2="17" />
                </svg>
                Help
              </button>
              <button className="menu-item" onClick={() => { setUserMenuOpen(false); }}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                  <line x1="3" y1="9" x2="21" y2="9" />
                  <line x1="9" y1="21" x2="9" y2="9" />
                </svg>
                Plan
              </button>
              <div className="menu-divider"></div>
              <button className="menu-item menu-item-danger" onClick={() => { setUserMenuOpen(false); onLogout(); }}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                  <polyline points="16 17 21 12 16 7" />
                  <line x1="21" y1="12" x2="9" y2="12" />
                </svg>
                Logout
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
