export function VoicePanel() {
  return (
    <div class="panelCard">
      <div class="panelHeader">
        <div class="panelTitle">Voice</div>
        <div class="muted panelSub">Feature-flagged shell (no mic/TTS wiring yet)</div>
      </div>

      <div class="panelSection">
        <div class="row">
          <button class="btn" disabled aria-disabled="true">Record</button>
          <button class="btn" disabled aria-disabled="true">Stop</button>
          <button class="btn" disabled aria-disabled="true">Play TTS</button>
        </div>
        <div class="muted" style="font-size:12px;margin-top:10px;">
          Future: record → upload to backend Voice agent → transcript in chat composer; optional TTS playback.
        </div>
      </div>
    </div>
  );
}
