import { useEffect, useState } from "react";

// True when the viewport is narrower than `breakpoint` (default 768px).
// Used to switch between the desktop sidebar layout and the mobile top-bar
// layout. Inline-styles app has no CSS framework, so we branch in JS.
export function useIsMobile(breakpoint = 768): boolean {
  const query = `(max-width: ${breakpoint - 1}px)`;
  const [isMobile, setIsMobile] = useState<boolean>(
    () => typeof window !== "undefined" && window.matchMedia(query).matches
  );

  useEffect(() => {
    const mq = window.matchMedia(query);
    const handler = (e: MediaQueryListEvent) => setIsMobile(e.matches);
    setIsMobile(mq.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, [query]);

  return isMobile;
}