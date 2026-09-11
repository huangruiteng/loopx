import { AlertTriangle, ShieldCheck, SlidersHorizontal } from "lucide-react";

import type { CapabilityConfigurationCatalog } from "../../data/chat";
import { useWorkspaceI18n, type WorkspaceLocale, type WorkspaceTranslate } from "./i18n";
import { localizeCapability, localizedCapabilityFieldCopy } from "./capability-localization";

type CapabilityDescriptor = CapabilityConfigurationCatalog["capabilities"][number];

export function canEditCapability(capability: CapabilityDescriptor, scope: "goal" | "machine") {
  return capability.available_scopes.includes(scope)
    && (scope !== "machine" || Boolean(capability.machine_namespace))
    && capability.configuration_editor.editable
    && capability.configuration_editor.writable_scopes.includes(scope);
}

export function CapabilityConfigurationSummary({ values, t }: Readonly<{
  values: ReadonlyArray<{ label: string; value: Record<string, unknown> | undefined }>;
  t: WorkspaceTranslate;
}>) {
  return <details className="personal-capability-raw-values">
    <summary>{t("capabilities.rawJson")}</summary>
    <div className="personal-capability-value-grid">
      {values.map(({ label, value }) => <section key={label}>
        <strong>{label}</strong><pre>{value ? JSON.stringify(value, null, 2) : "—"}</pre>
      </section>)}
    </div>
  </details>;
}

function CapabilityEffectiveSource({ source, t }: Readonly<{
  source?: NonNullable<CapabilityDescriptor["effective_configuration"]>["source"];
  t: WorkspaceTranslate;
}>) {
  return source ? <p className="personal-capability-effective-source">
      <ShieldCheck aria-hidden size={15} />
      <span><strong>{t("capabilities.effectiveSource")}</strong>{t(`capabilities.source.${source}`)}</span>
    </p> : null;
}

export function CapabilityEditorStatus({ available, description, t }: Readonly<{
  available: boolean;
  description: string;
  t: WorkspaceTranslate;
}>) {
  if (available) return null;
  return <section className="personal-capability-editor-status is-read-only">
    <AlertTriangle aria-hidden size={18} />
    <div><strong>{t("capabilities.readOnly")}</strong><p>{description}</p></div>
  </section>;
}

function capabilityPresentationTier(capability: CapabilityDescriptor) {
  if (capability.availability?.includes("experimental")) return 4;
  if (capability.capability_id === "multi_subagent") return 3;
  if (capability.configuration_editor.writable_scopes.length === 0) return 2;
  if (capability.availability === "supported_explicit_opt_in") return 2;
  if (capability.availability === "supported_explicit_override") return 0;
  return 1;
}

export function orderCapabilitiesForPresentation(
  capabilities: CapabilityDescriptor[],
  locale: WorkspaceLocale,
) {
  return [...capabilities].sort((left, right) => {
    const tierDifference = capabilityPresentationTier(left) - capabilityPresentationTier(right);
    if (tierDifference !== 0) return tierDifference;
    const localizedLeft = localizeCapability(left, locale);
    const localizedRight = localizeCapability(right, locale);
    return localizedLeft.display_name.localeCompare(localizedRight.display_name, locale)
      || left.capability_id.localeCompare(right.capability_id);
  });
}

export function CapabilityCatalogNavigation({
  capabilities,
  locale,
  onSelect,
  scope,
  selectedCapabilityId,
  t,
}: Readonly<{
  capabilities: CapabilityDescriptor[];
  locale: WorkspaceLocale;
  onSelect: (capabilityId: string) => void;
  scope: "goal" | "machine";
  selectedCapabilityId: string;
  t: WorkspaceTranslate;
}>) {
  return (
    <nav aria-label={t(scope === "goal" ? "capabilities.catalog" : "machine.capabilityCatalog")} className="personal-capability-list" tabIndex={0}>
      {orderCapabilitiesForPresentation(capabilities, locale).map((rawCapability) => {
        const capability = localizeCapability(rawCapability, locale);
        return (
          <button
            aria-current={selectedCapabilityId === capability.capability_id ? "page" : undefined}
            key={capability.capability_id}
            onClick={() => onSelect(capability.capability_id)}
            type="button"
          >
            <span>
              <strong>{capability.display_name}</strong>
            </span>
            <em>{t(capability.available_scopes.includes(scope)
              ? scope === "goal" ? "capabilities.goalScope" : "capabilities.machineScope"
              : scope === "machine" ? "capabilities.goalScope" : "capabilities.machineScope")}</em>
          </button>
        );
      })}
    </nav>
  );
}

export function CapabilityDetailHeader({ capability, locale, source }: Readonly<{
  capability: CapabilityDescriptor;
  locale: WorkspaceLocale;
  source?: NonNullable<CapabilityDescriptor["effective_configuration"]>["source"];
}>) {
  const { t } = useWorkspaceI18n();
  const localized = localizeCapability(capability, locale);
  return (
    <header>
      <span className="personal-settings-icon"><SlidersHorizontal aria-hidden size={18} /></span>
      <div>
        <div className="personal-capability-heading-row">
          <h2>{localized.display_name}</h2>
          <CapabilityEffectiveSource source={source} t={t} />
        </div>
        <details className="personal-capability-help" key={capability.capability_id}>
          <summary>{locale === "zh-CN" ? "配置说明" : "Configuration help"}</summary>
          <p>{localized.description}</p>
          <dl>{capability.configuration_editor.fields.map((field) => {
            const copy = localizedCapabilityFieldCopy(locale)[field.key];
            const description = copy?.description ?? field.description;
            return description ? <div key={field.key}><dt>{copy?.label ?? field.label}</dt><dd>{description}</dd></div> : null;
          })}</dl>
        </details>
      </div>
    </header>
  );
}
