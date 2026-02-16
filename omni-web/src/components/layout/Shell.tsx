import { ReactNode } from "react";

interface ShellProps {
  leftSidebar: ReactNode;
  centerPanel: ReactNode;
  rightSidebar: ReactNode;
}

export function Shell({ leftSidebar, centerPanel, rightSidebar }: ShellProps) {
  return (
    <div className="shell">
      <aside className="pane pane-left">
        {leftSidebar}
      </aside>
      <main className="pane pane-center">
        {centerPanel}
      </main>
      <aside className="pane pane-right">
        {rightSidebar}
      </aside>
    </div>
  );
}
