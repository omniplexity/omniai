import { StreamableText } from "./StreamableText";
import type { ChatMessage } from "../store/chatStore";

type Props = {
  message: ChatMessage;
};

export function MessageBubble({ message }: Props) {
  const isUser = message.role === "user";
  const isError = !isUser && message.content.trim().startsWith("⚠️");

  const wrapStyle = {
    display: "flex",
    justifyContent: isUser ? "flex-end" : "flex-start",
  } as const;

  const bubbleStyle = {
    maxWidth: "min(780px, 92%)",
    padding: "10px 12px",
    borderRadius: 14,
    border: isError
      ? "1px solid rgba(255,80,80,0.35)"
      : "1px solid rgba(255,255,255,0.10)",
    background: isUser
      ? "rgba(80,140,255,0.16)"
      : isError
        ? "rgba(255,80,80,0.12)"
        : "rgba(255,255,255,0.06)",
    color: isError ? "#ffd6d6" : "#e9eef5",
    lineHeight: 1.35,
    whiteSpace: "pre-wrap",
    overflowWrap: "anywhere",
  } as const;

  const metaStyle = {
    fontSize: 11,
    opacity: 0.65,
    marginTop: 6,
    textAlign: isUser ? ("right" as const) : ("left" as const),
  };

  return (
    <div style={wrapStyle}>
      <div>
        <div style={bubbleStyle}>
          <StreamableText text={message.content} />
        </div>
        <div style={metaStyle}>
          {new Date(message.timestamp).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </div>
      </div>
    </div>
  );
}
