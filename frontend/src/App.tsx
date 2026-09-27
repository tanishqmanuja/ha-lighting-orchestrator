import { useEffect, useMemo, useState } from "react";
import { Toaster } from "sonner";
import type { HomeAssistant } from "./ha-types";
import {
  discoverAreas,
  parseRoute,
  routeHref,
  sameView,
  type PanelView,
} from "./halo";
import { AreaCard } from "./components/AreaCard";
import { ManagePage } from "./components/ManagePage";
import { Button, EmptyState } from "./components/ui";
import panelCss from "./styles.css?inline";
import sonnerCss from "sonner/dist/styles.css?inline";

export function App({ hass }: { hass: HomeAssistant }) {
  const areas = useMemo(() => discoverAreas(hass.states), [hass]);
  // URL-aware view: refresh restores the manage page, back/forward work.
  const [view, setView] = useState<PanelView>(() =>
    parseRoute(window.location.hash)
  );
  const [busyAll, setBusyAll] = useState(false);

  const navigate = (next: PanelView, replace = false) => {
    setView((cur) => {
      if (sameView(cur, next)) return cur;
      if (replace) window.history.replaceState(null, "", routeHref(next));
      else window.location.hash = routeHref(next);
      return next;
    });
  };

  useEffect(() => {
    const onHash = () => {
      const parsed = parseRoute(window.location.hash);
      setView((cur) => (sameView(cur, parsed) ? cur : parsed));
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  // If the managed area disappears (entry removed), fall back to the list
  // and clean the URL instead of stranding a stale hash.
  const managingKnownArea =
    view.name === "manage" && areas.some((a) => a.key === view.area);

  useEffect(() => {
    if (view.name === "manage" && !managingKnownArea) {
      window.history.replaceState(null, "", "#/");
      setView({ name: "areas" });
    }
  }, [view, managingKnownArea]);

  const resyncAll = async () => {
    setBusyAll(true);
    try {
      await hass.callService("halo", "resync", {});
    } finally {
      setBusyAll(false);
    }
  };

  return (
    <>
      {/* Scoped here (not document.head): HA mounts custom panels inside
          shadow DOM, which document-level styles cannot pierce. */}
      <style>{panelCss}</style>
      <style>{sonnerCss}</style>
      <Toaster position="bottom-right" richColors closeButton />
      <div className="page">
      {view.name === "manage" && managingKnownArea ? (
        <ManagePage
          hass={hass}
          areaKey={view.area}
          initialMood={view.mood}
          onBack={() => navigate({ name: "areas" })}
          onNavigateMood={(mood) =>
            navigate({ name: "manage", area: view.area, mood }, true)
          }
        />
      ) : (
        <>
          <header className="page-head">
            <div className="page-title">
              <img
                className="brand-mark"
                src="/halo_static/halo-mark.png"
                alt="HALO"
              />
              <div>
                <p className="overline">Home Assistant</p>
                <h2>Lighting Orchestrator</h2>
                <p className="subtle">
                  {areas.length === 0
                    ? "No areas yet."
                    : `${areas.length} ${areas.length === 1 ? "area" : "areas"} managed`}
                </p>
              </div>
            </div>
            {areas.length > 0 && (
              <div className="page-actions">
                <a
                  className="btn btn-outline btn-md"
                  href="/config/integrations/integration/halo"
                >
                  Configure
                </a>
                <Button
                  variant="ghost"
                  disabled={busyAll}
                  onClick={() => void resyncAll()}
                >
                  Resync all
                </Button>
              </div>
            )}
          </header>

          {areas.length === 0 ? (
            <EmptyState title="No areas yet">
              Create your first area under Settings → Devices &amp; Services
              → HALO, then map each mood to the scenes and scripts it should
              run.
            </EmptyState>
          ) : (
            <div className="grid">
              {areas.map((area) => {
                const moodState = area.moodEntityId
                  ? hass.states[area.moodEntityId]?.state ?? null
                  : null;
                return (
                  <AreaCard
                    key={area.key}
                    hass={hass}
                    area={area}
                    onManage={(key) =>
                      navigate({ name: "manage", area: key, mood: moodState })
                    }
                  />
                );
              })}
            </div>
          )}
        </>
      )}
      </div>
    </>
  );
}
