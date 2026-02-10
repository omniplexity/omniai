import { useEffect, useState } from "preact/hooks";

function getHashPath(): string {
  // Expecting "#/path". If missing, default to "/login".
  const raw = window.location.hash || "";
  const h = raw.startsWith("#") ? raw.slice(1) : raw;
  if (!h || h === "/") return "/login";
  return h.startsWith("/") ? h : `/${h}`;
}

export function navigate(to: string) {
  const path = to.startsWith("/") ? to : `/${to}`;
  window.location.hash = `#${path}`;
}

export function useHashLocation(): [string, (to: string) => void] {
  const [path, setPath] = useState<string>(() => getHashPath());

  useEffect(() => {
    const onChange = () => setPath(getHashPath());
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);

  return [path, navigate];
}

export function Link(props: { to: string; class?: string; children: any }) {
  const href = `#${props.to.startsWith("/") ? props.to : `/${props.to}`}`;
  return (
    <a class={props.class} href={href}>
      {props.children}
    </a>
  );
}
