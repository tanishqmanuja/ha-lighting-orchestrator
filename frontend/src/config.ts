// Types + client for the halo/config/* websocket API (in-panel editing).
// The server validates strictly; the panel surfaces message strings as-is.

import type { HomeAssistant } from "./ha-types";

export interface MoodConfig {
  presets: Record<string, string>;
  /** preset -> "off" | "scene.<id>" (absent = auto). */
  verify: Record<string, string>;
  default_preset: string;
  /** Optional script ran once when this mood becomes active. */
  post_action: string;
  tracked_entities: string[];
  transition: number;
  settle: number;
  debounce: number;
  tolerance: number;
  ignore_attrs: string[];
  ignore_unavailable: boolean;
}

export interface AreaConfig {
  area: string;
  area_name: string;
  lock: string | null;
  moods: Record<string, MoodConfig>;
}

export function blankMood(): MoodConfig {
  return {
    presets: { base: "" },
    verify: {},
    default_preset: "base",
    post_action: "",
    tracked_entities: [],
    transition: 2,
    settle: 5,
    debounce: 2,
    tolerance: 1,
    ignore_attrs: [],
    ignore_unavailable: true,
  };
}

export async function fetchAreaConfig(
  hass: HomeAssistant,
  area: string
): Promise<AreaConfig> {
  const cfg = await hass.callWS<{
    area: string;
    area_name: string;
    lock: string | null;
    moods: Record<string, Record<string, unknown>>;
  }>({ type: "halo/config/get", area });
  // Server sends presets as {name: {action, verify}}; split into the two
  // editor maps (older shapes degrade to plain actions = auto).
  const moods: Record<string, MoodConfig> = {};
  for (const [name, m] of Object.entries(cfg.moods ?? {})) {
    const raw = (m as Record<string, unknown>).presets as Record<
      string,
      string | { action?: string; verify?: string }
    >;
    const presets: Record<string, string> = {};
    const verify: Record<string, string> = {};
    for (const [pname, pval] of Object.entries(raw ?? {})) {
      if (typeof pval === "string") {
        presets[pname] = pval;
      } else {
        presets[pname] = pval.action ?? "";
        if (pval.verify && pval.verify !== "auto") verify[pname] = pval.verify;
      }
    }
    moods[name] = {
      ...(m as object) as MoodConfig,
      presets,
      verify,
      post_action: asText((m as Record<string, unknown>).post_action),
    };
  }
  return { area: cfg.area, area_name: cfg.area_name, lock: cfg.lock, moods };
}

function asText(value: unknown): string {
  return typeof value === "string" ? value : "";
}

export interface SaveResult {
  saved: string;
  missing_actions: string[];
}

export async function saveMood(
  hass: HomeAssistant,
  area: string,
  mood: string,
  config: MoodConfig
): Promise<SaveResult> {
  const presets: Record<string, { action: string; verify: string }> = {};
  for (const [name, action] of Object.entries(config.presets)) {
    presets[name] = { action, verify: config.verify[name] ?? "auto" };
  }
  return hass.callWS<SaveResult>({
    type: "halo/config/set_mood",
    area,
    mood,
    config: {
      presets,
      default_preset: config.default_preset,
      post_action: config.post_action,
      tracked_entities: config.tracked_entities,
      transition: config.transition,
      settle: config.settle,
      debounce: config.debounce,
      tolerance: config.tolerance,
      ignore_attrs: config.ignore_attrs,
      ignore_unavailable: config.ignore_unavailable,
    },
  });
}

export async function deleteMood(
  hass: HomeAssistant,
  area: string,
  mood: string
): Promise<void> {
  await hass.callWS({ type: "halo/config/delete_mood", area, mood });
}

/**
 * What empty (auto-detect) would track for these actions, resolved from
 * scenes.yaml. Used to prefill the tracked field — still fully editable,
 * and clearing it restores auto behavior.
 */
export async function suggestTracked(
  hass: HomeAssistant,
  area: string,
  actions: string[]
): Promise<string[]> {
  const res = await hass.callWS<{ entities: string[] }>({
    type: "halo/config/suggest_tracked",
    area,
    actions,
  });
  return Array.isArray(res.entities) ? res.entities : [];
}

/** Human message from a failed callWS (HA wraps errors in various shapes). */
export function wsError(err: unknown): string {
  if (typeof err === "string") return err;
  if (err && typeof err === "object") {
    const e = err as Record<string, unknown>;
    if (typeof e.message === "string") return e.message;
    if (typeof e.error === "string") return e.error;
  }
  return "Save failed";
}
