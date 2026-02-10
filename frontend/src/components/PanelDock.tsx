import { getFlags } from "../core/config/featureFlags";
import { setPrefs, uiPrefsStore } from "../core/prefs/uiPrefsStore";
import { useEffect, useMemo, useState } from "preact/hooks";

import { MemoryPanel } from "./panels/MemoryPanel";
import { KnowledgePanel } from "./panels/KnowledgePanel";
import { VoicePanel } from "./panels/VoicePanel";
import { ToolsPanel } from "./panels/ToolsPanel";

type PanelKey = "memory" | "knowledge" | "voice" | "tools";

function useStore<T>(store: { get: () => T; subscribe: (fn: () => void) => () => void }) {
  const [v, setV] = useState(store.get());
  useEffect(() => store.subscribe(() => setV(store.get())), []);
  return v;
}

function enabledPanels(): Array<{ key: PanelKey; label: string }> {
  const f = getFlags();
  const out: Array<{ key: PanelKey; label: string }> = [];
  if (f.memoryPanel) out.push({ key: "memory", label: "Memory" });
  if (f.knowledgePanel) out.push({ key: "knowledge", label: "Knowledge" });
  if (f.voice) out.push({ key: "voice", label: "Voice" });
  if (f.tools) out.push({ key: "tools", label: "Tools" });
  return out;
}

export function PanelDock(props: { conversationId?: string | null }) {
  const prefs = useStore(uiPrefsStore);
  const panels = useMemo(() => enabledPanels(), []);

  // If no panels enabled, render nothing.
  if (!panels.length) return null;
  if (!prefs.panelDockOpen) return null;

  const active = panels.some((p) => p.key === prefs.activePanel)
    ? prefs.activePanel
    : panels[0]!.key;

  function close() {
    setPrefs({ panelDockOpen: false });
  }

  return (
    <aside class="panelDock" aria-label="Side panels">
      <div class="panelDockTop">
        <div class="panelDockTitle">Panels</div>
        <button class="btn" onClick={close} aria-label="Close panels">Close</button>
      </div>

      <div class="panelTabs" role="tablist" aria-label="Panels">
        {panels.map((p) => {
          const selected = p.key === active;
          return (
            <button
              class={`tab ${selected ? "active" : ""}`}
              role="tab"
              aria-selected={selected}
              onClick={() => setPrefs({ activePanel: p.key })}
            >
              {p.label}
            </button>
          );
        })}
      </div>

      <div class="panelBody" role="tabpanel">
        {active === "memory" ? <MemoryPanel conversationId={props.conversationId ?? null} /> : null}
        {active === "knowledge" ? <KnowledgePanel /> : null}
        {active === "voice" ? <VoicePanel /> : null}
        {active === "tools" ? <ToolsPanel /> : null}
      </div>
    </aside>
  );
}
