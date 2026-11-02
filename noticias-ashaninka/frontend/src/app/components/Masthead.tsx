// Cabecera tipo noticiero: marca, estado de red, noticias guardadas, tema y navegación principal.
// Sin roles (QuitarAdmin): la Sala de redacción está abierta a todos. Con una sesión experimental
// activa solo muestra la marca.
import { useEffect, useState } from "preact/hooks";
import { useApp } from "../ctx";
import { savedCount } from "../offline";
import { NEWSROOM_HREF, NEWS_HREF, type Route } from "../router";

interface MastheadProps {
  route: Route;
  enSesion: boolean;
  /** Última noticia abierta: lleva al estudio en C4 (sin pedir nada a la red). */
  studioHref: string | null;
}

export function Masthead({ route, enSesion, studioHref }: MastheadProps) {
  const { t, online, settings, setSettings } = useApp();
  const [saved, setSaved] = useState(0);
  const oscuro =
    settings.theme === "dark" ||
    (settings.theme === "auto" && typeof matchMedia !== "undefined" && matchMedia("(prefers-color-scheme: dark)").matches);

  useEffect(() => {
    let dead = false;
    void savedCount().then((n) => !dead && setSaved(n));
    return () => {
      dead = true;
    };
  }, [route]);

  if (enSesion) {
    return (
      <header class="top">
        <span class="brand">{t("appTitle")}</span>
      </header>
    );
  }

  return (
    <header class="top">
      <div class="top-strip">
        <p class="top-access">{t("masthead.access.public")}</p>
      </div>

      <div class="top-main">
        <a class="brand" href="#/">
          <span class="logo" aria-hidden="true">
            <i />
            <i />
            <i />
            <i />
          </span>
          <span class="brand-text">
            {t("appTitle")}
            <small>{t("masthead.subtitle")}</small>
          </span>
        </a>
        <div class="top-end">
          <span class={`pill ${online ? "pill-ok" : "pill-warn"}`} data-testid="net-status">
            {t(online ? "net.online" : "net.offline")}
          </span>
          <span class="pill" aria-live="polite" data-testid="saved-count">
            {t("masthead.saved", { n: saved })}
          </span>
          <button
            type="button"
            class="btn btn-sm"
            data-testid="theme-toggle"
            onClick={() => setSettings({ ...settings, theme: oscuro ? "light" : "dark" })}
          >
            {t(oscuro ? "masthead.themeToLight" : "masthead.themeToDark")}
          </button>
          <nav aria-label="Principal">
            <a href="#/" aria-current={route.name === "translate" ? "page" : undefined}>
              {t("nav.translate")}
            </a>
            <a href={NEWS_HREF} aria-current={route.name === "list" ? "page" : undefined}>
              {t("nav.news")}
            </a>
            {studioHref && (
              <a href={studioHref} aria-current={route.name === "news" ? "page" : undefined}>
                {t("nav.studio")}
              </a>
            )}
            <a href={NEWSROOM_HREF} aria-current={route.name === "newsroom" ? "page" : undefined}>
              {t("nav.newsroom")}
            </a>
            <a href="#/ajustes" aria-current={route.name === "settings" ? "page" : undefined}>
              {t("nav.settings")}
            </a>
          </nav>
        </div>
      </div>
    </header>
  );
}
