import { ModelSettingsForm } from "./ModelSettingsForm";

export function SettingsDrawer(props: { open: boolean; onClose: () => void }) {
  if (!props.open) return null;

  return (
    <div class="drawerOverlay" role="dialog" aria-modal="true" aria-label="Settings">
      <div class="drawer">
        <div class="drawerTop">
          <div class="drawerTitle">Quick settings</div>
          <button class="btn" onClick={props.onClose}>Close</button>
        </div>
        <div class="drawerBody">
          <ModelSettingsForm compact />
        </div>
      </div>
      <div class="drawerBackdrop" onClick={props.onClose} />
    </div>
  );
}
