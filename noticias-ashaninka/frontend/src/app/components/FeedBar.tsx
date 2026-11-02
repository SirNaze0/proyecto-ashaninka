// Barra «Noticias de TV Perú» del tablón (NoticiasTVPeru): intervalo de actualización automática,
// «Refrescar ahora» y estado del último ciclo. El trabajo lo hace el servidor (ver app/feed/).
import { useEffect, useRef, useState } from "preact/hooks";
import { useApp } from "../ctx";
import { type FeedStatus, fetchFeedStatus, refrescarAhora, relativo, resumenUltimo, setIntervalo, sondeoMs } from "../feed";

export function FeedBar({ onActualizado }: { onActualizado: () => void }) {
  const { t, online } = useApp();
  const [st, setSt] = useState<FeedStatus | null>(null);
  const [aviso, setAviso] = useState("");
  const ultima = useRef<string | null | undefined>(undefined);

  async function cargar() {
    const s = await fetchFeedStatus();
    if (!s) return null;
    // un ciclo terminó desde la última consulta: el tablón se recarga
    if (ultima.current !== undefined && s.ultima_ejecucion !== ultima.current && !s.ejecutando) onActualizado();
    ultima.current = s.ultima_ejecucion;
    setSt(s);
    return s;
  }

  useEffect(() => {
    if (!online) return;
    let vivo = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const ciclo = async () => {
      const s = await cargar();
      if (vivo) timer = setTimeout(() => void ciclo(), sondeoMs(s));
    };
    void ciclo();
    return () => {
      vivo = false;
      clearTimeout(timer);
    };
    // st?.ejecutando: al lanzar un ciclo se reinicia el sondeo con el intervalo rápido
  }, [online, st?.ejecutando]);

  if (!st) return null;

  const etiqueta = (min: number) => (min === 0 ? t("feed.off") : min < 60 ? t("feed.min", { n: min }) : t("feed.h", { n: min / 60 }));
  const tiempo = (iso: string | null) => {
    const r = relativo(iso);
    return r ? t(r.clave, { n: r.n }) : "";
  };
  const resumen = resumenUltimo(st);

  async function cambiar(min: number) {
    setAviso("");
    const s = await setIntervalo(min);
    if (s) setSt(s);
    else setAviso(t("feed.error"));
  }

  async function refrescar() {
    setAviso("");
    const r = await refrescarAhora();
    if (r === "iniciado") setSt({ ...st!, ejecutando: true });
    else if (r === "en-curso") setAviso(t("feed.busy"));
    else if (r === "apagado") setAviso(t("feed.disabled"));
    else setAviso(t("feed.error"));
  }

  return (
    <section class="feedbar" aria-labelledby="feed-h" data-testid="feedbar">
      <h3 id="feed-h">{t("feed.title", { f: st.fuente })}</h3>
      <div class="feed-controls">
        <label class="field">
          {t("feed.every")}
          <select
            value={String(st.intervalo_min)}
            disabled={!st.habilitado}
            data-testid="feed-interval"
            onChange={(e) => void cambiar(Number((e.currentTarget as HTMLSelectElement).value))}
          >
            {st.intervalos_permitidos.map((m) => (
              <option key={m} value={String(m)}>
                {etiqueta(m)}
              </option>
            ))}
          </select>
        </label>
        <button type="button" class="btn primary" data-testid="feed-refresh" disabled={!st.habilitado || st.ejecutando} onClick={() => void refrescar()}>
          {t(st.ejecutando ? "feed.running.short" : "feed.refresh")}
        </button>
      </div>
      <p class="feed-status" role="status" data-testid="feed-status">
        {!st.habilitado
          ? t("feed.disabled")
          : st.ejecutando
            ? t("feed.running")
            : [
                st.ultima_ejecucion ? t("feed.lastRun", { t: tiempo(st.ultima_ejecucion) }) : t("feed.never"),
                resumen ? t(resumen.clave, resumen.vars) : "",
                st.proxima_ejecucion ? t("feed.next", { t: tiempo(st.proxima_ejecucion) }) : "",
              ]
                .filter(Boolean)
                .join(" · ")}
      </p>
      {aviso && (
        <p class="token-msg" role="alert" data-testid="feed-msg">
          {aviso}
        </p>
      )}
      <p class="tr-note">{t("feed.note")}</p>
    </section>
  );
}
