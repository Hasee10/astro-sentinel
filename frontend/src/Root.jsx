import { lazy, Suspense, useEffect, useState } from "react";
import Experience from "./experience/Experience.jsx";
import Logo from "./components/Logo.jsx";
import "./experience/experience.css";
import "./experience/readability.css";

const App = lazy(() => import("./App.jsx"));
const PresentationView = lazy(
  () => import("./presentation/PresentationView.jsx"),
);

const ROUTES = new Set([
  "home",
  "mission",
  "dashboard",
  "ground",
  "timeline",
  "research",
  "debug",
  "engineering-dashboard",
  "engineering-timeline",
  "engineering-ground",
  "engineering-research",
]);
function routeFromHash() {
  const route =
    window.location.hash.slice(1).split("?")[0].replace(/^\//, "") || "home";
  return ROUTES.has(route) ? route : "home";
}

export default function Root() {
  return (
    <Suspense
      fallback={
        <div className="as-route-loading" role="status">
          <Logo />
          <p>Opening mission workspace…</p>
        </div>
      }
    >
      <Router />
    </Suspense>
  );
}

function Router() {
  const [route, setRoute] = useState(routeFromHash);
  useEffect(() => {
    const update = () => {
      setRoute(routeFromHash());
      window.scrollTo(0, 0);
    };
    window.addEventListener("hashchange", update);
    return () => window.removeEventListener("hashchange", update);
  }, []);
  const navigate = (to) => {
    window.location.hash = to === "home" ? "" : to;
  };
  if (route === "debug")
    return (
      <>
        <button
          type="button"
          className="mode-switch"
          onClick={() => navigate("dashboard")}
        >
          Return to mission dashboard
        </button>
        <App />
      </>
    );
  // Keep the operational component mounted across views: day, profile and sent
  // snapshots belong to this session, not to any one tab.
  if (["dashboard", "ground", "timeline", "research"].includes(route.replace("engineering-", "")))
    return (
      <PresentationView
        key={route.startsWith("engineering-") ? "fixture" : "pipeline"}
        engineeringFixture={route.startsWith("engineering-")}
        view={route.replace("engineering-", "")}
        navigate={(to) => navigate(route.startsWith("engineering-") && ["dashboard", "ground", "timeline", "research"].includes(to) ? `engineering-${to}` : to)}
        onOpenDebug={() => navigate("debug")}
      />
    );
  return <Experience route={route} navigate={navigate} />;
}
