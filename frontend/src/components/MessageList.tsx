import type { ChatMessage } from "../core/chat/types";

export function MessageList(props: { messages: ChatMessage[] }) {
  return (
    <div class="messages" role="log" aria-live="polite">
      {props.messages.map((m) => (
        <div class={`msg ${m.role}`}>
          <div class="msgInner">
            <div class="msgRole">{m.role}</div>
            <div class="msgBody">{m.content}</div>
            {m.status ? <div class="msgMeta">{m.status}</div> : null}
          </div>
        </div>
      ))}
    </div>
  );
}
