export function ToolsPanel() {
  return (
    <div class="panelCard">
      <div class="panelHeader">
        <div class="panelTitle">Tools</div>
        <div class="muted panelSub">Feature-flagged shell (no tool execution wiring yet)</div>
      </div>

      <div class="panelSection">
        <label class="checkRow">
          <input type="checkbox" disabled aria-disabled="true" />
          <span>Enable tool calls</span>
        </label>
        <label class="checkRow">
          <input type="checkbox" disabled aria-disabled="true" />
          <span>Show tool I/O in transcript</span>
        </label>
        <label class="checkRow">
          <input type="checkbox" disabled aria-disabled="true" />
          <span>Require confirmation before tool use</span>
        </label>

        <div class="muted" style="font-size:12px;margin-top:10px;">
          Future: toggle affects chat request payload (tools) sent to backend Tool agent.
        </div>
      </div>
    </div>
  );
}
