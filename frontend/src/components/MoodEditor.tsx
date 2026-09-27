import { useForm } from "@tanstack/react-form";
import { useState } from "react";
import { toast } from "sonner";
import type { HomeAssistant } from "../ha-types";
import {
  blankMood,
  deleteMood,
  saveMood,
  suggestTracked,
  wsError,
  type MoodConfig,
} from "../config";
import {
  Button,
  Field,
  Input,
  Select,
  Switch,
} from "./ui";

interface MoodEditorProps {
  hass: HomeAssistant;
  areaKey: string;
  mood: string;
  isNew: boolean;
  initial: MoodConfig;
  onSaved: (mood: string) => void;
  onDeleted: () => void;
}

interface PresetRow {
  name: string;
  action: string;
  kind: "scene" | "script";
  verify: "auto" | "off" | "snapshot" | "scene";
  sceneId: string;
}

const ID_RE = /^[A-Za-z0-9_]+$/;

function kindOfAction(text: string): "scene" | "script" | null {
  const t = text.trim();
  if (t.startsWith("scene.")) return "scene";
  if (t.startsWith("script.")) return "script";
  return null;
}

function fullIdError(
  presetName: string,
  action: string,
  kind: "scene" | "script"
): string | undefined {
  const text = action.trim();
  const want = kind === "scene" ? "scene.x" : "script.y";
  if (text === "") {
    // Fully blank rows are dropped; a named preset still needs its id.
    return presetName.trim() === ""
      ? undefined
      : `Preset '${presetName}' needs a full id like ${want}.`;
  }
  const prefixed = kindOfAction(text);
  if (prefixed && prefixed !== kind) {
    return `Preset '${presetName || "unnamed"}' is set to ${kind}, but the id looks like ${prefixed}.`;
  }
  const body = text.includes(".") ? text.split(".", 2)[1] : "";
  const ok =
    prefixed === kind &&
    (kind === "scene" ? text.startsWith("scene.") : text.startsWith("script.")) &&
    ID_RE.test(body);
  return ok
    ? undefined
    : `Preset '${presetName || "unnamed"}' needs a full id like ${want}.`;
}

function toRows(initial: MoodConfig): PresetRow[] {
  const rows = Object.entries(initial.presets ?? {}).map(([name, action]) => {
    const mode = initial.verify?.[name];
    return {
      name,
      action,
      kind: kindOfAction(action) ?? "scene",
      verify:
        mode === "off" || mode === "snapshot" ? mode : mode === "scene" ? "scene" : "auto",
      sceneId: mode && mode.startsWith("scene.") ? mode : "",
    } as PresetRow;
  });
  return rows.length > 0
    ? rows
    : [{ name: "", action: "", kind: "scene", verify: "auto", sceneId: "" }];
}

function fieldError(field: {
  state: { meta: { errorMap: Record<string, unknown> } };
}): string | undefined {
  const m = field.state.meta.errorMap;
  for (const key of ["onChange", "onBlur", "onMount", "onSubmit"] as const) {
    const v = m[key];
    if (typeof v === "string" && v) return v;
    if (Array.isArray(v)) {
      const first = v.find((x) => typeof x === "string" && x) as
        | string
        | undefined;
      if (first) return first;
    }
  }
  return undefined;
}

/**
 * Editor form for one mood's preset→action mapping plus verify tuning,
 * built on TanStack Form: every input validates as you type, cross-field
 * rules run on submit, and nothing hand-rolled tracks error state.
 */
export function MoodEditor({
  hass,
  areaKey,
  mood,
  isNew,
  initial,
  onSaved,
  onDeleted,
}: MoodEditorProps) {
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [suggestBusy, setSuggestBusy] = useState(false);
  const [suggestNote, setSuggestNote] = useState<string | null>(null);

  const form = useForm({
    defaultValues: {
      moodName: isNew ? "" : mood,
      presets: toRows(initial),
      defaultPreset: initial.default_preset,
      tracked: initial.tracked_entities.join(", "),
      transition: initial.transition,
      settle: initial.settle,
      debounce: initial.debounce,
      tolerance: initial.tolerance,
      ignoreAttrs: initial.ignore_attrs.join(", "),
      ignoreUnavailable: initial.ignore_unavailable,
      postAction: initial.post_action,
    },
    validators: {
      onSubmit: ({ value }) => {
        const names = value.presets
          .map((p) => p.name.trim())
          .filter((n) => n !== "");
        if (new Set(names).size !== names.length) {
          return "Two presets share a name — names must be unique.";
        }
        if (value.defaultPreset && !names.includes(value.defaultPreset)) {
          return "Default preset must be one of the presets above.";
        }
        return undefined;
      },
    },
    onSubmit: async ({ value }) => {
      const presets: Record<string, string> = {};
      const verify: Record<string, string> = {};
      for (const row of value.presets) {
        const name = row.name.trim();
        if (name === "") continue;
        presets[name] = row.action.trim();
        if (row.verify === "off" || row.verify === "snapshot") {
          verify[name] = row.verify;
        } else if (row.verify === "scene") {
          verify[name] = row.sceneId.trim();
        }
      }
      const csv = (v: string) =>
        v
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean);
      try {
        const res = await saveMood(hass, areaKey, value.moodName.trim() || mood, {
          presets,
          verify,
          default_preset: value.defaultPreset,
          tracked_entities: csv(value.tracked),
          transition: Number(value.transition),
          settle: Number(value.settle),
          debounce: Number(value.debounce),
          tolerance: Number(value.tolerance),
          ignore_attrs: csv(value.ignoreAttrs),
          ignore_unavailable: value.ignoreUnavailable,
          post_action: value.postAction.trim(),
        });
        if (res.missing_actions.length > 0) {
          toast.warning(
            `Saved — not found yet: ${res.missing_actions.join(", ")}.`
          );
        } else {
          toast.success(`Mood “${value.moodName.trim() || mood}” saved.`);
        }
        onSaved(value.moodName.trim() || mood);
      } catch (err) {
        toast.error(wsError(err));
      }
    },
  });

  const autofill = async () => {
    const actions = form.state.values.presets
      .map((p) => p.action.trim())
      .filter((a) => a !== "");
    if (actions.length === 0) {
      setSuggestNote("Add a scene or script action first.");
      return;
    }
    setSuggestBusy(true);
    setSuggestNote(null);
    try {
      const entities = await suggestTracked(hass, areaKey, actions);
      if (entities.length === 0) {
        setSuggestNote("No entities found in those scenes.");
      } else {
        form.setFieldValue("tracked", entities.join(", "));
        setSuggestNote(
          `${entities.length} ${entities.length === 1 ? "entity" : "entities"} filled — edit or clear freely.`
        );
      }
    } catch (err) {
      setSuggestNote(wsError(err));
    } finally {
      setSuggestBusy(false);
    }
  };

  const remove = async () => {
    if (!confirmDelete) {
      setConfirmDelete(true);
      return;
    }
    try {
      await deleteMood(hass, areaKey, mood);
      toast.success(`Mood “${mood}” deleted.`);
      onDeleted();
    } catch (err) {
      toast.error(wsError(err));
    }
  };

  return (
    <div>
      {isNew && (
        <form.Field
          name="moodName"
          validators={{
            onChange: ({ value }) =>
              !value.trim() ? "Give the mood a name first." : undefined,
          }}
        >
          {(field) => {
            const err = fieldError(field);
            return (
              <Field label="Mood name">
                <Input
                  aria-label="New mood name"
                  placeholder="e.g. party"
                  value={field.state.value}
                  aria-invalid={!!err}
                  onChange={(e) => field.handleChange(e.target.value)}
                  onBlur={field.handleBlur}
                />
                {err && (
                  <p className="form-field-error" role="alert">
                    {err}
                  </p>
                )}
              </Field>
            );
          }}
        </form.Field>
      )}

      <div className="section-head">
        <div>
          <h4 className="section-title">Presets</h4>
          <p className="section-sub">
            Each preset runs one scene or script when requested. Automatic
            verification checks scenes against themselves and trusts scripts.
          </p>
        </div>
        <form.Field name="presets" mode="array">
          {(arrayField) => (
            <Button
              variant="outline"
              size="sm"
              onClick={() =>
                arrayField.pushValue({
                  name: "",
                  action: "",
                  kind: "scene",
                  verify: "auto",
                  sceneId: "",
                })
              }
            >
              Add preset
            </Button>
          )}
        </form.Field>
      </div>

      <form.Field name="presets" mode="array">
        {(arrayField) => (
          <div className="preset-list">
            {arrayField.state.value.map((_, i) => (
              // Per-row subscription: array fields only re-render on
              // structural ops, so every computed value here must come
              // from this live row slice, never the outer map closure.
              <form.Subscribe
                key={i}
                selector={(s) => s.values.presets[i]}
              >
                {(row) => {
                  if (!row) return null;
                  const kind = kindOfAction(row.action) ?? row.kind;
                  const shownVerify =
                    row.verify === "scene" &&
                    row.sceneId === row.action.trim() &&
                    row.action.trim() !== ""
                      ? "__same"
                      : row.verify;
                  return (
                <div key={i} className="preset-block">
                  <div className="row preset-row">
                    <form.Field name={`presets[${i}].name`}>
                      {(field) => (
                        <Input
                          aria-label="Preset name"
                          placeholder="preset"
                          value={field.state.value}
                          onChange={(e) => field.handleChange(e.target.value)}
                          onBlur={field.handleBlur}
                        />
                      )}
                    </form.Field>
                    <div
                      className="seg seg-inline"
                      role="group"
                      aria-label={`Action kind for ${row.name || "preset"}`}
                    >
                      {(["scene", "script"] as const).map((k) => (
                        <button
                          key={k}
                          type="button"
                          className={[
                            "seg-item",
                            kind === k ? "active" : "",
                          ]
                            .filter(Boolean)
                            .join(" ")}
                          aria-pressed={kind === k}
                          onClick={() => {
                            const current =
                              arrayField.state.value[i].action.trim();
                            const bare = current.replace(
                              /^(scene|script)\./,
                              ""
                            );
                            const hadPrefix = bare !== current;
                            arrayField.replaceValue(i, {
                              ...arrayField.state.value[i],
                              kind: k,
                              action: hadPrefix ? `${k}.${bare}` : current,
                            });
                          }}
                        >
                          {k === "scene" ? "Scene" : "Script"}
                        </button>
                      ))}
                    </div>
                    <form.Field
                      name={`presets[${i}].action`}
                      validators={{
                        onChange: ({ value, fieldApi }) => {
                          const sibling = fieldApi.form.getFieldValue(
                            `presets[${i}].name`
                          ) as string;
                          const k =
                            kindOfAction(value) ??
                            (arrayField.state.value[i]
                              ?.kind as "scene" | "script") ??
                            "scene";
                          return fullIdError(sibling ?? "", value, k);
                        },
                      }}
                    >
                      {(field) => {
                        const err = fieldError(field);
                        return (
                          <Input
                            aria-label="Action entity"
                            placeholder={
                              kind === "scene" ? "scene.x" : "script.y"
                            }
                            mono
                            value={field.state.value}
                            aria-invalid={!!err}
                            onChange={(e) =>
                              field.handleChange(e.target.value)
                            }
                            onBlur={field.handleBlur}
                          />
                        );
                      }}
                    </form.Field>
                    <Button
                      variant="ghost"
                      size="sm"
                      aria-label={`Remove preset ${row.name || i}`}
                      onClick={() => arrayField.removeValue(i)}
                    >
                      ✕
                    </Button>
                  </div>
                  <form.Field name={`presets[${i}].action`}>
                    {(afield) => {
                      const aerr = fieldError(afield);
                      return aerr ? (
                        <p className="form-field-error" role="alert">
                          {aerr}
                        </p>
                      ) : null;
                    }}
                  </form.Field>
                  <div className="row verify-row">
                    <form.Field name={`presets[${i}].verify`}>
                      {(vfield) => (
                        <Select
                          aria-label={`Verify ${row.name || "preset"}`}
                          value={shownVerify}
                          onChange={(e) => {
                            const v = e.target.value;
                            // TEMP-DEBUG
                            console.log("VERIFYCHANGE", v);
                            const cur = arrayField.state.value[i];
                            if (v === "__same") {
                              arrayField.replaceValue(i, {
                                ...cur,
                                verify: "scene",
                                sceneId: cur.action.trim(),
                              });
                            } else {
                              vfield.handleChange(
                                v as "auto" | "off" | "snapshot" | "scene"
                              );
                            }
                          }}
                        >
                          <option value="auto">Recommended</option>
                          {kind === "script" ? (
                            <option value="off">Trust apply</option>
                          ) : (
                            <option value="__same">Same scene</option>
                          )}
                          <option value="snapshot">Snapshot on apply</option>
                          <option value="scene">Reference scene</option>
                        </Select>
                      )}
                    </form.Field>
                    {row.verify === "scene" && (
                      <form.Field
                        name={`presets[${i}].sceneId`}
                        validators={{
                          onChange: ({ value }) => {
                            const id = value.trim();
                            if (id === "" || id === "scene.") {
                              return "Reference scene needs an id like scene.x.";
                            }
                            if (!/^scene\.[A-Za-z0-9_]+$/.test(id)) {
                              return "Reference scene must look like scene.x.";
                            }
                            return undefined;
                          },
                        }}
                      >
                        {(sfield) => {
                          const serr = fieldError(sfield);
                          return (
                            <Input
                              aria-label="Reference scene"
                              placeholder="scene.x"
                              mono
                              value={sfield.state.value}
                              aria-invalid={!!serr}
                              onChange={(e) =>
                                sfield.handleChange(e.target.value)
                              }
                              onBlur={sfield.handleBlur}
                            />
                          );
                        }}
                      </form.Field>
                    )}
                  </div>
                </div>
              );
            }}
          </form.Subscribe>
        ))}
        </div>
      )}
    </form.Field>

      <Field
        label="Default preset"
        hint="Used when a mood is requested without a preset."
        className="default-preset"
      >
        <form.Subscribe
          selector={(s) => s.values.presets.map((p) => p.name)}
        >
          {(names) => {
            const presetNames = names.filter((n) => n.trim() !== "");
            return (
              <form.Field name="defaultPreset">
                {(field) => (
                  <Select
                    aria-label="Default preset"
                    value={
                      presetNames.includes(field.state.value)
                        ? field.state.value
                        : ""
                    }
                    onChange={(e) => field.handleChange(e.target.value)}
                  >
                    <option value="" disabled>
                      pick…
                    </option>
                    {presetNames.map((n) => (
                      <option key={n} value={n}>
                        {n}
                      </option>
                    ))}
                  </Select>
                )}
              </form.Field>
            );
          }}
        </form.Subscribe>
      </Field>

      <h4 className="section-title">Verification</h4>
      <p className="section-sub">
        How strictly HALO confirms the lights followed the request.
      </p>
      <Field
        label="Tracked entities"
        hint="Leave empty to detect automatically, or use Autofill to draft the detected set for editing."
      >
        <div className="row tracked-row">
          <form.Field name="tracked">
            {(field) => (
              <Input
                aria-label="Tracked entities"
                placeholder="light.a, light.b"
                mono
                className="grow"
                value={field.state.value}
                onChange={(e) => field.handleChange(e.target.value)}
                onBlur={field.handleBlur}
              />
            )}
          </form.Field>
          <Button
            variant="ghost"
            size="sm"
            title="Autofill from scenes"
            disabled={suggestBusy}
            onClick={() => void autofill()}
          >
            {suggestBusy ? "Detecting…" : "Autofill"}
          </Button>
        </div>
        {suggestNote && <span className="muted">{suggestNote}</span>}
      </Field>

      <Field label="Timing">
        <div className="row">
          {(
            [
              ["transition", "Transition", "s"],
              ["settle", "Settle", "s"],
              ["debounce", "Debounce", "s"],
              ["tolerance", "Tolerance", "±"],
            ] as const
          ).map(([key, label, unit]) => (
            <form.Field
              key={key}
              name={key}
              validators={{
                onChange: ({ value }) =>
                  Number(value) < 0 ? "Must be zero or more." : undefined,
              }}
            >
              {(field) => (
                <label className="tuning-field">
                  <span>
                    {label} <span className="unit">({unit})</span>
                  </span>
                  <Input
                    type="number"
                    min={0}
                    step="any"
                    aria-label={label}
                    value={field.state.value as number}
                    onChange={(e) => field.handleChange(Number(e.target.value))}
                    onBlur={field.handleBlur}
                  />
                </label>
              )}
            </form.Field>
          ))}
        </div>
      </Field>

      <Field
        label="Ignored attributes"
        hint="Skipped when comparing live states to the expected scene."
      >
        <form.Field name="ignoreAttrs">
          {(field) => (
            <Input
              aria-label="Ignored attributes"
              placeholder="effect, color_temp_kelvin"
              mono
              value={field.state.value}
              onChange={(e) => field.handleChange(e.target.value)}
              onBlur={field.handleBlur}
            />
          )}
        </form.Field>
      </Field>

      <Field
        label="Post script"
        hint="Optional script that runs once when this mood becomes active."
      >
        <form.Field
          name="postAction"
          validators={{
            onChange: ({ value }) =>
              value.trim() !== "" &&
              !/^script\.[A-Za-z0-9_]+$/.test(value.trim())
                ? "Post script must look like script.y."
                : undefined,
          }}
        >
          {(field) => {
            const err = fieldError(field);
            return (
              <>
                <Input
                  aria-label="Post script"
                  placeholder="script.y"
                  mono
                  value={field.state.value}
                  aria-invalid={!!err}
                  onChange={(e) => field.handleChange(e.target.value)}
                  onBlur={field.handleBlur}
                />
                {err && (
                  <p className="form-field-error" role="alert">
                    {err}
                  </p>
                )}
              </>
            );
          }}
        </form.Field>
      </Field>

      <div className="inline-check">
        <form.Field name="ignoreUnavailable">
          {(field) => (
            <Switch
              checked={!!field.state.value}
              onCheckedChange={(v) => field.handleChange(v)}
              label="Ignore unavailable entities"
            />
          )}
        </form.Field>
        <span>Ignore unavailable entities</span>
      </div>

      <div className="row foot">
        <form.Subscribe
          selector={(s) => ({ submitting: s.isSubmitting })}
        >
          {({ submitting }) => (
            <Button
              variant="default"
              disabled={submitting}
              onClick={() => void form.handleSubmit()}
            >
              {submitting ? "Saving…" : "Save"}
            </Button>
          )}
        </form.Subscribe>
        {!isNew && (
          <Button
            variant="destructive"
            onClick={() => void remove()}
          >
            {confirmDelete ? "Confirm delete" : "Delete"}
          </Button>
        )}
      </div>
    </div>
  );
}
