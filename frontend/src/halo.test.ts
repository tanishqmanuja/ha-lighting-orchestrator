import { describe, expect, it } from "vitest";
import {
  actionFor,
  areaDisplayName,
  asDefaults,
  asMapping,
  asMismatchDetails,
  asStatus,
  brandMarkSrc,
  discoverAreas,
  driftLines,
  isDarkMode,
  isDefaultPreset,
  parseRoute,
  routeHref,
  sameView,
  moodEntityId,
  presetEntityId,
  resyncButtonId,
  sensorEntityId,
} from "./halo";
import type { HassEntity } from "./ha-types";

const ent = (entity_id: string, state = "on"): HassEntity => ({
  entity_id,
  state,
  attributes: {},
});

describe("discoverAreas", () => {
  it("pairs mood + preset selects per area", () => {
    const areas = discoverAreas({
      "select.halo_living_room_mood": ent("select.halo_living_room_mood"),
      "select.halo_living_room_preset": ent("select.halo_living_room_preset"),
      "light.kitchen": ent("light.kitchen"),
    });
    expect(areas).toEqual([
      {
        key: "living_room",
        moodEntityId: "select.halo_living_room_mood",
        presetEntityId: "select.halo_living_room_preset",
      },
    ]);
  });

  it("tolerates a missing preset select", () => {
    const areas = discoverAreas({
      "select.halo_office_mood": ent("select.halo_office_mood"),
    });
    expect(areas[0].presetEntityId).toBeNull();
  });

  it("keeps area keys containing _mood intact", () => {
    const areas = discoverAreas({
      "select.halo_mood_room_mood": ent("select.halo_mood_room_mood"),
    });
    expect(areas[0].key).toBe("mood_room");
  });
});

describe("entity id builders", () => {
  it("build round-trippable ids", () => {
    expect(moodEntityId("living_room")).toBe("select.halo_living_room_mood");
    expect(presetEntityId("living_room")).toBe(
      "select.halo_living_room_preset"
    );
    expect(resyncButtonId("living_room")).toBe("button.halo_living_room_resync");
    expect(sensorEntityId("living_room", "status")).toBe(
      "sensor.halo_living_room_status"
    );
  });
});

describe("asStatus", () => {
  it("falls back to custom for unknown values", () => {
    expect(asStatus("active")).toBe("active");
    expect(asStatus("bogus")).toBe("custom");
    expect(asStatus(undefined)).toBe("custom");
  });
});

describe("asMapping / actionFor", () => {
  it("keeps only string actions", () => {
    expect(
      asMapping({
        evening: { default: "scene.x", bright: "script.y", broken: 42 },
        empty: {},
      })
    ).toEqual({ evening: { default: "scene.x", bright: "script.y" } });
    expect(asMapping(null)).toEqual({});
  });

  it("resolves the action for a mood/preset pair", () => {
    const m = { movie: { none: "script.movie" } };
    expect(actionFor(m, "movie", "none")).toBe("script.movie");
    expect(actionFor(m, "movie", "bright")).toBeNull();
    expect(actionFor(m, null, "none")).toBeNull();
  });
});

describe("asDefaults / isDefaultPreset", () => {  it("parses the defaults map and falls back to 'default'", () => {
    expect(asDefaults({ party: "wild", x: 42 })).toEqual({ party: "wild" });
    expect(isDefaultPreset({ party: "wild" }, "party", "wild", ["wild", "base"])).toBe(true);
    expect(isDefaultPreset({ party: "wild" }, "party", "base", ["wild", "base"])).toBe(false);
    expect(isDefaultPreset({}, "evening", "base", ["base", "bright"])).toBe(true);
    expect(isDefaultPreset({}, "evening", "default", ["default", "bright"])).toBe(true);
    expect(isDefaultPreset({}, "evening", "bright", ["default", "bright"])).toBe(false);
    expect(isDefaultPreset({}, "evening", "x", ["x", "y"])).toBe(true);
  });
});

describe("areaDisplayName", () => {  it("prefers the friendly name, falls back to the key", () => {
    const withName = {
      "sensor.halo_living_room_status": ent(
        "sensor.halo_living_room_status",
        "active"
      ),
    } as Record<string, import("./ha-types").HassEntity>;
    (withName["sensor.halo_living_room_status"].attributes as Record<string, unknown>).area_name =
      "Living Room";
    expect(areaDisplayName(withName, "living_room")).toBe("Living Room");
    expect(areaDisplayName({}, "living_room")).toBe("living_room");
  });
});

describe("panel routes", () => {
  it("parses manage routes and falls back to the list", () => {
    expect(parseRoute("#/manage/living_room")).toEqual({
      name: "manage",
      area: "living_room",
      mood: null,
    });
    expect(parseRoute("#/manage/living_room/evening")).toEqual({
      name: "manage",
      area: "living_room",
      mood: "evening",
    });
    expect(parseRoute("")).toEqual({ name: "areas" });
    expect(parseRoute("#/")).toEqual({ name: "areas" });
    expect(parseRoute("#/manage/")).toEqual({ name: "areas" });
    expect(parseRoute("#/nope")).toEqual({ name: "areas" });
  });

  it("round-trips views through hrefs", () => {
    expect(routeHref({ name: "areas" })).toBe("#/");
    expect(routeHref({ name: "manage", area: "living_room", mood: null })).toBe(
      "#/manage/living_room"
    );
    expect(
      parseRoute(
        routeHref({ name: "manage", area: "living_room", mood: "evening" })
      )
    ).toEqual({ name: "manage", area: "living_room", mood: "evening" });
  });

  it("compares views", () => {
    expect(sameView({ name: "areas" }, { name: "areas" })).toBe(true);
    expect(
      sameView(
        { name: "manage", area: "a", mood: "m" },
        { name: "manage", area: "a", mood: "m" }
      )
    ).toBe(true);
    expect(
      sameView(
        { name: "manage", area: "a", mood: "m" },
        { name: "manage", area: "a", mood: null }
      )
    ).toBe(false);
    expect(
      sameView({ name: "areas" }, { name: "manage", area: "a", mood: null })
    ).toBe(false);
  });
});

describe("brand mark", () => {
  it("picks the mark from the HA theme flag first", () => {
    expect(brandMarkSrc({ themes: { darkMode: true } })).toBe(
      "/halo_static/halo-mark.png"
    );
    expect(brandMarkSrc({ themes: { darkMode: false } })).toBe(
      "/halo_static/halo-mark-dark.png"
    );
  });

  it("falls back to matchMedia without a theme flag", () => {
    const g = globalThis as Record<string, unknown>;
    const prev = g.window;
    g.window = { matchMedia: () => ({ matches: true }) };
    try {
      expect(isDarkMode({})).toBe(true);
      expect(brandMarkSrc({})).toBe("/halo_static/halo-mark.png");
    } finally {
      if (prev === undefined) delete g.window;
      else g.window = prev;
    }
  });
});

describe("mismatch details", () => {
  it("parses the details map and renders drift lines", () => {
    expect(asMismatchDetails(null)).toEqual({});
    expect(asMismatchDetails({ "light.x": "nope" })).toEqual({});
    const details = asMismatchDetails({
      "light.x": { brightness: [100, 40] },
    });
    expect(driftLines(["light.x"], details)).toEqual([
      "light.x (brightness)",
    ]);
    // falls back to entity-only lines without details
    expect(driftLines(["light.y"], {})).toEqual(["light.y"]);
    expect(driftLines([], {})).toEqual([]);
  });
});
