import { createContext } from "react";
import type { WorkspaceLocale, WorkspaceTranslate } from "./i18n";

export type WorkspaceI18nValue = {
  locale: WorkspaceLocale;
  setLocale: (locale: WorkspaceLocale) => void;
  t: WorkspaceTranslate;
};

export const WorkspaceI18nContext = createContext<WorkspaceI18nValue | null>(null);
