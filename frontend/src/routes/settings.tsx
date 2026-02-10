import { ModelSettingsForm } from "../components/ModelSettingsForm";

export function SettingsRoute() {
  return (
    <div class="page pad">
      <div class="card wide">
        <h1 class="h1">Settings</h1>
        <p class="muted">Provider/model selection and chat defaults (stored locally).</p>
        <ModelSettingsForm />
      </div>
    </div>
  );
}
