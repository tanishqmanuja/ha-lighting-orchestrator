import { useEffect, useState } from "react";
import type { HomeAssistant } from "../ha-types";
import {
  blankMood,
  fetchAreaConfig,
  wsError,
  type AreaConfig,
} from "../config";
import { Alert, Button, EmptyState, Skeleton } from "./ui";
import { MoodEditor } from "./MoodEditor";

interface ManagePageProps {
  hass: HomeAssistant;
  areaKey: string;
  initialMood: string | null;
  onBack: () => void;
  onNavigateMood: (mood: string | null) => void;
}

/**
 * Full-page mapping management for one area: mood sidebar on the left,
 * editor form on the right. Saving writes entry options (auto-reload).
 */
export function ManagePage({
  hass,
  areaKey,
  initialMood,
  onBack,
  onNavigateMood,
}: ManagePageProps) {
  const [cfg, setCfg] = useState<AreaConfig | null>(null);
  const [selected, setSelected] = useState<string | null>(initialMood);
  const [isNew, setIsNew] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = async () => {
    const loaded = await fetchAreaConfig(hass, areaKey);
    setCfg(loaded);
    return loaded;
  };

  useEffect(() => {
    let live = true;
    void (async () => {
      try {
        const loaded = await refresh();
        if (!live) return;
        if (!selected || !loaded.moods[selected]) {
          const first = Object.keys(loaded.moods)[0] ?? null;
          setSelected(first);
          setIsNew(first == null);
        }
      } catch (err) {
        if (live) setError(wsError(err));
      }
    })();
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const moods = cfg ? Object.keys(cfg.moods).sort() : [];

  const startNew = () => {
    setSelected(null);
    setIsNew(true);
    setError(null);
    onNavigateMood(null);
  };

  const handleSaved = async (mood: string) => {
    const loaded = await refresh();
    setSelected(loaded.moods[mood] ? mood : null);
    setIsNew(false);
    onNavigateMood(mood);
  };

  const handleDeleted = async () => {
    const loaded = await refresh();
    const first = Object.keys(loaded.moods)[0] ?? null;
    setSelected(first);
    setIsNew(first == null);
    onNavigateMood(first);
  };

  const active = selected && cfg?.moods[selected] ? cfg.moods[selected] : null;

  return (
    <div>
      <div className="topbar">
        <Button variant="outline" size="sm" onClick={onBack}>
          ← All areas
        </Button>
        <h2>Manage · {cfg?.area_name || areaKey}</h2>
      </div>

      {error && <Alert tone="error">{error}</Alert>}

      {!cfg ? (
        <Skeleton lines={4} />
      ) : moods.length === 0 && !isNew ? (
        <EmptyState title="No moods yet">
          Create your first mood to map scenes and scripts to it.
          <div className="row" style={{ justifyContent: "center", marginTop: 12 }}>
            <Button variant="default" onClick={startNew}>
              New mood
            </Button>
          </div>
        </EmptyState>
      ) : (
        <div className="manage-layout">
          <nav className="seg" aria-label="Moods">
            {moods.map((name) => {
              const count = Object.keys(cfg.moods[name].presets).length;
              return (
                <button
                  key={name}
                  type="button"
                  className={["seg-item", name === selected && !isNew ? "active" : ""]
                    .filter(Boolean)
                    .join(" ")}
                  onClick={() => {
                    setSelected(name);
                    setIsNew(false);
                    setError(null);
                    onNavigateMood(name);
                  }}
                >
                  <span>{name}</span>
                  <span className="count">
                    {count} {count === 1 ? "preset" : "presets"}
                  </span>
                </button>
              );
            })}
            <button type="button" className="seg-item seg-add" onClick={startNew}>
              New mood
            </button>
          </nav>

          <div className="card">
            {isNew || !active ? (
              <MoodEditor
                key="__new"
                hass={hass}
                areaKey={areaKey}
                mood={selected ?? ""}
                isNew
                initial={blankMood()}
                onSaved={(m) => void handleSaved(m)}
                onDeleted={() => void handleDeleted()}
              />
            ) : (
              <MoodEditor
                key={selected}
                hass={hass}
                areaKey={areaKey}
                mood={selected!}
                isNew={false}
                initial={active}
                onSaved={(m) => void handleSaved(m)}
                onDeleted={() => void handleDeleted()}
              />
            )}
          </div>
        </div>
      )}

      <footer className="explainer">
        <p>
          <strong>How verification works.</strong> When a mood is requested,
          HALO runs its scene or script, waits out the transition and settle
          time, then compares the lights to the expected state. Changes made
          outside HALO afterwards show as Custom; Resync re-applies the
          requested mood.
        </p>
        <ul>
          <li>
            <strong>Transition (s)</strong> — fade time handed to the scene
            or script.
          </li>
          <li>
            <strong>Settle (s)</strong> — grace period after applying; the
            status shows Transitioning and nothing is judged yet.
          </li>
          <li>
            <strong>Debounce (s)</strong> — quiet wait after a light changes
            before re-checking, so one change is not counted twice.
          </li>
          <li>
            <strong>Tolerance (±)</strong> — how close counts as matching,
            in brightness points and degrees.
          </li>
        </ul>
      </footer>
    </div>
  );
}
