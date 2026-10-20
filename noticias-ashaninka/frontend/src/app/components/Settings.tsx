import { useApp } from "../ctx";
import { LANGS, type Lang, pendingCount } from "../i18n";
import { THEMES, type Theme } from "../settings";

export function SettingsView() {
  const { t, settings, setSettings, events } = useApp();
  return (
    <section aria-labelledby="set-h">
      <h2 id="set-h">{t("settings.title")}</h2>
      <label class="field">
        {t("settings.language")}
        <select
          value={settings.lang}
          onChange={(e) => {
            const lang = (e.currentTarget as HTMLSelectElement).value as Lang;
            setSettings({ ...settings, lang });
            void events.emit("lang", { lang });
          }}
        >
          {LANGS.map((l) => (
            <option key={l} value={l}>
              {t(`settings.lang.${l}`)}
            </option>
          ))}
        </select>
      </label>
      {settings.lang === "cni" && (
        <p class="banner" role="note">
          {t("settings.cniPending")} ({pendingCount()})
        </p>
      )}
      <label class="field">
        {t("settings.theme")}
        <select
          value={settings.theme}
          data-testid="theme-select"
          onChange={(e) => setSettings({ ...settings, theme: (e.currentTarget as HTMLSelectElement).value as Theme })}
        >
          {THEMES.map((th) => (
            <option key={th} value={th}>
              {t(`settings.theme.${th}`)}
            </option>
          ))}
        </select>
      </label>
      <fieldset>
        <legend>{t("settings.textSize")}</legend>
        {([0, 1, 2, 3] as const).map((n) => (
          <label key={n} class="radio">
            <input
              type="radio"
              name="size"
              checked={settings.textSize === n}
              onChange={() => {
                setSettings({ ...settings, textSize: n });
                void events.emit("text-size", { size: n });
              }}
            />
            {t(`settings.size.${n}`)}
          </label>
        ))}
      </fieldset>
    </section>
  );
}
