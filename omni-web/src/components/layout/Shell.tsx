import { ReactNode } from "react";

interface ShellProps {
  leftSidebar: ReactNode;
  centerPanel: ReactNode;
  sidebarCollapsed?: boolean;
  onExpandSidebar?: () => void;
}

export function Shell({ leftSidebar, centerPanel, sidebarCollapsed, onExpandSidebar }: ShellProps) {
  return (
    <div className={`shell ${sidebarCollapsed ? "shell-sidebar-collapsed" : ""}`}>
      {sidebarCollapsed && (
        <div className="sidebar-expand-bar">
          <button className="sb-icon-btn sidebar-expand-btn" onClick={onExpandSidebar} title="Open sidebar">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
              <line x1="9" y1="3" x2="9" y2="21" />
            </svg>
          </button>
          <button className="sb-icon-btn sidebar-expand-btn" onClick={onExpandSidebar} title="New chat">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
              <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
            </svg>
          </button>
        </div>
      )}
      {!sidebarCollapsed && (
        <aside className="pane pane-left">
          {leftSidebar}
        </aside>
      )}
      <main className="pane pane-center">
        {centerPanel}
      </main>
    </div>
  );
}
