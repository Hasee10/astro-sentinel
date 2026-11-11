import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { Resvg } from "@resvg/resvg-js";

// This preview is a static visualization of actual public observations, not an
// invented medical graphic. Re-run when publishing a new demo dataset.
const read = (name) =>
  readFileSync(
    new URL(`../public/data/pipeline/${name}`, import.meta.url),
    "utf8",
  );
const rows = (name) =>
  read(name)
    .trim()
    .split(/\r?\n/)
    .filter(Boolean)
    .map((line) => JSON.parse(line));
const observations = rows("crew_observations.jsonl");
const scored = rows("crew_scored.jsonl");
const manifest = JSON.parse(read("simulation_manifest.json"));
const id = [...new Set(observations.map((row) => row.astronaut_id))].sort(
  (a, b) => a.localeCompare(b, undefined, { numeric: true }),
)[0];
const day = 10;
const history = observations.filter(
  (row) => row.astronaut_id === id && row.day <= day,
);
const assessment = scored.find(
  (row) => row.astronaut_id === id && row.as_of_day === day,
);
if (!assessment || history.length !== day)
  throw new Error(
    "Preview requires a complete first-profile history through day 10.",
  );
const escape = (value) =>
  String(value).replace(
    /[<>&"']/g,
    (char) =>
      ({
        "<": "&lt;",
        ">": "&gt;",
        "&": "&amp;",
        '"': "&quot;",
        "'": "&apos;",
      })[char],
  );
const goodValues = history
  .filter(
    (row) =>
      row.scan?.type === "onsd" &&
      row.scan?.quality?.status !== "failed" &&
      Number.isFinite(row.scan?.onsd_mm),
  )
  .map((row) => row.scan.onsd_mm);
if (!goodValues.length)
  throw new Error(
    "The preview requires at least one usable recorded ONSD value.",
  );
const low = Math.floor((Math.min(...goodValues) - 0.3) * 2) / 2;
const high = Math.max(
  low + 1,
  Math.ceil((Math.max(...goodValues) + 0.3) * 2) / 2,
);
let segments = "";
let previous = null;
let dots = "";
for (const row of history) {
  if (
    row.scan?.type !== "onsd" ||
    row.scan?.quality?.status === "failed" ||
    !Number.isFinite(row.scan?.onsd_mm)
  ) {
    previous = null;
    continue;
  }
  const x = 55 + (row.day - 1) * 44;
  const y = 390 - ((row.scan.onsd_mm - low) / (high - low)) * 105;
  if (previous)
    segments += `<path d="M${previous.x.toFixed(2)} ${previous.y.toFixed(2)}L${x.toFixed(2)} ${y.toFixed(2)}"/>`;
  const poor = row.scan.quality?.status !== "ok";
  dots += `<circle cx="${x.toFixed(2)}" cy="${y.toFixed(2)}" r="3.2" fill="${poor ? "#13252d" : "#a1dfcb"}" stroke="${poor ? "#efc581" : "#a1dfcb"}" stroke-width="1.5"/>`;
  previous = { x, y };
}
const card = (x, key, label, subtitle, color) =>
  `<g transform="translate(${x} 98)"><rect width="219" height="136" rx="6" fill="#172832" stroke="#334954"/><path d="M0 18v100" stroke="${color}" stroke-width="2"/><text x="17" y="27" font-size="10" fill="${color}">${label}</text><text x="17" y="58" font-size="24" fill="#e1eae9">${escape(assessment[key].tier[0].toUpperCase() + assessment[key].tier.slice(1))}</text><text x="17" y="81" font-size="9" fill="#a5bdc9">${subtitle}</text><text x="17" y="113" font-size="9" fill="#93aebc">${assessment[key].probability == null ? "—  Probability unavailable" : `${Math.round(assessment[key].probability * 100)}% · Unvalidated simulation`}</text></g>`;
const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="520" height="464" viewBox="0 0 520 464"><rect width="520" height="464" fill="#0c161e"/><g font-family="Arial,sans-serif"><text x="29" y="30" fill="#83a7b4" font-size="7" letter-spacing="1.3">SYNTHETIC PROFILE / ${escape(id)} / DAY ${day}</text><text x="29" y="61" fill="#e2efeb" font-size="24">Onboard perspective.</text><text x="491" y="32" text-anchor="end" fill="#95cbbb" font-size="7">${manifest.crew_size} RESEARCH PROFILES</text>${card(29, "sans", "SANS / OCULAR", "Eye and optic nerve", "#9cdac8")}${card(272, "venous", "VENOUS / JUGULAR", "Neck veins", "#c1b3df")}<text x="29" y="267" fill="#bdcfd7" font-size="10">OPTIC NERVE SHEATH DIAMETER</text><text x="490" y="267" fill="#88a9b9" font-size="8" text-anchor="end">RECORDED VALUES / mm</text>${Array.from(
  { length: Math.round((high - low) * 2) + 1 },
  (_, i) => {
    const value = high - i * 0.5;
    const y = 390 - ((value - low) / (high - low)) * 105;
    return `<path d="M55 ${y}H470" stroke="#2c424e" stroke-dasharray="3 5"/><text x="29" y="${y + 3}" fill="#89a8b8" font-size="8">${value.toFixed(1)}</text>`;
  },
).join(
  "",
)}<g fill="none" stroke="#a1dfcb" stroke-width="1.5">${segments}</g>${dots}<text x="55" y="413" fill="#89a8b8" font-size="8">DAY 01</text><text x="451" y="413" fill="#89a8b8" font-size="8" text-anchor="end">DAY 10</text><path d="M29 434H491" stroke="#2b414c"/><text x="29" y="452" fill="#87a7b4" font-size="7">${escape(manifest.run_id)} · SYNTHETIC DATA · NOT CLINICALLY VALIDATED</text></g></svg>`;
const output = new URL("../public/images/mission-preview.svg", import.meta.url);
writeFileSync(output, svg);
writeFileSync(
  new URL("../public/images/mission-preview.png", import.meta.url),
  new Resvg(svg, {
    fitTo: { mode: "width", value: 1560 },
    font: { defaultFontFamily: "Arial" },
  })
    .render()
    .asPng(),
);
console.log(`Generated data-derived SVG preview: ${fileURLToPath(output)}`);

// Original brand assets: scalable mark, horizontal lockup and raster exports.
for (const name of ["astrosentinel-mark", "astrosentinel-logo"]) {
  const logo = readFileSync(
    new URL(`../public/images/${name}.svg`, import.meta.url),
    "utf8",
  );
  writeFileSync(
    new URL(`../public/images/${name}.png`, import.meta.url),
    new Resvg(logo, {
      fitTo: { mode: "width", value: name.endsWith("mark") ? 512 : 1920 },
      font: { defaultFontFamily: "Arial" },
    })
      .render()
      .asPng(),
  );
}
