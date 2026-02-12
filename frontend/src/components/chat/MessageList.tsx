import { MessageBubble } from "../MessageBubble";
import type { ChatMessage } from "../../store/chatStore";

export function MessageList(props: {
  messages: ChatMessage[];
  topSpacer?: number;
  bottomSpacer?: number;
}) {
  return (
    <>
      {(props.topSpacer ?? 0) > 0 ? <div style={{ height: props.topSpacer }} aria-hidden="true" /> : null}
      {props.messages.map((message) => (
        <MessageBubble key={message.id} message={message} />
      ))}
      {(props.bottomSpacer ?? 0) > 0 ? <div style={{ height: props.bottomSpacer }} aria-hidden="true" /> : null}
    </>
  );
}
