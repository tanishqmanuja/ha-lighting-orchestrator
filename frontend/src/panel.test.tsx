// @vitest-environment happy-dom
import { beforeEach, describe, expect, it, vi } from "vitest";
// ?inline CSS is a vite-build feature; under vitest it resolves empty, so
// stub it (the real content is verified in the built bundle instead).
vi.mock("./styles.css?inline", () => ({
  default: "halo-panel{--halo-bg:test;}",
}));
import type { HomeAssistant } from "./ha-types";
import "./main";

function fakeHass(): HomeAssistant & { calls: unknown[] } {
  const calls: unknown[] = [];
  const wsCalls: unknown[] = [];
  const callWS = vi.fn(
    async (msg: Record<string, unknown>): Promise<unknown> => {
      wsCalls.push(msg);
      if (msg.type === "halo/config/get") {
        return {
          area: "living_room",
          area_name: "Living",
          lock: null,
          moods: {
            evening: {
              presets: {
                default: { action: "scene.a", verify: "auto" },
                bright: { action: "script.c", verify: "off" },
              },
              default_preset: "default",
              tracked_entities: [],
              transition: 1,
              settle: 3,
              debounce: 1,
              tolerance: 2,
              ignore_attrs: [],
              ignore_unavailable: true,
            },
          },
        };
      }
      if (msg.type === "halo/config/set_mood") {
        return { saved: msg.mood, missing_actions: [] };
      }
      if (msg.type === "halo/config/suggest_tracked") {
        return { entities: ["light.a", "light.b"] };
      }
      return {};
    }
  ) as unknown as <T>(message: Record<string, unknown>) => Promise<T>;
  const hass: HomeAssistant & { calls: unknown[]; wsCalls: unknown[] } = {
    calls,
    wsCalls,
    themes: { darkMode: false },
    states: {
      "select.halo_living_room_mood": {
        entity_id: "select.halo_living_room_mood",
        state: "evening",
        attributes: { options: ["evening", "movie"] },
      },
      "select.halo_living_room_preset": {
        entity_id: "select.halo_living_room_preset",
        state: "default",
        attributes: { options: ["bright", "default"] },
      },
      "sensor.halo_living_room_active_mood": {
        entity_id: "sensor.halo_living_room_active_mood",
        state: "evening",
        attributes: {},
      },
      "sensor.halo_living_room_active_preset": {
        entity_id: "sensor.halo_living_room_active_preset",
        state: "default",
        attributes: {},
      },
      "sensor.halo_living_room_status": {
        entity_id: "sensor.halo_living_room_status",
        state: "active",
        attributes: {
          area_name: "Living Room",
          mismatched_entities: [],
          mapping: {
            evening: {
              default: "scene.living_evening_default",
              bright: "scene.living_evening_bright",
            },
          },
          default_presets: { evening: "default" },
        },
      },
    },
    callService: vi.fn(async (...args: unknown[]) => {
      calls.push(args);
    }),
    callWS,
  };
  return hass;
}

const tick = () => new Promise((r) => setTimeout(r, 20));

describe("<halo-panel>", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
    window.location.hash = "";
  });

  it("renders area cards once hass is assigned (normal ordering)", async () => {
    const el = document.createElement("halo-panel") as HTMLElement & {
      hass: HomeAssistant;
    };
    document.body.appendChild(el);
    el.hass = fakeHass();
    await tick();
    expect(el.innerHTML).toContain("living_room");
    expect(el.innerHTML).toContain("evening");
    expect(el.innerHTML).toContain("resync");
  });

  it("shows the friendly name as title with the id as subtitle", async () => {
    const el = document.createElement("halo-panel") as HTMLElement & {
      hass: HomeAssistant;
    };
    document.body.appendChild(el);
    el.hass = fakeHass();
    await tick();
    const title = el.querySelector(".card-title");
    const subtitle = el.querySelector(".card-subtitle");
    expect(title?.textContent).toBe("Living Room");
    expect(subtitle?.textContent).toBe("living_room");
  });

  it("injects the stylesheet inside the element (shadow-DOM safe)", async () => {
    const el = document.createElement("halo-panel") as HTMLElement & {
      hass: HomeAssistant;
    };
    document.body.appendChild(el);
    el.hass = fakeHass();
    await tick();
    // document.head styles cannot pierce HA's shadow DOM, so the panel
    // must carry its own <style> tag.
    const style = el.querySelector(":scope > style");
    expect(style).not.toBeNull();
    // CSS itself is mocked in tests; what matters is placement.
    expect(style!.textContent).toContain("halo-panel");
  });

  it("renders when hass was assigned before upgrade (own-property shadow)", async () => {
    // HA can create the element and assign .hass before our module defines
    // the element; the own data property then shadows the prototype setter.
    const el = document.createElement("halo-panel") as HTMLElement & {
      hass: HomeAssistant;
    };
    Object.defineProperty(el, "hass", {
      value: fakeHass(),
      writable: true,
      configurable: true,
    });
    document.body.appendChild(el);
    await tick();
    expect(el.innerHTML).toContain("living_room");
  });

  it("clicking a mood calls select.select_option", async () => {
    const hass = fakeHass();
    const el = document.createElement("halo-panel") as HTMLElement & {
      hass: HomeAssistant;
    };
    document.body.appendChild(el);
    el.hass = hass;
    await tick();
    const btn = [...el.querySelectorAll("button")].find(
      (b) => b.textContent === "movie"
    );
    expect(btn).toBeDefined();
    btn!.click();
    await tick();
    expect(hass.callService).toHaveBeenCalledWith("select", "select_option", {
      entity_id: "select.halo_living_room_mood",
      option: "movie",
    });
  });

  it("shows which scene each preset runs", async () => {
    const el = document.createElement("halo-panel") as HTMLElement & {
      hass: HomeAssistant;
    };
    document.body.appendChild(el);
    el.hass = fakeHass();
    await tick();
    expect(el.innerHTML).toContain("scene.living_evening_default");
    expect(el.innerHTML).toContain("scene.living_evening_bright");
  });

  it("resync-all calls halo.resync without an area", async () => {
    const hass = fakeHass();
    const el = document.createElement("halo-panel") as HTMLElement & {
      hass: HomeAssistant;
    };
    document.body.appendChild(el);
    el.hass = hass;
    await tick();
    const btn = [...el.querySelectorAll("button")].find(
      (b) => b.textContent === "Resync all"
    );
    expect(btn).toBeDefined();
    btn!.click();
    await tick();
    expect(hass.callService).toHaveBeenCalledWith("halo", "resync", {});
  });

  it("links to the integration configure page", async () => {
    const el = document.createElement("halo-panel") as HTMLElement & {
      hass: HomeAssistant;
    };
    document.body.appendChild(el);
    el.hass = fakeHass();
    await tick();
    const link = el.querySelector("a");
    expect(link?.getAttribute("href")).toBe(
      "/config/integrations/integration/halo"
    );
  });

  it("shows empty state with no halo areas", async () => {
    const hass = fakeHass();
    hass.states = {};
    const el = document.createElement("halo-panel") as HTMLElement & {
      hass: HomeAssistant;
    };
    document.body.appendChild(el);
    el.hass = hass;
    await tick();
    expect(el.innerHTML).toContain("No areas yet.");
  });

  it("manage opens the mapping editor and saves via websocket", async () => {
    const hass = fakeHass();
    const el = document.createElement("halo-panel") as HTMLElement & {
      hass: HomeAssistant;
    };
    document.body.appendChild(el);
    el.hass = hass;
    await tick();
    const manage = [...el.querySelectorAll("button")].find(
      (b) => b.textContent === "Manage"
    );
    expect(manage).toBeDefined();
    manage!.click();
    await tick();
    await tick();
    // editor lists the evening mood with its preset action field
    const actionInput = el.querySelector(
      'input[aria-label="Action entity"]'
    ) as HTMLInputElement | null;
    expect(actionInput).not.toBeNull();
    expect(actionInput!.value).toBe("scene.a");
    const nativeSet = Object.getOwnPropertyDescriptor(
      window.HTMLInputElement.prototype,
      "value"
    )!.set!;
    nativeSet.call(actionInput, "scene.b");
    actionInput!.dispatchEvent(new Event("input", { bubbles: true }));
    const save = [...el.querySelectorAll("button")].find(
      (b) => b.textContent === "Save"
    );
    expect(save).toBeDefined();
    save!.click();
    await tick();
    await tick();
    expect(hass.callWS).toHaveBeenCalledWith(
      expect.objectContaining({
        type: "halo/config/set_mood",
        area: "living_room",
        mood: "evening",
      })
    );
    const sent = (hass.callWS as ReturnType<typeof vi.fn>).mock.calls.find(
      (c) => (c[0] as Record<string, unknown>).type === "halo/config/set_mood"
    );
    expect(
      ((sent![0] as Record<string, unknown>).config as Record<string, unknown>)
        .presets
    ).toEqual({
      default: { action: "scene.b", verify: "auto" },
      bright: { action: "script.c", verify: "off" },
    });
  });

  it("marks the default preset and saves a changed default", async () => {
    const hass = fakeHass();
    const el = document.createElement("halo-panel") as HTMLElement & {
      hass: HomeAssistant;
    };
    document.body.appendChild(el);
    el.hass = hass;
    await tick();
    // card marks the designated default preset
    const presetBtn = [...el.querySelectorAll(".preset-main")].find((b) =>
      (b.textContent ?? "").startsWith("default")
    );
    expect(presetBtn?.querySelector(".preset-default")?.textContent).toBe(
      " · default"
    );
    // editor can re-designate it
    [...el.querySelectorAll("button")]
      .find((b) => b.textContent === "Manage")!
      .click();
    await tick();
    await tick();
    const defSel = el.querySelector(
      'select[aria-label="Default preset"]'
    ) as HTMLSelectElement;
    expect(defSel).not.toBeNull();
    expect(defSel.value).toBe("default");
    const nativeSet = Object.getOwnPropertyDescriptor(
      window.HTMLSelectElement.prototype,
      "value"
    )!.set!;
    nativeSet.call(defSel, "bright");
    defSel.dispatchEvent(new Event("change", { bubbles: true }));
    [...el.querySelectorAll("button")]
      .find((b) => b.textContent === "Save")!
      .click();
    await tick();
    await tick();
    const sent = (hass.callWS as ReturnType<typeof vi.fn>).mock.calls.find(
      (c) => (c[0] as Record<string, unknown>).type === "halo/config/set_mood"
    );
    expect((sent![0] as Record<string, unknown>).config).toEqual(
      expect.objectContaining({ default_preset: "bright" })
    );
  });

  it("autofill sits inline with a tooltip", async () => {
    const hass = fakeHass();
    const el = document.createElement("halo-panel") as HTMLElement & {
      hass: HomeAssistant;
    };
    document.body.appendChild(el);
    el.hass = hass;
    await tick();
    [...el.querySelectorAll("button")]
      .find((b) => b.textContent === "Manage")!
      .click();
    await tick();
    await tick();
    const tracked = el.querySelector(
      'input[aria-label="Tracked entities"]'
    ) as HTMLInputElement;
    expect(tracked.value).toBe("");
    const autofill = [...el.querySelectorAll("button")].find(
      (b) => b.textContent === "Autofill"
    ) as HTMLButtonElement;
    expect(autofill.title).toBe("Autofill from scenes");
    // same row as the input, not stacked below it
    expect(autofill.parentElement).toBe(tracked.parentElement);
    autofill.click();
    await tick();
    await tick();
    expect(tracked.value).toBe("light.a, light.b");
    expect(el.innerHTML).toContain("2 entities filled");
  });

  it("verify override is sent per preset", async () => {
    const hass = fakeHass();
    const el = document.createElement("halo-panel") as HTMLElement & {
      hass: HomeAssistant;
    };
    document.body.appendChild(el);
    el.hass = hass;
    await tick();
    [...el.querySelectorAll("button")]
      .find((b) => b.textContent === "Manage")!
      .click();
    await tick();
    await tick();
    // bright (script) preset arrives with verify=off preselected
    const verifySels = [
      ...el.querySelectorAll('select[aria-label^="Verify "]'),
    ] as HTMLSelectElement[];
    expect(verifySels.length).toBe(2);
    expect(verifySels[1].value).toBe("off");
    // flip default (scene) preset to a reference scene, then save
    const nativeSet = Object.getOwnPropertyDescriptor(
      window.HTMLSelectElement.prototype,
      "value"
    )!.set!;
    nativeSet.call(verifySels[0], "scene");
    verifySels[0].dispatchEvent(new Event("change", { bubbles: true }));
    await tick();
    await tick();
    const refInput = el.querySelector(
      'input[aria-label="Reference scene"]'
    ) as HTMLInputElement;
    const nativeText = Object.getOwnPropertyDescriptor(
      window.HTMLInputElement.prototype,
      "value"
    )!.set!;
    nativeText.call(refInput, "scene.living_evening_base");
    refInput.dispatchEvent(new Event("input", { bubbles: true }));
    [...el.querySelectorAll("button")]
      .find((b) => b.textContent === "Save")!
      .click();
    await tick();
    await tick();
    const sent = (hass.callWS as ReturnType<typeof vi.fn>).mock.calls.find(
      (c) => (c[0] as Record<string, unknown>).type === "halo/config/set_mood"
    );
    const presets = (
      (sent![0] as Record<string, unknown>).config as Record<string, unknown>
    ).presets as Record<string, { action: string; verify: string }>;
    expect(presets.default.verify).toBe("scene.living_evening_base");
    expect(presets.bright.verify).toBe("off");
  });

  it("same-scene shortcut fills the reference without typing", async () => {
    const hass = fakeHass();
    const el = document.createElement("halo-panel") as HTMLElement & {
      hass: HomeAssistant;
    };
    document.body.appendChild(el);
    el.hass = hass;
    await tick();
    [...el.querySelectorAll("button")]
      .find((b) => b.textContent === "Manage")!
      .click();
    await tick();
    await tick();
    const verifySels = [
      ...el.querySelectorAll('select[aria-label^="Verify "]'),
    ] as HTMLSelectElement[];
    // default preset runs a scene and verifies auto: shortcut offered
    expect([...verifySels[0].options].map((o) => o.value)).toContain("__same");
    const nativeSet = Object.getOwnPropertyDescriptor(
      window.HTMLSelectElement.prototype,
      "value"
    )!.set!;
    nativeSet.call(verifySels[0], "__same");
    verifySels[0].dispatchEvent(new Event("change", { bubbles: true }));
    await tick();
    const refInput = el.querySelector(
      'input[aria-label="Reference scene"]'
    ) as HTMLInputElement;
    expect(refInput.value).toBe("scene.a");
    [...el.querySelectorAll("button")]
      .find((b) => b.textContent === "Save")!
      .click();
    await tick();
    await tick();
    const sent = (hass.callWS as ReturnType<typeof vi.fn>).mock.calls.find(
      (c) => (c[0] as Record<string, unknown>).type === "halo/config/set_mood"
    );
    const presets = (
      (sent![0] as Record<string, unknown>).config as Record<string, unknown>
    ).presets as Record<string, { action: string; verify: string }>;
    expect(presets.default.verify).toBe("scene.a");
  });

  it("manage page explains verification with units", async () => {
    const hass = fakeHass();
    const el = document.createElement("halo-panel") as HTMLElement & {
      hass: HomeAssistant;
    };
    document.body.appendChild(el);
    el.hass = hass;
    await tick();
    [...el.querySelectorAll("button")]
      .find((b) => b.textContent === "Manage")!
      .click();
    await tick();
    await tick();
    expect(el.innerHTML).toContain("How verification works.");
    for (const label of [
      "Transition (s)",
      "Settle (s)",
      "Debounce (s)",
      "Tolerance (±)",
    ]) {
      expect(el.innerHTML).toContain(label);
    }
  });

  it("shows the brand mark in the header", async () => {
    const el = document.createElement("halo-panel") as HTMLElement & {
      hass: HomeAssistant;
    };
    document.body.appendChild(el);
    el.hass = fakeHass();
    await tick();
    const img = el.querySelector(
      "img.brand-mark"
    ) as HTMLImageElement | null;
    expect(img).not.toBeNull();
    expect(img!.getAttribute("src")).toBe("/halo_static/halo-mark-dark.png");
  });

  it("shows the light mark in dark mode", async () => {
    const hass = fakeHass();
    hass.themes = { darkMode: true };
    const el = document.createElement("halo-panel") as HTMLElement & {
      hass: HomeAssistant;
    };
    document.body.appendChild(el);
    el.hass = hass;
    await tick();
    const img = el.querySelector(
      "img.brand-mark"
    ) as HTMLImageElement | null;
    expect(img?.getAttribute("src")).toBe("/halo_static/halo-mark.png");
  });

  it("editor separates presets from verification with headings", async () => {
    const hass = fakeHass();
    const el = document.createElement("halo-panel") as HTMLElement & {
      hass: HomeAssistant;
    };
    document.body.appendChild(el);
    el.hass = hass;
    await tick();
    [...el.querySelectorAll("button")]
      .find((b) => b.textContent === "Manage")!
      .click();
    await tick();
    await tick();
    expect(el.querySelector(".editor-title")).toBeNull();
    const sections = [...el.querySelectorAll(".section-title")].map(
      (s) => s.textContent
    );
    expect(sections).toEqual(["Presets", "Verification"]);
    // preset blocks live in a list container so dividers can skip the last
    const list = el.querySelector(".preset-list");
    expect(list).not.toBeNull();
    expect(list!.querySelectorAll(":scope > .preset-block").length).toBe(2);
    expect(el.querySelector(".editor-sub")).toBeNull();
  });

  it("post script round-trips through the editor", async () => {
    const hass = fakeHass();
    const el = document.createElement("halo-panel") as HTMLElement & {
      hass: HomeAssistant;
    };
    document.body.appendChild(el);
    el.hass = hass;
    await tick();
    [...el.querySelectorAll("button")]
      .find((b) => b.textContent === "Manage")!
      .click();
    await tick();
    await tick();
    const post = el.querySelector(
      'input[aria-label="Post script"]'
    ) as HTMLInputElement;
    expect(post).not.toBeNull();
    expect(post.value).toBe("");
    const nativeSet = Object.getOwnPropertyDescriptor(
      window.HTMLInputElement.prototype,
      "value"
    )!.set!;
    nativeSet.call(post, "script.done");
    post.dispatchEvent(new Event("input", { bubbles: true }));
    [...el.querySelectorAll("button")]
      .find((b) => b.textContent === "Save")!
      .click();
    await tick();
    await tick();
    const sent = (hass.callWS as ReturnType<typeof vi.fn>).mock.calls.find(
      (c) => (c[0] as Record<string, unknown>).type === "halo/config/set_mood"
    );
    expect((sent![0] as Record<string, unknown>).config).toEqual(
      expect.objectContaining({ post_action: "script.done" })
    );
  });

  it("manage click writes the route hash", async () => {
    const hass = fakeHass();
    const el = document.createElement("halo-panel") as HTMLElement & {
      hass: HomeAssistant;
    };
    document.body.appendChild(el);
    el.hass = hass;
    await tick();
    [...el.querySelectorAll("button")]
      .find((b) => b.textContent === "Manage")!
      .click();
    await tick();
    expect(window.location.hash).toBe("#/manage/living_room/evening");
  });

  it("restores the manage page from the URL on load", async () => {
    window.location.hash = "#/manage/living_room/evening";
    const hass = fakeHass();
    const el = document.createElement("halo-panel") as HTMLElement & {
      hass: HomeAssistant;
    };
    document.body.appendChild(el);
    el.hass = hass;
    await tick();
    await tick();
    expect(el.querySelector(".grid")).toBeNull();
    expect(el.innerHTML).toContain("Manage · Living");
    expect(
      el.querySelector(".seg-item.active")?.textContent
    ).toContain("evening");
  });

  it("kind toggle swaps prefixes and filters verify options", async () => {
    const hass = fakeHass();
    const el = document.createElement("halo-panel") as HTMLElement & {
      hass: HomeAssistant;
    };
    document.body.appendChild(el);
    el.hass = hass;
    await tick();
    [...el.querySelectorAll("button")]
      .find((b) => b.textContent === "Manage")!
      .click();
    await tick();
    await tick();
    // script row offers Trust apply but not Same scene
    const scriptVerify = el.querySelector(
      'select[aria-label="Verify bright"]'
    ) as HTMLSelectElement;
    const scriptOpts = [...scriptVerify.options].map((o) => o.value);
    expect(scriptOpts).toContain("off");
    expect(scriptOpts).not.toContain("__same");
    // flip bright row to Scene: prefix swapped, options change
    const sceneBtn = [
      ...el.querySelectorAll('[aria-label="Action kind for bright"] button'),
    ].find((b) => b.textContent === "Scene") as HTMLButtonElement;
    sceneBtn.click();
    await tick();
    const actionInputs = [
      ...el.querySelectorAll('input[aria-label="Action entity"]'),
    ] as HTMLInputElement[];
    expect(actionInputs[1].value).toBe("scene.c");
    const sceneOptsAfter = [...scriptVerify.options].map((o) => o.value);
    expect(sceneOptsAfter).toContain("__same");
    expect(sceneOptsAfter).not.toContain("off");
    // save sends the full id untouched
    [...el.querySelectorAll("button")]
      .find((b) => b.textContent === "Save")!
      .click();
    await tick();
    await tick();
    const sent = (hass.callWS as ReturnType<typeof vi.fn>).mock.calls.find(
      (c) => (c[0] as Record<string, unknown>).type === "halo/config/set_mood"
    );
    const presets = (
      (sent![0] as Record<string, unknown>).config as Record<string, unknown>
    ).presets as Record<string, { action: string }>;
    expect(presets.bright.action).toBe("scene.c");
  });

  it("bare action ids are rejected client-side with the server rule", async () => {
    const hass = fakeHass();
    const el = document.createElement("halo-panel") as HTMLElement & {
      hass: HomeAssistant;
    };
    document.body.appendChild(el);
    el.hass = hass;
    await tick();
    [...el.querySelectorAll("button")]
      .find((b) => b.textContent === "Manage")!
      .click();
    await tick();
    await tick();
    const actionInputs = [
      ...el.querySelectorAll('input[aria-label="Action entity"]'),
    ] as HTMLInputElement[];
    const nativeSet = Object.getOwnPropertyDescriptor(
      window.HTMLInputElement.prototype,
      "value"
    )!.set!;
    nativeSet.call(actionInputs[0], "evening_lights");
    actionInputs[0].dispatchEvent(new Event("input", { bubbles: true }));
    [...el.querySelectorAll("button")]
      .find((b) => b.textContent === "Save")!
      .click();
    await tick();
    await tick();
    expect(el.innerHTML).toContain("needs a full id like scene.x");
    const badInput = el.querySelector(
      'input[aria-label="Action entity"][aria-invalid="true"]'
    );
    expect(badInput).not.toBeNull();
    expect(el.querySelector(".form-field-error")).not.toBeNull();
    const sent = (hass.callWS as ReturnType<typeof vi.fn>).mock.calls.find(
      (c) => (c[0] as Record<string, unknown>).type === "halo/config/set_mood"
    );
    expect(sent).toBeUndefined();
  });

  it("snapshot mode is offered and saved per preset", async () => {
    const hass = fakeHass();
    const el = document.createElement("halo-panel") as HTMLElement & {
      hass: HomeAssistant;
    };
    document.body.appendChild(el);
    el.hass = hass;
    await tick();
    [...el.querySelectorAll("button")]
      .find((b) => b.textContent === "Manage")!
      .click();
    await tick();
    await tick();
    const verifySel = el.querySelector(
      'select[aria-label="Verify default"]'
    ) as HTMLSelectElement;
    expect([...verifySel.options].map((o) => o.value)).toContain("snapshot");
    const nativeSet = Object.getOwnPropertyDescriptor(
      window.HTMLSelectElement.prototype,
      "value"
    )!.set!;
    nativeSet.call(verifySel, "snapshot");
    verifySel.dispatchEvent(new Event("change", { bubbles: true }));
    [...el.querySelectorAll("button")]
      .find((b) => b.textContent === "Save")!
      .click();
    await tick();
    await tick();
    const sent = (hass.callWS as ReturnType<typeof vi.fn>).mock.calls.find(
      (c) => (c[0] as Record<string, unknown>).type === "halo/config/set_mood"
    );
    const presets = (
      (sent![0] as Record<string, unknown>).config as Record<string, unknown>
    ).presets as Record<string, { action: string; verify: string }>;
    expect(presets.default.verify).toBe("snapshot");
  });

  it("drift line names the mismatching attributes", async () => {
    const hass = fakeHass();
    hass.states["sensor.halo_living_room_status"] = {
      entity_id: "sensor.halo_living_room_status",
      state: "custom",
      attributes: {
        mismatched_entities: ["light.living_main"],
        mismatch_details: {
          "light.living_main": { brightness: [128, 5] },
        },
      },
    };
    const el = document.createElement("halo-panel") as HTMLElement & {
      hass: HomeAssistant;
    };
    document.body.appendChild(el);
    el.hass = hass;
    await tick();
    expect(el.innerHTML).toContain("light.living_main (brightness)");
  });

  it("no drift banner when active on another mood (requested diff is not drift)", async () => {
    const hass = fakeHass();
    hass.states["sensor.halo_living_room_status"] = {
      entity_id: "sensor.halo_living_room_status",
      state: "active",
      attributes: {
        mismatched_entities: [],
        mismatch_details: {
          "light.living_main": { state: ["off", "on"] },
        },
      },
    };
    const el = document.createElement("halo-panel") as HTMLElement & {
      hass: HomeAssistant;
    };
    document.body.appendChild(el);
    el.hass = hass;
    await tick();
    expect(el.innerHTML).not.toContain("Manual changes detected");
  });

  it("manage opens a separate page with back navigation", async () => {
    const hass = fakeHass();
    const el = document.createElement("halo-panel") as HTMLElement & {
      hass: HomeAssistant;
    };
    document.body.appendChild(el);
    el.hass = hass;
    await tick();
    [...el.querySelectorAll("button")]
      .find((b) => b.textContent === "Manage")!
      .click();
    await tick();
    await tick();
    // area cards are gone, manage topbar shows the friendly name
    expect(el.querySelector(".grid")).toBeNull();
    expect(el.innerHTML).toContain("Manage · Living");
    [...el.querySelectorAll("button")]
      .find((b) => b.textContent?.includes("All areas"))!
      .click();
    await tick();
    expect(el.querySelector(".grid")).not.toBeNull();
    expect(el.innerHTML).toContain("living_room");
  });

  it("preset rows are full width with a working apply button", async () => {
    const hass = fakeHass();
    const el = document.createElement("halo-panel") as HTMLElement & {
      hass: HomeAssistant;
    };
    document.body.appendChild(el);
    el.hass = hass;
    await tick();
    // one clickable row per preset, apply nested inside (no nested buttons)
    const rows = [...el.querySelectorAll(".preset-main[role='button']")];
    expect(rows.length).toBe(2);
    expect(el.querySelectorAll("button.preset-main").length).toBe(0);
    // the already-active preset (default) gets no apply button
    const applyBtns = [...el.querySelectorAll("button.preset-apply")];
    expect(applyBtns.length).toBe(1);
    expect(applyBtns[0].textContent).toBe("Apply");
    (applyBtns[0] as HTMLButtonElement).click();
    await tick();
    expect(hass.callService).toHaveBeenCalledWith("select", "select_option", {
      entity_id: "select.halo_living_room_preset",
      option: "bright",
    });
    // keyboard activation on the row works too
    const brightRow = rows[0] as HTMLElement;
    brightRow.dispatchEvent(
      new KeyboardEvent("keydown", { key: "Enter", bubbles: true })
    );
    await tick();
    expect(hass.callService).toHaveBeenCalledWith("select", "select_option", {
      entity_id: "select.halo_living_room_preset",
      option: "bright",
    });
  });
});
