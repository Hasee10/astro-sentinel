import { useEffect, useRef, useState } from "react";
import Icon from "../components/Icon.jsx";
import { detailPages } from "./missionModel.js";

export function Tabs({ items, value, onChange, label }) {
  return (
    <div className="pv-tabs" role="tablist" aria-label={label}>
      {items.map(([id, name]) => (
        <button
          type="button"
          role="tab"
          key={id}
          id={`tab-${label.replaceAll(" ", "-")}-${id}`}
          aria-selected={id === value}
          tabIndex={id === value ? 0 : -1}
          onClick={() => onChange(id)}
          onKeyDown={(event) => {
            if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key))
              return;
            event.preventDefault();
            const index = items.findIndex(([key]) => key === id);
            const next =
              event.key === "Home"
                ? 0
                : event.key === "End"
                  ? items.length - 1
                  : (index +
                      (event.key === "ArrowRight" ? 1 : -1) +
                      items.length) %
                    items.length;
            onChange(items[next][0]);
            event.currentTarget.parentElement.children[next].focus();
          }}
        >
          {name}
        </button>
      ))}
    </div>
  );
}

export function Pager({ page, count, onChange, label = "Pages" }) {
  return (
    <nav className="pv-pager" aria-label={label}>
      <button
        type="button"
        className="pv-icon-button"
        aria-label={`Previous ${label.toLowerCase()}`}
        disabled={page <= 0}
        onClick={() => onChange(page - 1)}
      >
        <Icon name="chevron" className="pv-reverse" size={17} />
      </button>
      <span>
        {page + 1} / {Math.max(1, count)}
      </span>
      <button
        type="button"
        className="pv-icon-button"
        aria-label={`Next ${label.toLowerCase()}`}
        disabled={page >= count - 1}
        onClick={() => onChange(page + 1)}
      >
        <Icon name="chevron" size={17} />
      </button>
    </nav>
  );
}

export function Dialog({ title, onClose, children, className = "" }) {
  const ref = useRef(null);
  useEffect(() => {
    const dialog = ref.current;
    dialog.showModal();
    return () => dialog.close();
  }, []);
  return (
    <dialog
      className={`pv-dialog ${className}`}
      ref={ref}
      aria-label={title}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
    >
      <header>
        <h2>{title}</h2>
        <button
          type="button"
          className="pv-icon-button"
          aria-label="Close dialog"
          onClick={onClose}
        >
          <Icon name="close" size={20} />
        </button>
      </header>
      {children}
    </dialog>
  );
}

// Long source explanations are paged rather than clipped or put in a tiny
// scrolling modal. Every original word remains available.
export function DetailDialog({ title, entries, onClose }) {
  const pages = detailPages(entries);
  const [page, setPage] = useState(0);
  const current = pages[Math.min(page, pages.length - 1)];
  return (
    <Dialog title={title} onClose={onClose}>
      <div className="pv-dialog-body">
        <span className="pv-eyebrow">{current?.label}</span>
        <p>{current?.text}</p>
      </div>
      <Pager
        page={page}
        count={pages.length}
        onChange={setPage}
        label="Evidence pages"
      />
    </Dialog>
  );
}
