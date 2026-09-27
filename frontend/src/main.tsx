import { StrictMode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { App } from "./App";
import type { HomeAssistant } from "./ha-types";

/**
 * HA custom-panel bridge: HA creates <halo-panel> and assigns `.hass`
 * on every state change. We keep one React root and re-render with the
 * latest hass object (cheap: hass.states is a fresh object each time).
 */
class HaloPanel extends HTMLElement {
  private root: Root | null = null;
  private mounted = false;

  // Assigned by Home Assistant, not via attributes.
  declare hass: HomeAssistant;

  connectedCallback(): void {
    this.mounted = true;
    if (!this.root) {
      this.root = createRoot(this);
    }
    this.render();
  }

  disconnectedCallback(): void {
    this.mounted = false;
    // Unmount so React effect cleanups run (hashchange listener, etc.).
    // Without this, removed panels leak listeners across navigations.
    this.root?.unmount();
    this.root = null;
  }

  private render(): void {
    if (!this.mounted || !this.root) return;
    const hass = this.hass;
    if (!hass) return;
    this.root.render(
      <StrictMode>
        <App hass={hass} />
      </StrictMode>
    );
  }
}

// HA re-assigns `.hass` (plain property, no setter hook possible without
// patching), so intercept the assignment to trigger re-renders.
Object.defineProperty(HaloPanel.prototype, "hass", {
  get(this: HaloPanel & { _hass?: HomeAssistant }): HomeAssistant | undefined {
    return this._hass;
  },
  set(this: HaloPanel & { _hass?: HomeAssistant }, value: HomeAssistant) {
    this._hass = value;
    (this as unknown as { render(): void }).render();
  },
  configurable: true,
});

if (!customElements.get("halo-panel")) {
  customElements.define("halo-panel", HaloPanel);
}

// Marker for diagnosing blank panels: if the sidebar page stays empty,
// open devtools (F12) — absence of this line means the bundle never loaded
// (stale cache / failed fetch), anything after it points at render errors.
// eslint-disable-next-line no-console
console.info("[halo-panel] loaded");
