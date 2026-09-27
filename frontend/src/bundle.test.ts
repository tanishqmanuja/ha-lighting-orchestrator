// @vitest-environment happy-dom
// TEMPORARY diagnostic: loads the committed built bundle (not src) and
// mounts it, to catch build-only breakage (minify, CSS inline, define).
import { describe, expect, it } from "vitest";

describe("built bundle smoke", () => {
  it("defines halo-panel and renders", async () => {
    // No types for the built bundle; type safety comes from src tests.
    // @ts-ignore
    await import("../../custom_components/halo/frontend/halo-panel.js");
    expect(customElements.get("halo-panel")).toBeDefined();
    const el = document.createElement("halo-panel") as HTMLElement & {
      hass: any;
    };
    document.body.appendChild(el);
    el.hass = {
      states: {
        "select.halo_test_mood": {
          entity_id: "select.halo_test_mood",
          state: "evening",
          attributes: { options: ["evening"] },
        },
      },
      callService: async () => {},
    };
    await new Promise((r) => setTimeout(r, 50));
    expect(el.innerHTML).toContain("test");
  });
});
