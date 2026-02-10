import { useRef, useState } from "preact/hooks";

export function ChatComposer(props: {
  streaming: boolean;
  onSend: (text: string) => void | Promise<void>;
  onStop: () => void;
  onRetry: () => void | Promise<void>;
}) {
  const [text, setText] = useState("");
  const taRef = useRef<HTMLTextAreaElement>(null);

  async function send() {
    const t = text.trim();
    if (!t) return;
    setText("");
    await props.onSend(t);
    taRef.current?.focus();
  }

  return (
    <div class="composer">
      <textarea
        ref={taRef}
        class="textarea"
        rows={2}
        value={text}
        onInput={(e) => setText((e.target as any).value)}
        placeholder="Message OmniAI…"
      />
      <div class="composerRow">
        <button class="btn" disabled={props.streaming} onClick={() => void props.onRetry()}>
          Retry
        </button>
        {props.streaming ? (
          <button class="btn danger" onClick={() => props.onStop()}>
            Stop
          </button>
        ) : (
          <button class="btn primary" disabled={!text.trim()} onClick={() => void send()}>
            Send
          </button>
        )}
      </div>
    </div>
  );
}
