import { MainLayout } from "../layouts/MainLayout";

export function ChatRoute(props: { threadId?: string }) {
  return <MainLayout threadId={props.threadId} />;
}
