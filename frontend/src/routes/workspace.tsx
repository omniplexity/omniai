export function WorkspaceRoute(props: { projectId?: string }) {
  return (
    <div class="page pad" data-testid="workspace-shell">
      <div class="card wide">
        <h1 class="h1">Workspace</h1>
        <p class="muted">Phase 2 scaffold (flag-gated)</p>
      </div>
      <div
        style="display:grid;grid-template-columns:1.2fr 1fr 1fr;gap:12px;margin-top:12px;"
        data-testid="workspace-panes"
      >
        <section class="card" data-testid="workspace-pane-chat">
          <h2 class="h2">Chat</h2>
          <p class="muted">Embedded chat pane stub.</p>
        </section>
        <section class="card" data-testid="workspace-pane-editor">
          <h2 class="h2">Editor</h2>
          <p class="muted">Document editor pane stub.</p>
        </section>
        <section class="card" data-testid="workspace-pane-results">
          <h2 class="h2">Results</h2>
          <p class="muted">Analysis/results pane stub.</p>
        </section>
      </div>
      <div class="muted" style="margin-top:10px;" data-testid="workspace-project-id">
        Project: {props.projectId ?? "none"}
      </div>
    </div>
  );
}

