// Minimal Home Assistant frontend types needed by the HALO panel.
// Kept local (instead of pulling the full HA frontend types) on purpose:
// the panel only reads states and calls services.

export interface HassEntity {
  entity_id: string;
  state: string;
  attributes: Record<string, unknown>;
}

export interface HomeAssistant {
  states: Record<string, HassEntity>;
  callService(
    domain: string,
    service: string,
    data?: Record<string, unknown>
  ): Promise<unknown>;
  callWS<T>(message: Record<string, unknown>): Promise<T>;
}
