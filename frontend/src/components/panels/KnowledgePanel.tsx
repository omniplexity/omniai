export function KnowledgePanel() {
  return (
    <div class="panelCard">
      <div class="panelHeader">
        <div class="panelTitle">Knowledge</div>
        <div class="muted panelSub">Feature-flagged shell (no API wiring yet)</div>
      </div>

      <div class="panelSection">
        <div class="muted">
          Planned v1 wiring:
          <ul>
            <li>Browse/search indexed sources</li>
            <li>Attach sources to a chat run</li>
            <li>Show citations per message</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
