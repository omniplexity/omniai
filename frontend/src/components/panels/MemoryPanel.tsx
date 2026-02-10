export function MemoryPanel(props: { conversationId: string | null }) {
  return (
    <div class="panelCard">
      <div class="panelHeader">
        <div class="panelTitle">Memory</div>
        <div class="muted panelSub">Feature-flagged shell (no API wiring yet)</div>
      </div>

      <div class="panelSection">
        <div class="muted">Conversation:</div>
        <div class="mono">{props.conversationId ?? "(new)"}</div>
      </div>

      <div class="panelSection">
        <div class="muted">
          Planned v1 wiring:
          <ul>
            <li>List saved memories</li>
            <li>Pin/save from messages</li>
            <li>Search/filter</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
