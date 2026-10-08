import { useEffect } from "react";
import { useLocation } from "react-router-dom";

// Remember scroll position per pathname so navigating "back" returns to the
// same place (e.g. Overview -> finding detail -> back to Overview).
const positions = new Map<string, number>();

export default function ScrollRestoration() {
  const location = useLocation();
  const path = location.pathname;

  // Continuously record the scroll position for the current path.
  useEffect(() => {
    const onScroll = () => positions.set(path, window.scrollY);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, [path]);

  // Restore (after content has had a moment to mount) when the path changes.
  useEffect(() => {
    const saved = positions.get(path);
    const t = setTimeout(() => window.scrollTo(0, saved ?? 0), 80);
    return () => clearTimeout(t);
  }, [path]);

  return null;
}
