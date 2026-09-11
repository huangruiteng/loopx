import { useEffect, useMemo, useState } from "react";
import { Check, Code2, RotateCcw, ShieldCheck, Trash2 } from "lucide-react";

import {
  applyMachineConfiguration,
  applyMachineConfigurationRemoval,
  applyMachineConfigurationRollback,
  fetchMachineConfiguration,
  previewMachineConfiguration,
  previewMachineConfigurationRemoval,
  previewMachineConfigurationRollback,
  type CapabilityConfigurationCatalog,
  type MachineConfigurationInspection,
  type MachineConfigurationPreview,
  type MachineConfigurationRollbackPlan,
  type MachineConfigurationTransaction,
} from "../../data/chat";
import { projectEditableCapabilityConfiguration } from "../../data/capability-configuration";
import { CapabilityConfigurationFields } from "./capability-configuration-fields";
import { localizeCapability, localizedCapabilityFieldCopy } from "./capability-localization";
import { canEditCapability, CapabilityCatalogNavigation, CapabilityConfigurationSummary, CapabilityDetailHeader, CapabilityEditorStatus } from "./capability-workbench";
import { useWorkspaceI18n } from "./i18n";

type CapabilityDescriptor = CapabilityConfigurationCatalog["capabilities"][number];
type EditorMode = "guided" | "json";

function configurationObject(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {};
}

function currentConfiguration(
  inspection: MachineConfigurationInspection | null,
  capability: CapabilityDescriptor | undefined,
) {
  const namespace = capability?.machine_namespace;
  return namespace ? inspection?.machine_configuration?.namespaces[namespace] : undefined;
}

function completeMachineConfiguration(
  capability: CapabilityDescriptor,
  current: Record<string, unknown> | undefined,
  draft: Record<string, unknown>,
) {
  return {
    ...configurationObject(capability.default),
    ...configurationObject(current),
    ...draft,
  };
}

function validGuidedDraft(capability: CapabilityDescriptor, value: Record<string, unknown>) {
  for (const field of capability.configuration_editor.fields) {
    const item = value[field.key];
    if (field.required && (item === undefined || item === null || item === "")) return false;
  }
  if (capability.capability_id === "periodic_report" && value.enabled === true) {
    return Boolean(String(value.profile_preset ?? "").trim()
      && String(value.route_ref ?? "").trim()
      && String(value.timezone ?? "").trim());
  }
  return true;
}

function parseJsonObject(value: string) {
  try {
    const parsed: unknown = JSON.parse(value);
    return parsed && typeof parsed === "object" && !Array.isArray(parsed)
      ? parsed as Record<string, unknown>
      : null;
  } catch {
    return null;
  }
}

function shortRevision(value: string | undefined) {
  if (!value) return "—";
  if (value === "absent") return value;
  return value.replace(/^sha256:/, "").slice(0, 12);
}

export function MachineConfigurationSettings() {
  const { locale, t } = useWorkspaceI18n();
  const [inspection, setInspection] = useState<MachineConfigurationInspection | null>(null);
  const [selectedCapabilityId, setSelectedCapabilityId] = useState("");
  const [draft, setDraft] = useState<Record<string, unknown>>({});
  const [jsonDraft, setJsonDraft] = useState("{}");
  const [editorMode, setEditorMode] = useState<EditorMode>("guided");
  const [preview, setPreview] = useState<MachineConfigurationPreview | null>(null);
  const [previewOperation, setPreviewOperation] = useState<"upsert" | "remove">("upsert");
  const [transaction, setTransaction] = useState<MachineConfigurationTransaction | null>(null);
  const [rollbackPlan, setRollbackPlan] = useState<MachineConfigurationRollbackPlan | null>(null);
  const [busy, setBusy] = useState<"load" | "preview" | "apply" | "rollback-preview" | "rollback" | null>("load");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const capabilities = inspection?.capability_catalog.capabilities ?? [];
  const selectedRaw = capabilities.find(
    (capability) => capability.capability_id === selectedCapabilityId,
  ) ?? capabilities[0];
  const selected = selectedRaw ? localizeCapability(selectedRaw, locale) : undefined;
  const selectedCurrent = currentConfiguration(inspection, selected);
  const configured = Boolean(selected?.machine_namespace && selectedCurrent);
  const editorAvailable = Boolean(selected && canEditCapability(selected, "machine"));
  const parsedJsonDraft = useMemo(() => parseJsonObject(jsonDraft), [jsonDraft]);
  const desiredConfiguration = selected
    ? editorMode === "json"
      ? parsedJsonDraft
      : completeMachineConfiguration(selected, selectedCurrent, draft)
    : null;
  const editorValid = Boolean(
    selected && (editorMode === "json"
      ? parsedJsonDraft
      : validGuidedDraft(selected, desiredConfiguration ?? {})),
  );

  async function reload() {
    setInspection(await fetchMachineConfiguration());
  }

  useEffect(() => {
    let active = true;
    fetchMachineConfiguration()
      .then((next) => {
        if (!active) return;
        setInspection(next);
        setSelectedCapabilityId(next.capability_catalog.capabilities.find(
          (capability) => capability.available_scopes.includes("machine"),
        )?.capability_id ?? "");
      })
      .catch((cause: unknown) => {
        if (active) setError(cause instanceof Error ? cause.message : t("machine.loadError"));
      })
      .finally(() => {
        if (active) setBusy(null);
      });
    return () => { active = false; };
  }, [t]);

  useEffect(() => {
    if (!selected) return;
    const current = currentConfiguration(inspection, selected);
    const editable = projectEditableCapabilityConfiguration(
      selected.configuration_editor,
      current ?? selected.default,
      selected.default,
    );
    const complete = completeMachineConfiguration(selected, current, editable);
    setDraft(editable);
    setJsonDraft(JSON.stringify(complete, null, 2));
    setEditorMode(editorAvailable ? "guided" : "json");
    setPreview(null);
    setPreviewOperation("upsert");
    setRollbackPlan(null);
  }, [inspection, selectedCapabilityId, locale]);

  function changeDraft(key: string, value: boolean | number | string | string[]) {
    setDraft((current) => ({ ...current, [key]: value }));
    setPreview(null);
    setPreviewOperation("upsert");
    setError(null);
    setNotice(null);
  }

  function changeMode(mode: EditorMode) {
    if (!selected) return;
    if (mode === "json") {
      setJsonDraft(JSON.stringify(
        completeMachineConfiguration(selected, selectedCurrent, draft),
        null,
        2,
      ));
    } else if (parsedJsonDraft) {
      setDraft(projectEditableCapabilityConfiguration(
        selected.configuration_editor,
        parsedJsonDraft,
        selected.default,
      ));
    } else {
      setError(t("machine.jsonInvalid"));
      return;
    }
    setEditorMode(mode);
    setPreview(null);
    setPreviewOperation("upsert");
    setError(null);
  }

  async function createPreview() {
    if (!editorAvailable || !selected?.machine_namespace || !desiredConfiguration || !editorValid || busy) return;
    setBusy("preview");
    setError(null);
    setNotice(null);
    try {
      setPreviewOperation("upsert");
      setPreview(await previewMachineConfiguration(selected.machine_namespace, desiredConfiguration));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : t("machine.previewError"));
    } finally {
      setBusy(null);
    }
  }

  async function createRemovalPreview() {
    if (!editorAvailable || !selected?.machine_namespace || !configured || busy) return;
    setBusy("preview");
    setError(null);
    setNotice(null);
    try {
      setPreviewOperation("remove");
      setPreview(await previewMachineConfigurationRemoval(selected.machine_namespace));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : t("machine.previewError"));
    } finally {
      setBusy(null);
    }
  }

  async function applyPreview() {
    if (!editorAvailable || !selected?.machine_namespace || !preview || busy || (previewOperation === "upsert" && !desiredConfiguration)) return;
    setBusy("apply");
    setError(null);
    const operation = previewOperation;
    try {
      const result = operation === "remove"
        ? await applyMachineConfigurationRemoval(selected.machine_namespace, preview.plan_revision)
        : await applyMachineConfiguration(selected.machine_namespace, desiredConfiguration!, preview.plan_revision);
      setTransaction(result);
      setPreview(null);
      setPreviewOperation("upsert");
      setRollbackPlan(null);
      await reload();
      setNotice(result.status === "applied"
        ? t(operation === "remove" ? "machine.removed" : "machine.applied")
        : t("machine.unchanged"));
    } catch (cause) {
      setPreview(null);
      setPreviewOperation("upsert");
      setError(cause instanceof Error ? cause.message : t("machine.applyError"));
    } finally {
      setBusy(null);
    }
  }

  async function previewRollback() {
    if (!transaction?.transaction_id || busy) return;
    setBusy("rollback-preview");
    setError(null);
    try {
      setRollbackPlan(await previewMachineConfigurationRollback(transaction.transaction_id));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : t("machine.rollbackError"));
    } finally {
      setBusy(null);
    }
  }

  async function applyRollback() {
    if (!transaction?.transaction_id || !rollbackPlan || busy) return;
    setBusy("rollback");
    setError(null);
    try {
      await applyMachineConfigurationRollback(transaction.transaction_id, rollbackPlan.plan_revision);
      setTransaction(null);
      setRollbackPlan(null);
      setPreview(null);
      await reload();
      setNotice(t("machine.rolledBack"));
    } catch (cause) {
      setRollbackPlan(null);
      setError(cause instanceof Error ? cause.message : t("machine.rollbackError"));
    } finally {
      setBusy(null);
    }
  }

  if (busy === "load") {
    return <div className="personal-machine-loading" role="status">{t("common.loading")}</div>;
  }
  if (!selected) {
    return <p className="personal-capability-empty">{t("machine.capabilityEmpty")}</p>;
  }

  return (
    <section className="personal-capability-settings" data-revision={inspection?.revision}>
      <details className="personal-capability-scope-note">
        <summary><ShieldCheck aria-hidden size={17} />{t("machine.liveDefault")}</summary>
        <p>{t("machine.liveDefaultDescription")}</p>
      </details>

      <div className="personal-capability-layout">
        <CapabilityCatalogNavigation capabilities={capabilities} locale={locale} onSelect={setSelectedCapabilityId} scope="machine" selectedCapabilityId={selected.capability_id} t={t} />

        <article aria-label={selected.display_name} className="personal-capability-detail" tabIndex={0}>
          <CapabilityDetailHeader capability={selectedRaw} locale={locale}
            source={selected.available_scopes.includes("machine") ? configured ? "machine_default" : "capability_default" : undefined} />
          <CapabilityEditorStatus available={editorAvailable} t={t} description={!selected.available_scopes.includes("machine") ? t("machine.goalOnly")
              : t("machine.editorUnavailableDescription")} />

          {selected.capability_id === "periodic_report" ? (
            <section className="personal-capability-behavior-note">
              <ShieldCheck aria-hidden size={18} />
              <div><strong>{t("machine.periodicReportActivation")}</strong><p>{t("machine.periodicReportActivationDescription")}</p></div>
            </section>
          ) : null}

          {editorAvailable ? <>{editorMode === "json" || !selected.configuration_editor.fields.some((field) => field.key === "enabled" && field.input_kind === "boolean") ? <div className="personal-capability-editor-mode">
            <button onClick={() => changeMode(editorMode === "guided" ? "json" : "guided")} type="button">
              <Code2 aria-hidden size={14} />{t(editorMode === "guided" ? "machine.editJson" : "machine.backToForm")}
            </button>
          </div> : null}

          {editorMode === "guided" ? (
            <section className="personal-capability-field-summary">
              <CapabilityConfigurationFields copy={localizedCapabilityFieldCopy(locale)} disabled={Boolean(busy)} editor={selected.configuration_editor} onChange={changeDraft} value={draft}
                enabledAction={<button className="personal-capability-edit-json" onClick={() => changeMode("json")} type="button"><Code2 aria-hidden size={14} />{t("machine.editJson")}</button>} />
              {!editorValid ? <p className="personal-machine-validation" role="alert">{t("machine.requiredFields")}</p> : null}
            </section>
          ) : (
            <label className="personal-capability-json-editor" htmlFor="machine-configuration-json">
              <span>{t("machine.jsonConfiguration")}</span>
              <textarea aria-describedby="machine-configuration-json-help" disabled={Boolean(busy)} id="machine-configuration-json" onChange={(event) => { setJsonDraft(event.target.value); setPreview(null); setError(null); }} rows={12} spellCheck={false} value={jsonDraft} />
              <small id="machine-configuration-json-help">{t("machine.jsonConfigurationHelp")}</small>
              {!parsedJsonDraft ? <span className="personal-machine-validation" role="alert">{t("machine.jsonInvalid")}</span> : null}
            </label>
          )}</> : null}

          {error ? <p className="personal-machine-error" role="alert">{error}</p> : null}
          {notice ? <p className="personal-machine-notice" role="status" aria-live="polite"><Check aria-hidden size={16} />{notice}</p> : null}

          {preview ? (
            <section aria-label={t("machine.preview")} className="personal-machine-preview">
              <header><strong>{t("machine.preview")}</strong><span>{t(`machine.action.${preview.action}`)}</span></header>
              <dl>
                <div><dt>{t("machine.currentRevision")}</dt><dd title={preview.current_revision}>{shortRevision(preview.current_revision)}</dd></div>
                <div><dt>{t("machine.desiredRevision")}</dt><dd title={preview.desired_revision}>{shortRevision(preview.desired_revision)}</dd></div>
                <div><dt>{t("machine.changedNamespaces")}</dt><dd>{preview.changed_namespaces.join(", ") || t("common.none")}</dd></div>
              </dl>
              <p>{t("machine.previewLocked")}</p>
            </section>
          ) : null}

          {transaction?.rollback_available && transaction.transaction_id ? (
            <section className="personal-machine-rollback">
              <div><strong>{t("machine.rollbackAvailable")}</strong><p>{rollbackPlan ? t("machine.rollbackPreviewDescription") : t("machine.rollbackDescription")}</p></div>
              <button className="personal-secondary-action" disabled={Boolean(busy) || Boolean(rollbackPlan && !rollbackPlan.rollback_allowed)} onClick={() => void (rollbackPlan ? applyRollback() : previewRollback())} type="button">
                <RotateCcw aria-hidden size={15} />
                {busy === "rollback" || busy === "rollback-preview" ? t("common.loading") : rollbackPlan ? t("machine.confirmRollback") : t("machine.previewRollback")}
              </button>
            </section>
          ) : null}

          {editorAvailable ? <footer className="personal-capability-actions">
            {configured ? <button className="is-danger" disabled={Boolean(busy)} onClick={() => void createRemovalPreview()} type="button"><Trash2 aria-hidden size={15} />{t("machine.previewRemoval")}</button> : null}
            <button disabled={Boolean(busy) || !editorValid} onClick={() => void createPreview()} type="button">{busy === "preview" ? t("common.loading") : t("machine.previewChanges")}</button>
            <button className="is-primary" disabled={Boolean(busy) || !preview} onClick={() => void applyPreview()} type="button">{busy === "apply" ? t("common.loading") : t("machine.applyPreview")}</button>
          </footer> : null}
          {selected.available_scopes.includes("machine") ? <CapabilityConfigurationSummary key={selected.capability_id}
            values={[{ label: t("machine.currentValue"), value: selectedCurrent }, { label: t("capabilities.defaultValue"), value: selected.default }]}
            t={t}
          /> : null}
        </article>
      </div>
    </section>
  );
}
