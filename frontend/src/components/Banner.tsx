export function Banner(props: { kind: "error" | "info"; text: string }) {
  return <div class={`banner ${props.kind}`} role={props.kind === "error" ? "alert" : "status"}>{props.text}</div>;
}
