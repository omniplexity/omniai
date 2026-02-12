import { render } from "preact";
import { App } from "./app";
import { bootstrapApp } from "./core/boot/bootstrap";
import "./styles/tokens.css";
import "./styles/base.css";

async function bootstrap() {
  const root = document.getElementById("app");
  if (!root) throw new Error("Missing #app");

  root.textContent = "Loading…";

  const boot = await bootstrapApp();
  render(<App runtimeConfig={boot.runtimeConfig} initialBootError={boot.bootError} />, root);
}

bootstrap().catch((err) => {
  const root = document.getElementById("app");
  if (!root) return;
  root.innerHTML = `
    <div style="padding:16px;font-family:ui-sans-serif,system-ui;color:#e7eaf0;">
      <h1 style="margin:0 0 8px 0;font-size:18px;">OmniAI failed to start</h1>
      <pre style="white-space:pre-wrap;border:1px solid rgba(255,255,255,.12);border-radius:10px;padding:12px;background:#101522;">
${String((err as any)?.message ?? err)}
      </pre>
      <button style="padding:10px 12px;border-radius:10px;border:1px solid rgba(255,255,255,.12);background:#6aa6ff;color:#07101f;font-weight:700;cursor:pointer"
              onclick="location.reload()">Retry</button>
    </div>
  `;
});
