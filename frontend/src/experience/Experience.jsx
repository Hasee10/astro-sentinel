import { useEffect, useState } from "react";
import Icon from "../components/Icon.jsx";
import Logo from "../components/Logo.jsx";
import EngineeringPreview from "./EngineeringPreview.jsx";

const HERO = "/images/astronaut-earth.webp";

function Brand({ navigate }) {
  return (
    <button
      className="as-brand"
      type="button"
      onClick={() => navigate("home")}
      aria-label="AstroSentinel homepage"
    >
      <Logo />
      <span>
        ASTROSENTINEL<small>HUMAN PERFORMANCE / DEEP SPACE</small>
      </span>
    </button>
  );
}

function TopNav({ navigate, solid = false }) {
  const [open, setOpen] = useState(false);
  function go(section) {
    setOpen(false);
    if (document.getElementById(section))
      document.getElementById(section).scrollIntoView({ behavior: "smooth" });
    else navigate(`home?section=${section}`);
  }
  return (
    <header className={`as-header${solid ? " as-header--solid" : ""}`}>
      <Brand navigate={navigate} />
      <nav className={open ? "is-open" : ""} aria-label="Main navigation">
        <button type="button" onClick={() => go("mission-story")}>
          The mission
        </button>
        <button type="button" onClick={() => go("how-it-works")}>
          Our approach
        </button>
        <button
          type="button"
          onClick={() => {
            setOpen(false);
            navigate("mission");
          }}
        >
          Experience
        </button>
      </nav>
      <button
        type="button"
        className="as-header-cta"
        onClick={() => navigate("dashboard")}
      >
        Open mission control <Icon name="external" size={16} />
      </button>
      <button
        className="as-menu-button"
        type="button"
        aria-label={open ? "Close navigation" : "Open navigation"}
        aria-expanded={open}
        onClick={() => setOpen(!open)}
      >
        <Icon name={open ? "close" : "menu"} />
      </button>
    </header>
  );
}

function Footer({ navigate }) {
  return (
    <footer className="as-footer">
      <div>
        <Brand navigate={navigate} />
        <p>SHIFU HAWKS · NASA SPACE APPS 2026</p>
      </div>
      <p>
        Synthetic research demonstration.
        <br />
        Monitoring only. Not clinically or flight validated.
      </p>
      <button
        type="button"
        className="as-footer-cta"
        onClick={() => navigate("dashboard")}
      >
        Enter mission control <Icon name="external" size={17} />
      </button>
      <div className="as-footer-bottom">
        <span>BUILT FOR THE HUMAN SIDE OF EXPLORATION</span>
        <button type="button" onClick={() => navigate("research")}>
          Research & limitations <Icon name="arrow" size={13} />
        </button>
      </div>
    </footer>
  );
}

function useRunInfo() {
  const [run, setRun] = useState(null);
  useEffect(() => {
    let cancelled = false;
    fetch("/data/pipeline/simulation_manifest.json")
      .then((response) => (response.ok ? response.json() : null))
      .then((manifest) => {
        if (!cancelled) setRun(manifest);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);
  return run;
}

function Landing({ navigate }) {
  const run = useRunInfo();
  useEffect(() => {
    const section = new URLSearchParams(window.location.hash.split("?")[1]).get(
      "section",
    );
    if (section)
      document.getElementById(section)?.scrollIntoView({ behavior: "smooth" });
  }, []);
  return (
    <div className="as-site" id="top">
      <section className="as-hero" style={{ "--hero-image": `url(${HERO})` }}>
        <TopNav navigate={navigate} />
        <div className="as-hero-content">
          <div className="as-eyebrow">
            <i /> HUMAN PERFORMANCE IN DEEP SPACE
          </div>
          <h1>
            The next frontier
            <br />
            is <em>human.</em>
          </h1>
          <p>
            Far from Earth. Closer to the evidence.
            <br />
            Explore a new perspective on crew health monitoring when every reply
            takes time.
          </p>
          <div className="as-actions">
            <button
              type="button"
              className="as-primary"
              onClick={() => navigate("dashboard")}
            >
              Experience mission control <Icon name="external" size={18} />
            </button>
            <button
              type="button"
              className="as-quiet"
              onClick={() =>
                document
                  .getElementById("mission-story")
                  ?.scrollIntoView({ behavior: "smooth" })
              }
            >
              Discover the mission <Icon name="arrow" size={17} />
            </button>
          </div>
          <span className="as-hero-disclosure">
            SYNTHETIC RESEARCH PROTOTYPE / NASA SPACE APPS 2026
          </span>
        </div>
        <div
          className="as-hero-facts"
          aria-label="Current demonstration dataset"
        >
          <div>
            <small>MISSION WINDOW</small>
            <strong>
              {run ? String(run.mission_duration_days).padStart(3, "0") : "—"}{" "}
              <span>DAYS</span>
            </strong>
          </div>
          <div>
            <small>RESEARCH COHORT</small>
            <strong>
              {run?.crew_size ?? "—"} <span>SYNTHETIC PROFILES</span>
            </strong>
          </div>
          <div>
            <small>INDEPENDENT OUTCOMES</small>
            <strong>
              SANS <span>+</span> VENOUS
            </strong>
          </div>
          <div>
            <small>SIMULATED EARTH LINK</small>
            <strong>
              0–20 <span>MIN / ONE WAY</span>
            </strong>
          </div>
        </div>
      </section>

      <main>
        <section className="as-story as-section" id="mission-story">
          <div className="as-story-copy">
            <span className="as-eyebrow">01 / THE DISTANCE BETWEEN US</span>
            <h2>
              Your crew can’t
              <br />
              wait for a reply.
            </h2>
            <p>
              In deep space, the body changes while Earth waits for a signal.
              AstroSentinel explores how onboard observations, measurement
              quality, and independent assessments can help make those changes
              understandable.
            </p>
            <p className="as-story-secondary">
              The mission here is synthetic. The design challenge is real: keep
              the crew’s latest evidence distinct from the last snapshot
              received on Earth.
            </p>
            <button
              type="button"
              className="as-text-link"
              onClick={() => navigate("ground")}
            >
              Explore the Earth link <Icon name="arrow" size={16} />
            </button>
          </div>
          <div className="as-distance-card">
            <div className="as-card-kicker">
              <span>DEEP SPACE COMMUNICATION</span>
              <span className="as-small-status">
                <i /> SIMULATED
              </span>
            </div>
            <img
              src="/images/mission-link.svg"
              alt="An illustrative communication path between Mars and Earth"
            />
            <div className="as-distance-labels">
              <span>CREW / MARS</span>
              <span>GROUND / EARTH</span>
            </div>
            <div className="as-distance-number">
              12
              <span>
                min
                <br />
                one way
              </span>
            </div>
            <div className="as-distance-detail">
              <span>A moment onboard.</span>
              <span>A later arrival on Earth.</span>
            </div>
            <p>
              Illustrative link setting. In the demo, one real second represents
              one mission minute.
            </p>
          </div>
        </section>

        <section className="as-method as-section" id="how-it-works">
          <div className="as-section-intro">
            <div>
              <span className="as-eyebrow">
                02 / FROM OBSERVATION TO UNDERSTANDING
              </span>
              <h2>Evidence has a sequence.</h2>
            </div>
            <p>
              One continuous timeline.
              <br />
              Two independent monitoring outcomes.
            </p>
          </div>
          <div className="as-method-grid">
            <Method
              number="01"
              icon="eye"
              title="Observe"
              label="THE MEASUREMENT"
              description="Inspect each recorded scan with its acquisition quality. A failed measurement stays unavailable."
            />
            <Method
              number="02"
              icon="pulse"
              title="Understand"
              label="THE ASSESSMENT"
              description="Read SANS and venous tiers separately, with the evidence and limitations behind every assessment."
            />
            <Method
              number="03"
              icon="signal"
              title="Communicate"
              label="THE SHARED PERSPECTIVE"
              description="Send a snapshot to Earth. Follow its journey, then acknowledge it from the ground station."
            />
          </div>
          <div className="as-method-note">
            <Icon name="info" size={17} />
            <span>
              Not enough evidence is a meaningful state. An unavailable
              probability is never presented as zero risk.
            </span>
            <button type="button" onClick={() => navigate("research")}>
              Read the limitations <Icon name="external" size={14} />
            </button>
          </div>
        </section>

        <section className="as-product">
          <div className="as-section as-product-grid">
            <div className="as-product-copy">
              <span className="as-eyebrow">03 / THE MISSION WORKSPACE</span>
              <h2>
                A clearer view.
                <br />
                <em>At every distance.</em>
              </h2>
              <p>
                Move through the mission, inspect a profile, and follow an
                observation from onboard assessment to Earth’s delayed view.
              </p>
              <ul>
                <li>
                  <Icon name="check" size={16} />
                  Search the complete synthetic cohort
                </li>
                <li>
                  <Icon name="check" size={16} />
                  Explore time-ordered measurement history
                </li>
                <li>
                  <Icon name="check" size={16} />
                  Understand the evidence and next action
                </li>
              </ul>
              <button
                type="button"
                className="as-primary"
                onClick={() => navigate("dashboard")}
              >
                Open mission control <Icon name="external" size={18} />
              </button>
            </div>
            <div className="as-product-preview">
              <div className="as-preview-frame">
                <span>
                  <i />
                  <i />
                  <i />
                </span>
                <span>ASTROSENTINEL / MISSION CONTROL</span>
                <Icon name="grid" size={13} />
              </div>
              <EngineeringPreview navigate={navigate} researchCohortSize={run?.crew_size} />
              <div className="as-preview-caption">
                <span>Current engineering acceptance data · E4, day 14</span>
                <button type="button" onClick={() => navigate("engineering-dashboard?profile=E4&day=14")}>
                  Explore the workspace <Icon name="arrow" size={14} />
                </button>
              </div>
            </div>
          </div>
        </section>

        <section className="as-closing as-section">
          <span className="as-eyebrow">
            DESIGNED FOR A MORE DISTANT TOMORROW
          </span>
          <h2>
            Keep the human
            <br />
            in the mission.
          </h2>
          <p>
            Explore the synthetic demonstration. Follow the evidence for
            yourself.
          </p>
          <button
            type="button"
            className="as-primary"
            onClick={() => navigate("mission")}
          >
            Choose your perspective <Icon name="arrow" size={18} />
          </button>
        </section>
      </main>
      <Footer navigate={navigate} />
    </div>
  );
}

function Method({ number, icon, title, label, description }) {
  return (
    <article className="as-method-card">
      <div className="as-method-card-top">
        <span>{number}</span>
        <Icon name={icon} size={26} />
      </div>
      <span className="as-method-label">{label}</span>
      <h3>{title}</h3>
      <p>{description}</p>
      <div className="as-method-line" />
    </article>
  );
}

function MissionEntry({ navigate }) {
  const cards = [
    {
      route: "dashboard",
      icon: "eye",
      number: "01",
      title: "Crew onboard.",
      label: "ONBOARD MONITORING",
      body: "Start with the astronaut. Inspect independent outcomes, measurement quality, and the evidence available today.",
      action: "Enter the workspace",
    },
    {
      route: "ground",
      icon: "signal",
      number: "02",
      title: "Ground, Earth.",
      label: "THE DELAYED PERSPECTIVE",
      body: "Watch a snapshot travel across the simulated link. See what Earth has received, then send an acknowledgement.",
      action: "Open the Earth link",
    },
    {
      route: "timeline",
      icon: "timeline",
      number: "03",
      title: "Mission time.",
      label: "TIME-ORDERED EVIDENCE",
      body: "Follow the observation trace, inspect recorded changes, and explore the mission one day at a time.",
      action: "Explore the timeline",
    },
  ];
  return (
    <div
      className="as-site as-portal"
      style={{ "--hero-image": `url(${HERO})` }}
    >
      <TopNav navigate={navigate} solid />
      <main className="as-portal-main as-section">
        <span className="as-eyebrow">MISSION DECK / SELECT A PERSPECTIVE</span>
        <h1>
          Choose your <em>perspective.</em>
        </h1>
        <p>
          Every perspective shares the same synthetic mission.
          <br />
          Every observation keeps its place in time.
        </p>
        <div className="as-portal-grid">
          {cards.map((card) => (
            <button
              type="button"
              key={card.route}
              className={`as-route-card as-route-${card.route}`}
              onClick={() => navigate(card.route)}
            >
              <div>
                <span>
                  {card.number} / {card.label}
                </span>
                <Icon name={card.icon} size={26} />
              </div>
              <h2>{card.title}</h2>
              <p>{card.body}</p>
              <strong>
                {card.action}
                <Icon name="arrow" size={17} />
              </strong>
            </button>
          ))}
        </div>
        <div className="as-portal-note">
          <Icon name="research" size={18} />
          <p>
            Synthetic research. Monitoring only.
          </p>
          <button type="button" onClick={() => navigate("research")}>
            Research & readiness <Icon name="external" size={14} />
          </button>
        </div>
      </main>
    </div>
  );
}

export default function Experience({ route, navigate }) {
  return route === "mission" ? (
    <MissionEntry navigate={navigate} />
  ) : (
    <Landing navigate={navigate} />
  );
}
