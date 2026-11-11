import { useState } from "react";
import Icon from "../components/Icon.jsx";
import { OUTCOMES, TIERS, TIER_TEXT } from "./constants.js";
import { recordThrough } from "./missionModel.js";
import { Pager } from "./WorkspaceUI.jsx";
import { usePageSize } from "./usePageSize.js";

export default function CohortBrowser({
  indexed,
  day,
  astronautId,
  onSelect,
  onOpenResearch,
}) {
  const [query, setQuery] = useState("");
  const [outcome, setOutcome] = useState("sans");
  const [tier, setTier] = useState("all");
  const [page, setPage] = useState(0);
  const [open, setOpen] = useState(false);
  const { ref, size } = usePageSize(57);
  const ids = indexed.ids.filter(
    (id) =>
      id.toLowerCase().includes(query.toLowerCase().trim()) &&
      (tier === "all" ||
        recordThrough(indexed.crew.get(id), day)?.[outcome]?.tier === tier),
  );
  const count = Math.max(1, Math.ceil(ids.length / size));
  const current = Math.min(page, count - 1);
  return (
    <aside className="pv-sidebar" aria-label="Synthetic cohort browser">
      <div className="pv-cohort-heading">
        <h2>Research cohort</h2>
        <span className="pv-count">{indexed.ids.length}</span>
      </div>
      <p className="pv-sidebar-note">Synthetic astronaut profiles</p>
      <button
        type="button"
        className="pv-mobile-browser"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
      >
        <Icon name="people" size={18} />
        Astronaut {astronautId ?? "—"}
        <span>
          {open ? "Close" : "Choose profile"}
          <Icon name={open ? "close" : "chevron"} size={17} />
        </span>
      </button>
      <div className={`pv-browser${open ? " is-open" : ""}`}>
        <label className="pv-search">
          <Icon name="search" size={18} />
          <input
            type="search"
            aria-label="Search astronaut profiles"
            placeholder="Find a profile…"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setPage(0);
            }}
          />
        </label>
        <div className="pv-filters">
          <select
            aria-label="Filter outcome"
            value={outcome}
            onChange={(event) => {
              setOutcome(event.target.value);
              setPage(0);
            }}
          >
            <option value="sans">SANS</option>
            <option value="venous">Venous</option>
          </select>
          <select
            aria-label="Filter status"
            value={tier}
            onChange={(event) => {
              setTier(event.target.value);
              setPage(0);
            }}
          >
            <option value="all">All statuses</option>
            {TIERS.map((key) => (
              <option key={key} value={key}>
                {TIER_TEXT[key].label}
              </option>
            ))}
          </select>
        </div>
        <div className="pv-list-header">
          <span>{ids.length} profiles</span>
          <span>S / V</span>
        </div>
        <div className="pv-crew-list" ref={ref}>
          {ids.length ? (
            ids.slice(current * size, (current + 1) * size).map((id) => {
              const result = recordThrough(indexed.crew.get(id), day);
              return (
                <button
                  type="button"
                  key={id}
                  className={`pv-profile${id === astronautId ? " is-selected" : ""}`}
                  aria-pressed={id === astronautId}
                  aria-label={`Select astronaut ${id}`}
                  onClick={() => {
                    onSelect(id);
                    setOpen(false);
                  }}
                >
                  <span className="pv-avatar">
                    <Icon name="people" size={18} />
                  </span>
                  <span className="pv-profile-name">
                    {id}
                    <small>Synthetic profile</small>
                  </span>
                  <span className="pv-profile-status">
                    {OUTCOMES.map(({ key, name }) => (
                      <span
                        key={key}
                        className={`pv-status-dot pv-tier-${result?.[key]?.tier ?? "unresolved"}`}
                        title={`${name}: ${result?.[key]?.tier ?? "No record"}`}
                      >
                        <span className="sr-only">
                          {name}: {result?.[key]?.tier ?? "No record"}
                        </span>
                      </span>
                    ))}
                  </span>
                </button>
              );
            })
          ) : (
            <div className="pv-no-results">
              <p>No matching profiles.</p>
              <button
                type="button"
                className="pv-text-button"
                onClick={() => {
                  setQuery("");
                  setTier("all");
                  setPage(0);
                }}
              >
                Clear filters
              </button>
            </div>
          )}
        </div>
        <Pager
          page={current}
          count={count}
          onChange={setPage}
          label="Cohort pages"
        />
      </div>
      <div className="pv-sidebar-bottom">
        <span>
          <Icon name="research" size={18} />
          Synthetic research
        </span>
        <button type="button" onClick={onOpenResearch}>
          Research details
          <Icon name="external" size={14} />
        </button>
      </div>
    </aside>
  );
}
