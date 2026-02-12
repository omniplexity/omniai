import { useEffect, useState } from "preact/hooks";
import { listProjects } from "../core/workspace/projectsApi";
import { pushToast } from "../ui/toastStore";

export function WorkspaceRoute(props: { projectId?: string }) {
  const [projects, setProjects] = useState<any[] | null>(null);
  const [disabled, setDisabled] = useState(false);

  useEffect(() => {
    void (async () => {
      try {
        const data = await listProjects();
        setProjects(data);
      } catch (error: any) {
        if (error?.backendCode === "E_CAPABILITY_DISABLED") {
          setDisabled(true);
          return;
        }
        pushToast({
          message: error?.message ?? "Failed to load projects.",
          backendCode: error?.backendCode ?? null,
          requestId: error?.requestId ?? null,
        });
      }
    })();
  }, []);

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
      {disabled ? (
        <div class="card" style="margin-top:12px;" data-testid="workspace-disabled-state">
          Workspace capability is disabled by backend policy.
        </div>
      ) : null}
      {Array.isArray(projects) && projects.length === 0 ? (
        <div class="card" style="margin-top:12px;" data-testid="workspace-empty-state">
          No projects yet.
        </div>
      ) : null}
    </div>
  );
}
