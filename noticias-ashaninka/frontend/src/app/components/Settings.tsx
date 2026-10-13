import { useApp } from "../ctx";
import { LANGS, type Lang, pendingCount } from "../i18n";

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
