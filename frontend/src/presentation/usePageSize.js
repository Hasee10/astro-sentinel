import { useEffect, useRef, useState } from "react";

// Page density follows the space actually available, not browser zoom or a
// guessed viewport. Containers keep a fixed size while rows are paginated.
export function usePageSize(rowHeight, reserved = 0, maximum = 10) {
  const ref = useRef(null);
  const [size, setSize] = useState(1);
  useEffect(() => {
    const element = ref.current;
    if (!element) return undefined;
    const observer = new ResizeObserver(([entry]) =>
      setSize(
        Math.max(
          1,
          Math.min(
            maximum,
            Math.floor((entry.contentRect.height - reserved) / rowHeight),
          ),
        ),
      ),
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, [rowHeight, reserved, maximum]);
  return { ref, size };
}
