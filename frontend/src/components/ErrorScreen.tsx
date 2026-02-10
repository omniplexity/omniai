export function ErrorScreen(props: { title: string; detail: string; onRetry?: () => void }) {
  return (
    <div class="page center">
      <div class="card">
        <h1 class="h1">{props.title}</h1>
        <pre class="pre">{props.detail}</pre>
        {props.onRetry ? (
          <button class="btn primary" onClick={props.onRetry}>Retry</button>
        ) : null}
      </div>
    </div>
  );
}
