import { useState } from "react";
import { ArrowLeft, Check, Languages, Palette, ServerCog, Settings2, SlidersHorizontal } from "lucide-react";

import type { WorkspaceLocale } from "./i18n";
import { useWorkspaceI18n } from "./i18n";
import { LarkSettingsPage } from "./lark-settings-page";
import { GoalCapabilitySettings } from "./goal-capability-settings";
import { MachineConfigurationSettings } from "./machine-configuration-settings";
import type { WorkspaceGoal } from "./personal-workspace-model";
import type { WorkspaceTheme } from "./workspace-theme";

type WorkspaceSettingsTab = "machine" | "capabilities" | "lark" | "appearance" | "language";

const tabIcons: Record<WorkspaceSettingsTab, typeof Settings2> = {
  appearance: Palette,
  capabilities: SlidersHorizontal,
  language: Languages,
  lark: Settings2,
  machine: ServerCog,
};

export function WorkspaceSettingsPage({
  focusGoalConnection = false,
  goals,
  initialGoalId,
  initialTab = "lark",
  onChanged,
  onClose,
  onThemeChange,
  theme,
}: {
  focusGoalConnection?: boolean;
  goals: WorkspaceGoal[];
  initialGoalId?: string | null;
  initialTab?: WorkspaceSettingsTab;
  onChanged: () => void;
  onClose: () => void;
  onThemeChange: (theme: WorkspaceTheme) => void;
  theme: WorkspaceTheme;
}) {
  const { locale, setLocale, t } = useWorkspaceI18n();
  const [tab, setTab] = useState<WorkspaceSettingsTab>(initialTab);
  const tabs: Array<{ key: WorkspaceSettingsTab; label: string }> = [
    ...(initialGoalId ? [{ key: "capabilities" as const, label: t("capabilities.title") }] : []),
    { key: "machine", label: t("machine.title") },
    { key: "lark", label: "Lark" },
    { key: "appearance", label: t("settings.appearance") },
    { key: "language", label: t("settings.language") },
  ];
  const localeOptions: Array<{ label: string; value: WorkspaceLocale }> = [
    {
      label: t("settings.languageEnglish"),
      value: "en",
    },
    {
      label: t("settings.languageSimplifiedChinese"),
      value: "zh-CN",
    },
  ];
  const headings: Record<WorkspaceSettingsTab, { title: string }> = {
    appearance: {
      title: t("settings.appearance"),
    },
    capabilities: {
      title: t("capabilities.title"),
    },
    language: {
      title: t("settings.language"),
    },
    lark: {
      title: "Lark",
    },
    machine: {
      title: t("machine.title"),
    },
  };
  const heading = headings[tab];

  return (
    <section aria-label={t("settings.title")} className="personal-settings-page" data-pw-theme={theme}>
      <aside className="personal-settings-sidebar">
        <button className="personal-settings-back" onClick={onClose} type="button">
          <ArrowLeft size={17} />
          <span>{t("settings.back")}</span>
        </button>
        <div className="personal-settings-title">
          <small>{t("settings.eyebrow")}</small>
          <strong>{t("settings.title")}</strong>
        </div>
        <nav aria-label={t("settings.categories")} className="personal-settings-tabs">
          {tabs.map((item) => {
            const Icon = tabIcons[item.key];
            return (
              <button aria-current={tab === item.key ? "page" : undefined} key={item.key} onClick={() => setTab(item.key)} type="button">
                <Icon size={17} />
                <span>
                  <strong>{item.label}</strong>
                </span>
              </button>
            );
          })}
        </nav>
      </aside>

      <main className="personal-settings-body">
        <header className="personal-settings-header">
          <div>
            <h1>{heading.title}</h1>
          </div>
        </header>
        {tab === "lark" ? (
          <LarkSettingsPage
            embedded
            focusGoalConnection={focusGoalConnection}
            goals={goals}
            initialGoalId={initialGoalId}
            onChanged={onChanged}
            onClose={onClose}
          />
        ) : null}

        {tab === "machine" ? <MachineConfigurationSettings /> : null}
        {tab === "capabilities" ? <GoalCapabilitySettings goalId={initialGoalId} /> : null}

        {tab === "appearance" ? (
          <section className="personal-detail-card personal-appearance-settings">
            <small>{t("settings.workspaceDisplay")}</small>
            <h3>{t("settings.appearance")}</h3>
            <div className="personal-settings-choice-group" role="radiogroup" aria-label={t("settings.workspaceTheme")}>
              <button aria-checked={theme === "loopx"} onClick={() => onThemeChange("loopx")} role="radio" type="button">
                <span className="personal-settings-theme-swatch is-loopx" />
                <strong>{t("settings.themeLoopx")}</strong>
              </button>
              <button aria-checked={theme === "paper"} onClick={() => onThemeChange("paper")} role="radio" type="button">
                <span className="personal-settings-theme-swatch is-paper" />
                <strong>{t("settings.themeDefault")}</strong>
              </button>
              <button aria-checked={theme === "brutal"} onClick={() => onThemeChange("brutal")} role="radio" type="button">
                <span className="personal-settings-theme-swatch is-brutal" />
                <strong>{t("settings.themeHighContrast")}</strong>
              </button>
            </div>
          </section>
        ) : null}

        {tab === "language" ? (
          <section className="personal-settings-card">
            <header>
              <span className="personal-settings-icon"><Languages size={18} /></span>
              <div>
                <h2>{t("settings.language")}</h2>
              </div>
            </header>
            <div aria-label={t("settings.language")} className="personal-language-options" role="radiogroup">
              {localeOptions.map((option) => (
                <button
                  aria-checked={locale === option.value}
                  className={locale === option.value ? "is-selected" : ""}
                  key={option.value}
                  onClick={() => setLocale(option.value)}
                  role="radio"
                  type="button"
                >
                  <span>
                    <strong>{option.label}</strong>
                  </span>
                  {locale === option.value ? <Check aria-hidden size={17} /> : null}
                </button>
              ))}
            </div>
          </section>
        ) : null}
      </main>
    </section>
  );
}
