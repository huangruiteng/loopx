import { useCallback, useEffect, useState } from "react";
import { Check, KeyRound, ShieldCheck, Trash2 } from "lucide-react";

import {
  fetchOperatorCredential,
  writeOperatorCredential,
  type OperatorCredential,
} from "../../data/chat";
import { type WorkspaceTranslate, useWorkspaceI18n } from "./i18n";

function localizeStatus(status: OperatorCredential["status"], t: WorkspaceTranslate) {
  if (status === "invalid") return t("machine.credentialInvalid");
  return t(status === "configured" ? "machine.credentialConfigured" : "machine.credentialAbsent");
}

function localizeSource(source: string, t: WorkspaceTranslate) {
  if (source === "machine_store") return t("machine.credentialSourceMachine");
  if (source === "service_environment") return t("machine.credentialSourceEnvironment");
  return t("machine.credentialSourceUnset");
}

/**
 * The one place a person stores the operator model credential.
 *
 * The key is write-only end to end: this form submits one, and every readback
 * it renders is the redacted projection, so the browser can configure a
 * credential it is never able to display again. The endpoint is not a secret
 * and reads back as itself.
 */
export function OperatorCredentialSettings() {
  const { t } = useWorkspaceI18n();
  const [credential, setCredential] = useState<OperatorCredential | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [busy, setBusy] = useState<"" | "load" | "store">("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setBusy("load");
    try {
      const loaded = await fetchOperatorCredential();
      setCredential(loaded);
      // Only a non-secret field is prefilled; the key never round-trips.
      setBaseUrl(String(loaded.base_url.value ?? ""));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : t("machine.credentialError"));
    } finally {
      setBusy("");
    }
  }, [t]);

  useEffect(() => {
    void reload();
  }, [reload]);

  async function submit(update: Parameters<typeof writeOperatorCredential>[0], done: string) {
    setBusy("store");
    setError(null);
    setNotice(null);
    try {
      const stored = await writeOperatorCredential(update);
      setCredential(stored);
      setBaseUrl(String(stored.base_url.value ?? ""));
      setApiKey("");
      setNotice(done);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : t("machine.credentialError"));
    } finally {
      setBusy("");
    }
  }

  if (!credential && busy === "load") {
    return <div className="personal-machine-loading" role="status">{t("common.loading")}</div>;
  }

  const keyLabel = credential
    ? `${localizeStatus(credential.provider_key.configured ? "configured" : "absent", t)} · ${localizeSource(credential.provider_key.source, t)}`
    : "";
  const urlLabel = credential
    ? `${credential.base_url.value ?? t("machine.credentialAbsent")} · ${localizeSource(credential.base_url.source, t)}`
    : "";

  return (
    <section className="personal-operator-credential" data-testid="operator-credential-settings">
      <header>
        <KeyRound aria-hidden size={17} />
        <div>
          <strong>{t("machine.credentialTitle")}</strong>
          <p>{t("machine.credentialDescription")}</p>
        </div>
        <span className="personal-operator-credential-status">
          {credential ? localizeStatus(credential.status, t) : t("common.loading")}
        </span>
      </header>

      {credential ? (
        <dl className="personal-operator-credential-readback">
          <div>
            <dt>{t("machine.credentialApiKey")}</dt>
            <dd>{keyLabel}</dd>
          </div>
          <div>
            <dt>{t("machine.credentialFingerprint")}</dt>
            <dd><code>{credential.provider_key.fingerprint ?? t("common.none")}</code></dd>
          </div>
          <div>
            <dt>{t("machine.credentialBaseUrl")}</dt>
            <dd>{urlLabel}</dd>
          </div>
        </dl>
      ) : null}

      {credential?.status === "invalid" && credential.repair ? (
        <p className="personal-machine-error" role="alert">{credential.repair}</p>
      ) : null}

      <label htmlFor="operator-credential-api-key">
        <span>{t("machine.credentialApiKey")}</span>
        <input
          autoComplete="off"
          disabled={Boolean(busy)}
          id="operator-credential-api-key"
          onChange={(event) => setApiKey(event.target.value)}
          placeholder={t("machine.credentialApiKeyPlaceholder")}
          type="password"
          value={apiKey}
        />
      </label>

      <label htmlFor="operator-credential-base-url">
        <span>{t("machine.credentialBaseUrl")}</span>
        <input
          autoComplete="off"
          disabled={Boolean(busy)}
          id="operator-credential-base-url"
          onChange={(event) => setBaseUrl(event.target.value)}
          placeholder={t("machine.credentialBaseUrlPlaceholder")}
          type="text"
          value={baseUrl}
        />
      </label>

      {error ? <p className="personal-machine-error" role="alert">{error}</p> : null}
      {notice ? <p className="personal-machine-notice" role="status" aria-live="polite"><Check aria-hidden size={16} />{notice}</p> : null}

      {/* Not `personal-capability-actions`: the browser smoke treats that class
          as the capability editor's own action row, and this panel renders on
          the same page. */}
      <footer className="personal-operator-credential-actions">
        <button
          className="is-primary"
          disabled={Boolean(busy) || (!apiKey.trim() && !baseUrl.trim())}
          onClick={() => void submit(
            {
              ...(apiKey.trim() ? { provider_key: apiKey } : {}),
              ...(baseUrl.trim() ? { base_url: baseUrl } : {}),
            },
            t("machine.credentialStored"),
          )}
          type="button"
        >
          {busy === "store" ? t("common.loading") : t("machine.credentialStore")}
        </button>
        <button
          disabled={Boolean(busy) || credential?.provider_key.configured !== true}
          onClick={() => void submit({ clear_provider_key: true }, t("machine.credentialCleared"))}
          type="button"
        >
          <Trash2 aria-hidden size={15} />{t("machine.credentialClearKey")}
        </button>
        <button
          disabled={Boolean(busy) || credential?.base_url.configured !== true}
          onClick={() => void submit({ clear_base_url: true }, t("machine.credentialCleared"))}
          type="button"
        >
          <Trash2 aria-hidden size={15} />{t("machine.credentialClearUrl")}
        </button>
      </footer>

      <details className="personal-capability-scope-note">
        <summary><ShieldCheck aria-hidden size={17} />{t("machine.credentialTitle")}</summary>
        <p>{t("machine.credentialBoundary")}</p>
      </details>
    </section>
  );
}
