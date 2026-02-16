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
  isAdmin: boolean;
  onLogout: () => void;
  me: { display_name: string; user_id: string } | null;
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
  isAdmin,
  onLogout,
  me,
  isOnline,
}: LeftSidebarProps) {
  return (
    <div className="left-sidebar">
      {/* Header */}
      <div className="header">
        <div className="header-title">
          <div className="logo">O</div>
          <span>OmniAI</span>
        </div>
        <div className="header-actions">
          <div className="status-indicator">
            <span className={`status-dot ${isOnline ? "" : "offline"}`}></span>
            <span>{isOnline ? "Online" : "Offline"}</span>
          </div>
        </div>
      </div>

      {/* User Section */}
      {me && (
        <div className="section">
          <div className="user-badge">
            <div className="avatar">{me.display_name.charAt(0).toUpperCase()}</div>
            <span>{me.display_name}</span>
            {isAdmin && <span className="badge badge-primary">Admin</span>}
          </div>
          <button className="btn btn-ghost btn-sm w-full" onClick={onLogout}>
            Sign Out
          </button>
        </div>
      )}

      {/* Projects */}
      <div className="section">
        <div className="section-header">
          <span className="section-title">Projects</span>
          <button className="btn btn-sm btn-ghost" onClick={onCreateProject}>+</button>
        </div>
        <div className="section-content">
          <div className="nav-tree">
            {projects.map((p) => (
              <button
                key={p.id}
                className={`nav-item ${p.id === selectedProjectId ? "active" : ""}`}
                onClick={() => onSelectProject(p.id)}
              >
                <svg className="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M3 3h18v18H3zM3 9h18M9 21V9" />
                </svg>
                <span>{p.name}</span>
                {projectUnread[p.id] ? <span className="badge">{projectUnread[p.id]}</span> : null}
              </button>
            ))}
            {projects.length === 0 && (
              <div className="empty-state">
                <p className="text-secondary text-sm">No projects yet</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Threads */}
      {selectedProjectId && (
        <div className="section">
          <div className="section-header">
            <span className="section-title">Threads</span>
            <button className="btn btn-sm btn-ghost" onClick={onCreateThread}>+</button>
          </div>
          <div className="section-content">
            <div className="nav-tree">
              {threads.map((t) => (
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
              {threads.length === 0 && (
                <div className="empty-state">
                  <p className="text-secondary text-sm">No threads yet</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Runs */}
      {selectedThreadId && (
        <div className="section">
          <div className="section-header">
            <span className="section-title">Runs</span>
            <button className="btn btn-sm btn-ghost" onClick={onCreateRun}>+</button>
          </div>
          <div className="section-content">
            <div className="nav-tree">
              {runs.map((r) => (
                <button
                  key={r.id}
                  className={`nav-item ${r.id === selectedRunId ? "active" : ""}`}
                  onClick={() => onSelectRun(r.id)}
                >
                  <svg className="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <polygon points="5 3 19 12 5 21 5 3" />
                  </svg>
                  <span>{r.id.slice(0, 8)}</span>
                  <span className={`badge badge-${r.status === "active" ? "success" : "default"}`}>
                    {r.status}
                  </span>
                </button>
              ))}
              {runs.length === 0 && (
                <div className="empty-state">
                  <p className="text-secondary text-sm">No runs yet</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
