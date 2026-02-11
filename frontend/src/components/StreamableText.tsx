import { useEffect, useMemo, useRef, useState } from "preact/hooks";

type Props = {
  text: string;
  animate?: boolean;
};

export function StreamableText({ text, animate = true }: Props) {
  const [visibleLen, setVisibleLen] = useState(text.length);
  const rafRef = useRef<number | null>(null);
  const targetLen = text.length;

  useEffect(() => {
    if (!animate) {
      setVisibleLen(targetLen);
      return;
    }

    setVisibleLen((current) => Math.min(current, targetLen));

    const step = () => {
      let shouldContinue = false;
      setVisibleLen((current) => {
        if (current >= targetLen) return current;
        const remaining = targetLen - current;
        const increment = remaining > 120 ? 10 : remaining > 40 ? 6 : 3;
        const next = Math.min(targetLen, current + increment);
        shouldContinue = next < targetLen;
        return next;
      });
      if (shouldContinue) {
        rafRef.current = requestAnimationFrame(step);
      } else {
        rafRef.current = null;
      }
    };

    if (visibleLen < targetLen) {
      rafRef.current = requestAnimationFrame(step);
    }

    return () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    };
  }, [targetLen, animate, visibleLen]);

  useEffect(() => {
    setVisibleLen((current) => Math.min(current, targetLen));
  }, [targetLen]);

  const display = useMemo(() => text.slice(0, visibleLen), [text, visibleLen]);

  return <span>{display}</span>;
}
