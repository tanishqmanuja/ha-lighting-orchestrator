// Pure HALO helpers: entity naming, area discovery, status metadata.
// Framework-free so they stay unit-testable (see halo.test.ts).

import type { HassEntity } from "./ha-types";

export type HaloStatus = "active" | "transitioning" | "custom";

export interface HaloArea {
  /** Area key, e.g. "living_room" (may itself contain underscores). */
  key: string;
  moodEntityId: string | null;
  presetEntityId: string | null;
}

const SELECT_RE = /^select\.halo_(.+)_(mood|preset)$/;

export function discoverAreas(
  states: Record<string, HassEntity>
): HaloArea[] {
  const byKey = new Map<string, HaloArea>();
  for (const entityId of Object.keys(states)) {
    const m = SELECT_RE.exec(entityId);
    if (!m) continue;
    // Strip the known prefix/suffix instead of trusting the greedy group,
    // so area keys containing "_mood"/"_preset" still resolve correctly.
    const key = entityId
      .replace(/^select\.halo_/, "")
      .replace(/_(mood|preset)$/, "");
    let area = byKey.get(key);
    if (!area) {
      area = { key, moodEntityId: null, presetEntityId: null };
      byKey.set(key, area);
    }
    if (m[2] === "mood") area.moodEntityId = entityId;
    else area.presetEntityId = entityId;
  }
  return [...byKey.values()].sort((a, b) => a.key.localeCompare(b.key));
}

export const moodEntityId = (key: string): string =>
  `select.halo_${key}_mood`;
export const presetEntityId = (key: string): string =>
  `select.halo_${key}_preset`;
export const resyncButtonId = (key: string): string =>
  `button.halo_${key}_resync`;
export const sensorEntityId = (
  key: string,
  suffix: "active_mood" | "active_preset" | "status"
): string => `sensor.halo_${key}_${suffix}`;

export function asStringArray(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((v): v is string => typeof v === "string")
    : [];
}

/** entity -> attr -> [expected, actual], from the status sensor. */
export type MismatchDetails = Record<string, Record<string, unknown>>;

export function asMismatchDetails(value: unknown): MismatchDetails {
  if (typeof value !== "object" || value === null) return {};
  const out: MismatchDetails = {};
  for (const [entity, attrs] of Object.entries(value as Record<string, unknown>)) {
    if (typeof attrs === "object" && attrs !== null) {
      out[entity] = attrs as Record<string, unknown>;
    }
  }
  return out;
}

/** "light.x (brightness, rgb_color)" lines for the drift display. */
export function driftLines(
  mismatched: string[],
  details: MismatchDetails
): string[] {
  const entities =
    mismatched.length > 0 ? mismatched : Object.keys(details);
  return entities.map((entity) => {
    const attrs = Object.keys(details[entity] ?? {});
    return attrs.length > 0 ? `${entity} (${attrs.join(", ")})` : entity;
  });
}

export function asStatus(value: unknown): HaloStatus {
  return value === "active" || value === "transitioning"
    ? value
    : "custom";
}

/** mood -> preset -> scene.* / script.* action, from the status sensor. */
export type ActionMapping = Record<string, Record<string, string>>;

export function asMapping(value: unknown): ActionMapping {
  if (typeof value !== "object" || value === null) return {};
  const out: ActionMapping = {};
  for (const [mood, presets] of Object.entries(
    value as Record<string, unknown>
  )) {
    if (typeof presets !== "object" || presets === null) continue;
    const inner: Record<string, string> = {};
    for (const [preset, action] of Object.entries(
      presets as Record<string, unknown>
    )) {
      if (typeof action === "string" && action.length > 0) inner[preset] = action;
    }
    if (Object.keys(inner).length > 0) out[mood] = inner;
  }
  return out;
}

export function actionFor(
  mapping: ActionMapping,
  mood: string | null,
  preset: string
): string | null {
  if (!mood) return null;
  return mapping[mood]?.[preset] ?? null;
}

/** Friendly area name from the status sensor, falling back to the key. */
export function areaDisplayName(
  states: Record<string, HassEntity>,
  key: string
): string {
  const name = states[sensorEntityId(key, "status")]?.attributes.area_name;
  return typeof name === "string" && name.length > 0 ? name : key;
}

/** mood -> designated default preset, from the status sensor. */
export type DefaultsMap = Record<string, string>;

export function asDefaults(value: unknown): DefaultsMap {
  if (typeof value !== "object" || value === null) return {};
  const out: DefaultsMap = {};
  for (const [mood, preset] of Object.entries(value as Record<string, unknown>)) {
    if (typeof preset === "string" && preset.length > 0) out[mood] = preset;
  }
  return out;
}

export function isDefaultPreset(
  defaults: DefaultsMap,
  mood: string | null,
  preset: string,
  presets: string[]
): boolean {
  if (!mood || !presets.includes(preset)) return false;
  // Mirror the backend chain (designated -> base -> legacy default ->
  // first) so the marker agrees with what a bare request resolves to.
  const designated = defaults[mood];
  if (designated && presets.includes(designated)) return designated === preset;
  if (presets.includes("base")) return preset === "base";
  if (presets.includes("default")) return preset === "default";
  return presets[0] === preset;
}

export function isDarkMode(hass: {
  themes?: { darkMode?: boolean };
}): boolean {
  const flag = hass.themes?.darkMode;
  if (typeof flag === "boolean") return flag;
  if (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function"
  ) {
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  }
  return false;
}

export function brandMarkSrc(hass: {
  themes?: { darkMode?: boolean };
}): string {
  return isDarkMode(hass)
    ? "/halo_static/halo-mark.png"
    : "/halo_static/halo-mark-dark.png";
}

export type PanelView =
  | { name: "areas" }
  | { name: "manage"; area: string; mood: string | null };

/**
 * Hash sub-routes for the panel (`#/manage/<area>[/<mood>]`). HA owns the
 * path (`/halo`); the hash is ours — it survives refresh and drives the
 * back button without a reload.
 */
export function parseRoute(hash: string): PanelView {
  const parts = hash.replace(/^#\/?/, "").split("/").map(decodeURIComponent);
  if (parts[0] === "manage" && parts[1]) {
    return { name: "manage", area: parts[1], mood: parts[2] || null };
  }
  return { name: "areas" };
}

export function routeHref(view: PanelView): string {
  if (view.name === "manage") {
    const trail = view.mood
      ? `/${encodeURIComponent(view.area)}/${encodeURIComponent(view.mood)}`
      : `/${encodeURIComponent(view.area)}`;
    return `#/manage${trail}`;
  }
  return "#/";
}

export function sameView(a: PanelView, b: PanelView): boolean {
  if (a.name !== b.name) return false;
  if (a.name === "manage" && b.name === "manage") {
    return a.area === b.area && (a.mood ?? null) === (b.mood ?? null);
  }
  return true;
}
