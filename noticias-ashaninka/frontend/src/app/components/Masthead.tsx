// Cabecera tipo noticiero: marca, rol (Ciudadano / Administrador), estado de red, noticias guardadas,
// tema y navegación principal. Con una sesión experimental activa solo muestra la marca.
import { useEffect, useState } from "preact/hooks";
import { useApp } from "../ctx";
import { savedCount } from "../offline";
import { NEWSROOM_HREF, NEWS_HREF, type Route } from "../router";
import { type Role, type TokenCheck, verificarToken } from "../role";

interface MastheadProps {
  route: Route;
  enSesion: boolean;
  role: Role;
  token: string | null;
  onRole: (r: Role) => void;
  onToken: (t: string | null) => void;
  /** Última noticia abierta: lleva al estudio en C4 (sin pedir nada a la red). */
  studioHref: string | null;
}

export function Masthead({ route, enSesion, role, token, onRole, onToken, studioHref }: MastheadProps) {
  const { t, online, settings, setSettings } = useApp();
  const [saved, setSaved] = useState(0);
  const [entrada, setEntrada] = useState("");
  const [check, setCheck] = useState<TokenCheck | "verificando" | null>(null);
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

  const submit = async (e: Event) => {
    e.preventDefault();
    setCheck("verificando");
    const r = await verificarToken(entrada);
    setCheck(r);
    if (r === "ok") {
      onToken(entrada.trim());
      setEntrada("");
    }
  };
  const elegir = (r: Role) => {
    onRole(r);
    if (r === "ciudadano") {
      onToken(null);
      setCheck(null);
    }
  };

  return (
    <header class="top">
      <div class="top-strip">
        <p class="top-access">{t(role === "admin" && token ? "masthead.access.admin" : "masthead.access.public")}</p>
        <div class="roles" role="radiogroup" aria-label={t("role.group")}>
          {(["ciudadano", "admin"] as const).map((r) => (
            <button
              key={r}
              type="button"
              role="radio"
              aria-checked={role === r}
              class={`role role-${r}`}
              data-testid={`role-${r}`}
              onClick={() => elegir(r)}
            >
              {t(`role.${r}`)}
            </button>
          ))}
        </div>
        {role === "admin" && token && (
          <>
            <span class="pill pill-ok" data-testid="token-ok">
              {t("role.token.ok")}
            </span>
            <button type="button" class="btn btn-sm" onClick={() => elegir("ciudadano")}>
              {t("role.logout")}
            </button>
          </>
        )}
      </div>

      {role === "admin" && !token && (
        <form class="token-form" onSubmit={(e) => void submit(e)}>
          <label class="field">
            {t("role.token.label")}
            <input
              type="password"
              autocomplete="off"
              value={entrada}
              data-testid="token-input"
              onInput={(e) => {
                setEntrada((e.currentTarget as HTMLInputElement).value);
                setCheck(null);
              }}
            />
          </label>
          <button type="submit" class="btn primary" data-testid="token-submit" disabled={!entrada.trim() || check === "verificando"}>
            {t(check === "verificando" ? "role.token.checking" : "role.token.submit")}
          </button>
          <p class="tr-note">{t("role.token.hint")}</p>
          <p role="alert" class="token-msg" data-testid="token-msg">
            {check === "rechazado" && t("role.token.bad")}
            {check === "red" && t("role.token.net")}
          </p>
        </form>
      )}

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
            {role === "admin" && token && (
              <a href={NEWSROOM_HREF} aria-current={route.name === "newsroom" ? "page" : undefined}>
                {t("nav.newsroom")}
              </a>
            )}
            <a href="#/ajustes" aria-current={route.name === "settings" ? "page" : undefined}>
              {t("nav.settings")}
            </a>
          </nav>
        </div>
      </div>
    </header>
  );
}
