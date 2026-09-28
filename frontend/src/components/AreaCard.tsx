import { useState } from "react";
import type { HomeAssistant } from "../ha-types";
import {
  actionFor,
  areaDisplayName,
  asDefaults,
  asMapping,
  asMismatchDetails,
  asStatus,
  asStringArray,
  driftLines,
  isDefaultPreset,
  moodEntityId,
  presetEntityId,
  resyncButtonId,
  sensorEntityId,
  type HaloArea,
} from "../halo";
import { OptionButtons } from "./OptionButtons";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  CardTitle,
} from "./ui";

interface AreaCardProps {
  hass: HomeAssistant;
  area: HaloArea;
  onManage: (areaKey: string) => void;
}

/**
 * One HALO area: requested mood/preset pickers (the single source of input)
 * plus read-only truth (active mood/preset, status, mapped actions, drift).
 */
export function AreaCard({ hass, area, onManage }: AreaCardProps) {
  // Which option we last sent but HA hasn't confirmed yet (quick-change
  // feedback: the button shows "…" until the select entity flips).
  const [pendingMood, setPendingMood] = useState<string | null>(null);
  const [pendingPreset, setPendingPreset] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const mood = area.moodEntityId ? hass.states[area.moodEntityId] : undefined;
  const preset = area.presetEntityId
    ? hass.states[area.presetEntityId]
    : undefined;
  const status = hass.states[sensorEntityId(area.key, "status")];
  const activeMood = hass.states[sensorEntityId(area.key, "active_mood")];
  const activePreset = hass.states[sensorEntityId(area.key, "active_preset")];

  const statusValue = asStatus(status?.state);
  const moods = asStringArray(mood?.attributes.options);
  const presets = asStringArray(preset?.attributes.options);
  const reqMood = mood?.state ?? null;
  const reqPreset = preset?.state ?? null;
  const mismatched = asStringArray(status?.attributes.mismatched_entities);
  const drift = driftLines(mismatched, asMismatchDetails(status?.attributes.mismatch_details));
  const mapping = asMapping(status?.attributes.mapping);
  const defaults = asDefaults(status?.attributes.default_presets);

  const call = async (
    domain: string,
    service: string,
    data: Record<string, unknown>,
    done: () => void
  ) => {
    setBusy(true);
    try {
      await hass.callService(domain, service, data);
    } finally {
      done();
      setBusy(false);
    }
  };

  const pickMood = (option: string) => {
    if (!area.moodEntityId || option === reqMood) return;
    setPendingMood(option);
    void call(
      "select",
      "select_option",
      { entity_id: moodEntityId(area.key), option },
      () => setPendingMood(null)
    );
  };

  const pickPreset = (option: string) => {
    if (!area.presetEntityId || option === reqPreset) return;
    setPendingPreset(option);
    void call(
      "select",
      "select_option",
      { entity_id: presetEntityId(area.key), option },
      () => setPendingPreset(null)
    );
  };

  const resync = () => {
    void call("halo", "resync", { area: area.key }, () => undefined);
  };

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>{areaDisplayName(hass.states, area.key)}</CardTitle>
          <p className="card-subtitle">{area.key}</p>
        </div>
        <Badge
          tone={
            statusValue === "active"
              ? "ok"
              : statusValue === "transitioning"
                ? "warn"
                : "neutral"
          }
          dot
        >
          {statusValue}
        </Badge>
      </CardHeader>

      <dl className="facts">
        <div>
          <dt>Requested</dt>
          <dd>
            {reqMood ?? "—"} / {reqPreset ?? "—"}
          </dd>
        </div>
        <div>
          <dt>Active</dt>
          <dd>
            {activeMood?.state ?? "?"} / {activePreset?.state ?? "?"}
          </dd>
        </div>
      </dl>

      <p className="label">Mood</p>
      <OptionButtons
        options={moods}
        current={reqMood}
        pending={pendingMood}
        disabled={busy}
        onPick={pickMood}
      />

      <p className="label">Preset</p>
      <div className="presets-col">
        {presets.length === 0 && (
          <span className="muted">
            No presets configured yet — add them under Manage.
          </span>
        )}
        {presets.map((option) => {
          const isCurrent = option === reqPreset;
          const isPending = option === pendingPreset;
          const action = actionFor(mapping, reqMood, option);
          const isDefault = isDefaultPreset(defaults, reqMood, option, presets);
          const apply = () => pickPreset(option);
          const onRowKey = (e: React.KeyboardEvent) => {
            if (busy) return;
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              apply();
            }
          };
          return (
            <div
              key={option}
              role="button"
              tabIndex={busy ? -1 : 0}
              aria-disabled={busy}
              className={[
                "btn",
                "btn-outline",
                "btn-md",
                "preset",
                "preset-main",
                isCurrent ? "on" : "",
                isPending && !isCurrent ? "pending" : "",
              ]
                .filter(Boolean)
                .join(" ")}
              title={action ? `Runs ${action}` : "No action mapped"}
              onClick={() => {
                if (!busy) apply();
              }}
              onKeyDown={onRowKey}
            >
              <span className="preset-text">
                <span className="preset-name">
                  {option}
                  {isDefault && <span className="preset-default"> · default</span>}
                  {isPending && !isCurrent ? " …" : ""}
                </span>
                <span className="action">{action ?? "Not mapped"}</span>
              </span>
              {!isCurrent && (
                <Button
                  variant="outline"
                  size="sm"
                  className="preset-apply"
                  disabled={busy}
                  onClick={(e) => {
                    e.stopPropagation();
                    apply();
                  }}
                >
                  Apply
                </Button>
              )}
            </div>
          );
        })}
      </div>

      <div className="row foot">
        <Button
          variant="outline"
          size="sm"
          disabled={busy}
          data-testid={resyncButtonId(area.key)}
          onClick={resync}
        >
          Resync
        </Button>
        <Button variant="outline" size="sm" onClick={() => onManage(area.key)}>
          Manage
        </Button>
      </div>

      {statusValue === "custom" && drift.length > 0 && (
        <div className="drift">
          <span className="drift-title">Manual changes detected</span>
          <span className="drift-list">{drift.join(" · ")}</span>
        </div>
      )}
    </Card>
  );
}
