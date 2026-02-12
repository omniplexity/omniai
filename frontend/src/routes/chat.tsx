import { MainLayout } from "../layouts/MainLayout";

export function ChatRoute(props: { threadId?: string }) {
  return (
    <div data-testid="chat-shell">
      <MainLayout threadId={props.threadId} />
    </div>
  );
}
