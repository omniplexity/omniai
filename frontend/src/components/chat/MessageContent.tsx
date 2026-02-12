import { useState } from "preact/hooks";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

function CodeBlock(props: { className?: string; children?: any }) {
  const [copied, setCopied] = useState(false);
  const text = String(props.children ?? "").replace(/\n$/, "");
  const language = props.className?.replace("language-", "") ?? "";

  async function onCopy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1200);
    } catch {
      setCopied(false);
    }
  }

  return (
    <div class="mdCodeWrap" data-testid="message-code-block">
      <div class="mdCodeTop">
        <span>{language || "text"}</span>
        <button class="btn mdCopyBtn" onClick={() => void onCopy()} data-testid="copy-code-btn">
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre class="mdPre">
        <code class={props.className}>{text}</code>
      </pre>
    </div>
  );
}

export function MessageContent(props: { content: string }) {
  const codeRenderer = ((codeProps: any) => {
    const { inline, className, children } = codeProps;
    if (inline) return <code>{children}</code>;
    return <CodeBlock className={className} children={children} />;
  }) as any;
  const linkRenderer = ((props: any) => {
    return (
      <a href={props.href} target="_blank" rel="noopener noreferrer">
        {props.children}
      </a>
    );
  }) as any;

  return (
    <div class="markdownBody" data-testid="message-content">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code: codeRenderer,
          a: linkRenderer,
        }}
      >
        {props.content}
      </ReactMarkdown>
    </div>
  );
}
