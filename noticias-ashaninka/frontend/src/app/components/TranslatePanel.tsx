// Pantalla de entrada: texto en castellano → traducción al asháninka, con la presentadora al costado.
// El traductor está PENDIENTE de integración (ver translator.ts): por defecto no se envía el texto
// a ningún lugar y no se muestra ninguna traducción. El avatar es el mismo de C4 y queda en reposo:
// sin audio no hay visemas, así que no «habla» ni finge leer el resultado.
import type { ComponentType } from "preact";
import { useEffect, useReducer, useRef, useState } from "preact/hooks";
import type { AvatarHandle } from "../../avatar/create-avatar";
import { useApp } from "../ctx";
import { FALLBACK_IMG, VRM_URL } from "../data";
import { NEWS_HREF } from "../router";
import { ESTADO_INICIAL, TRADUCTOR_PENDIENTE, type Translator, reducir } from "../translator";

interface AvatarPanelProps {
  vrmUrl: string;
  fallbackImage: string;
  width?: number;
  height?: number;
  onReady?: (h: AvatarHandle) => void;
}

export function TranslatePanel({ translator = TRADUCTOR_PENDIENTE }: { translator?: Translator }) {
  const { t } = useApp();
  const [texto, setTexto] = useState("");
  const [state, dispatch] = useReducer(reducir, ESTADO_INICIAL);
  const [Panel, setPanel] = useState<ComponentType<AvatarPanelProps> | null>(null);
  const [avatarMode, setAvatarMode] = useState<string | null>(null);
  const abort = useRef<AbortController | null>(null);

  // Import dinámico, igual que en C4: three y three-vrm quedan fuera del paquete inicial
  useEffect(() => {
    let dead = false;
    void import("../../avatar/AvatarPanel").then((m) => !dead && setPanel(() => m.AvatarPanel));
    return () => {
      dead = true;
      abort.current?.abort();
    };
  }, []);

  const cargando = state.s === "cargando";
  const onSubmit = async (e: Event) => {
    e.preventDefault();
    if (!texto.trim() || cargando) return;
    abort.current = new AbortController();
    dispatch({ type: "enviar" });
    try {
      dispatch({ type: "ok", texto: await translator.translate(texto.trim(), abort.current.signal) });
    } catch (err) {
      if (!abort.current.signal.aborted) dispatch({ type: "fallo", error: err });
    }
  };

  return (
    <section class="tr" aria-labelledby="tr-h">
      <div class="tr-media">
        <div class="avatar-slot" data-avatar-mode={avatarMode ?? "cargando"}>
          {Panel && (
            <Panel vrmUrl={VRM_URL} fallbackImage={FALLBACK_IMG} width={320} height={320} onReady={(h) => setAvatarMode(h.mode)} />
          )}
          {avatarMode === "fijo" && <p class="mode">{t("avatar.fallback")}</p>}
        </div>
        <p class="tr-note">{t("notice.avatar")}</p>
      </div>

      <div class="tr-main">
        <h2 id="tr-h">{t("translate.title")}</h2>
        {!translator.disponible && (
          <p class="banner" role="note" data-testid="tr-pending">
            {t("translate.pending")}
          </p>
        )}
        <form onSubmit={(e) => void onSubmit(e)}>
          <label class="field">
            {t("translate.input")}
            <textarea
              lang="es"
              rows={6}
              value={texto}
              disabled={cargando}
              data-testid="tr-input"
              onInput={(e) => {
                setTexto((e.currentTarget as HTMLTextAreaElement).value);
                dispatch({ type: "editar" });
              }}
            />
          </label>
          <button type="submit" class="btn primary" disabled={!texto.trim() || cargando} data-testid="tr-submit">
            {t("translate.submit")}
          </button>
        </form>

        <h3 id="tr-out-h">{t("translate.output")}</h3>
        <div class="tr-out" aria-labelledby="tr-out-h" aria-live="polite" aria-busy={cargando} data-testid="tr-output" data-estado={state.s}>
          {state.s === "inicial" && <p class="tr-empty">{t("translate.placeholderResult")}</p>}
          {state.s === "cargando" && <p role="status">{t("translate.loading")}</p>}
          {state.s === "pendiente" && <p class="tr-empty">{t("translate.notAvailable")}</p>}
          {state.s === "error" && (
            <p role="alert">{state.mensaje === "vacio" ? t("translate.errorEmpty") : t("translate.error", { m: state.mensaje })}</p>
          )}
          {state.s === "resultado" && (
            <p lang="cni" class="tr-result">
              {state.texto}
            </p>
          )}
        </div>

        <p class="tr-note">{t("translate.voiceNote")}</p>
        <p>
          <a class="btn tr-news" href={NEWS_HREF} data-testid="tr-to-news">
            {t("translate.toNews")}
          </a>
        </p>
      </div>
    </section>
  );
}
