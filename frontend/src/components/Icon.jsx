const paths = {
  grid: "M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z",
  signal:
    "M3 12a9 9 0 0 1 18 0 M6 12a6 6 0 0 1 12 0 M9 12a3 3 0 0 1 6 0 M12 16v5",
  timeline: "M4 4v16h16 M8 15l4-5 4 2 4-7",
  research: "M9 3h6 M10 3v6L4 19a1 1 0 0 0 1 2h14a1 1 0 0 0 1-2L14 9V3 M8 14h8",
  arrow: "M5 12h14 M13 6l6 6-6 6",
  external: "M7 17L17 7 M7 7h10v10",
  search: "M21 21l-5-5 M18 10a7 7 0 1 1-14 0 7 7 0 0 1 14 0",
  eye: "M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12 M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0",
  pulse: "M2 12h5l3-8 4 16 3-8h5",
  play: "M8 5l11 7-11 7z",
  pause: "M8 5v14 M16 5v14",
  chevron: "M9 5l7 7-7 7",
  check: "M5 12l4 4L19 6",
  clock: "M12 8v5l3 2 M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0",
  info: "M12 11v6 M12 7h.01 M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0",
  close: "M6 6l12 12 M6 18L18 6",
  menu: "M4 6h16 M4 12h16 M4 18h16",
  send: "M22 2L9 15 M22 2l-7 20-6-7-7-6z",
  reset: "M3 10a9 9 0 1 1 1 8 M3 4v6h6",
  people:
    "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2 M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8 M17 4a4 4 0 0 1 0 7 M22 21v-2a4 4 0 0 0-3-3.87",
};

export default function Icon({ name, size = 20, ...props }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    >
      <path d={paths[name] || paths.grid} />
    </svg>
  );
}
