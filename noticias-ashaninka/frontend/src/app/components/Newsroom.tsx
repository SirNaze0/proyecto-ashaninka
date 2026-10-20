// Sala de redacción (solo administrador): carga de texto por párrafos o de archivos (.txt, .csv, .json),
// procedencia obligatoria y publicación real: /api/news → process → build (audio por lotes).
// El texto debe venir YA en asháninka; la traducción es-cni sigue pendiente de integración.
import { useRef, useState } from "preact/hooks";
import { useApp } from "../ctx";
import {
  ACCEPTED_EXTENSIONS,
  MAX_PARAGRAPHS,
  type NewsDraft,
  PLANTILLA_CSV,
  PROVENANCE_TIPOS,
  PublishError,
  type PublishResult,
  emptyDraft,
  parseNewsFile,
  parsePlainText,
  publicar,
  validar,
} from "../newsroom";
import { newsHref } from "../router";

export function Newsroom() {
  const { t, token } = useApp();
  const [draft, setDraft] = useState<NewsDraft>(emptyDraft);
  const [queue, setQueue] = useState<NewsDraft[]>([]);
  const [current, setCurrent] = useState(0);
  const [fileMsg, setFileMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [reading, setReading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [paste, setPaste] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<PublishResult | null>(null);
  const input = useRef<HTMLInputElement>(null);

  const patch = (p: Partial<NewsDraft>) => {
    setDraft((d) => ({ ...d, ...p }));
    setResult(null);
  };
  const patchProv = (p: Partial<NewsDraft["procedencia"]>) => patch({ procedencia: { ...draft.procedencia, ...p } });

  const load = (d: NewsDraft) => {
    setDraft(d);
    setResult(null);
    setError("");
  };

  async function onFiles(files: FileList | null) {
    const file = files?.[0];
    if (!file) return;
    setReading(true);
    setFileMsg(null);
    try {
      const list = await parseNewsFile(file);
      if (!list.length) throw new Error("no se encontraron noticias");
      setQueue(list.length > 1 ? list : []);
      setCurrent(0);
      load(list[0]);
      setFileMsg({ ok: true, text: t("newsroom.import.loaded", { n: list.length, f: file.name }) });
    } catch (err) {
      setFileMsg({ ok: false, text: t("newsroom.import.error", { m: err instanceof Error ? err.message : String(err) }) });
    } finally {
      setReading(false);
      if (input.current) input.current.value = "";
    }
  }

  function descargarPlantilla() {
    const url = URL.createObjectURL(new Blob([PLANTILLA_CSV], { type: "text/csv" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = "plantilla_noticias.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  async function onPublish() {
    const falta = validar(draft);
    if (falta) return setError(t("newsroom.error.invalid", { m: falta }));
    if (!token) return;
    setBusy(true);
    setError("");
    setResult(null);
    try {
      setResult(await publicar(draft, token));
    } catch (err) {
      if (err instanceof PublishError) {
        setError(err.status === 403 ? t("newsroom.error.forbidden") : t("newsroom.error.step", { paso: err.paso, m: err.message }));
      } else setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  const steps = [1, 2, 3, 4];
  const step = result ? 4 : draft.titulo_cni.trim() && draft.paragraphs.some((p) => p.trim()) ? 3 : 1;

  return (
    <section class="room" aria-labelledby="room-h">
      <h2 id="room-h">{t("newsroom.title")}</h2>
      <ol class="steps" aria-label={t("newsroom.steps")}>
        {steps.map((n) => (
          <li key={n} class={n < step ? "done" : ""} aria-current={n === step ? "step" : undefined}>
            {n}. {t(`newsroom.step${n}`)}
          </li>
        ))}
      </ol>
      <p class="banner" role="note" data-testid="room-pending">
        {t("newsroom.translatorPending")}
      </p>

      <div class="card">
        <h3>{t("newsroom.import")}</h3>
        <p class="tr-note">{t("newsroom.import.hint")}</p>
        <label
          class={`drop${dragging ? " drop-on" : ""}`}
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            void onFiles(e.dataTransfer?.files ?? null);
          }}
        >
          <span class="drop-icon" aria-hidden="true">
            {dragging ? "⤓" : "⇪"}
          </span>
          <span>{dragging ? t("newsroom.import.release") : reading ? t("newsroom.import.reading") : t("newsroom.import.drop")}</span>
          <span class="drop-ext">{ACCEPTED_EXTENSIONS.join("  ")}</span>
          <input
            ref={input}
            type="file"
            class="sr-only"
            data-testid="room-file"
            accept={ACCEPTED_EXTENSIONS.join(",")}
            onChange={(e) => void onFiles((e.currentTarget as HTMLInputElement).files)}
          />
        </label>
        <button type="button" class="btn btn-sm" onClick={descargarPlantilla}>
          {t("newsroom.import.template")}
        </button>
        {fileMsg && (
          <p role={fileMsg.ok ? "status" : "alert"} class={fileMsg.ok ? "room-ok" : "token-msg"} data-testid="room-file-msg">
            {fileMsg.text}
          </p>
        )}
        {queue.length > 1 && (
          <>
            <h4>{t("newsroom.batch", { n: queue.length })}</h4>
            <ul class="batch" data-testid="room-batch">
              {queue.map((q, i) => (
                <li key={i}>
                  <span class="batch-title" lang="cni">
                    {i + 1}. {q.titulo_cni || "—"}
                  </span>
                  <button
                    type="button"
                    class="btn btn-sm"
                    disabled={i === current}
                    onClick={() => {
                      setCurrent(i);
                      load(q);
                    }}
                  >
                    {t(i === current ? "newsroom.batch.current" : "newsroom.batch.load")}
                  </button>
                </li>
              ))}
            </ul>
          </>
        )}
        <details>
          <summary>{t("newsroom.paste")}</summary>
          <p class="tr-note">{t("newsroom.paste.hint")}</p>
          <textarea rows={5} lang="cni" value={paste} data-testid="room-paste" aria-label={t("newsroom.paste")} onInput={(e) => setPaste((e.currentTarget as HTMLTextAreaElement).value)} />
          <button
            type="button"
            class="btn btn-sm"
            disabled={!paste.trim()}
            data-testid="room-paste-apply"
            onClick={() => {
              setQueue([]);
              load({ ...emptyDraft(), ...parsePlainText(paste), procedencia: draft.procedencia });
            }}
          >
            {t("newsroom.paste.apply")}
          </button>
        </details>
      </div>

      <div class="card">
        <label class="field">
          {t("newsroom.field.title")}
          <input type="text" lang="cni" value={draft.titulo_cni} maxLength={160} data-testid="room-title" onInput={(e) => patch({ titulo_cni: (e.currentTarget as HTMLInputElement).value })} />
        </label>
        {draft.paragraphs.map((p, i) => (
          <div class="par-edit" key={i}>
            <label class="field">
              {t("newsroom.field.paragraph", { n: i + 1 })}
              <textarea
                rows={3}
                lang="cni"
                maxLength={2000}
                value={p}
                data-testid={`room-par-${i}`}
                onInput={(e) => patch({ paragraphs: draft.paragraphs.map((x, j) => (j === i ? (e.currentTarget as HTMLTextAreaElement).value : x)) })}
              />
            </label>
            {draft.paragraphs.length > 1 && (
              <button type="button" class="btn btn-sm" onClick={() => patch({ paragraphs: draft.paragraphs.filter((_, j) => j !== i) })}>
                {t("newsroom.field.removeParagraph", { n: i + 1 })}
              </button>
            )}
          </div>
        ))}
        {draft.paragraphs.length < MAX_PARAGRAPHS && (
          <button type="button" class="btn btn-sm" data-testid="room-add-par" onClick={() => patch({ paragraphs: [...draft.paragraphs, ""] })}>
            {t("newsroom.field.addParagraph")}
          </button>
        )}
        <div class="grid2">
          <label class="field">
            {t("newsroom.field.variant")}
            <input type="text" value={draft.variante_dialectal} onInput={(e) => patch({ variante_dialectal: (e.currentTarget as HTMLInputElement).value })} />
          </label>
          <label class="field">
            {t("newsroom.field.date")}
            <input type="date" value={draft.fecha_publicacion} onInput={(e) => patch({ fecha_publicacion: (e.currentTarget as HTMLInputElement).value })} />
          </label>
          <label class="field">
            {t("newsroom.field.source")}
            <input type="text" value={draft.fuente_original} onInput={(e) => patch({ fuente_original: (e.currentTarget as HTMLInputElement).value })} />
          </label>
        </div>
        <details>
          <summary>{t("newsroom.field.titleEs")} / {t("newsroom.field.bodyEs")}</summary>
          <label class="field">
            {t("newsroom.field.titleEs")}
            <input type="text" lang="es" value={draft.titulo_es} onInput={(e) => patch({ titulo_es: (e.currentTarget as HTMLInputElement).value })} />
          </label>
          <label class="field">
            {t("newsroom.field.bodyEs")}
            <textarea rows={3} lang="es" value={draft.cuerpo_es} onInput={(e) => patch({ cuerpo_es: (e.currentTarget as HTMLTextAreaElement).value })} />
          </label>
        </details>
      </div>

      <fieldset class="card">
        <legend>{t("newsroom.prov.heading")}</legend>
        <label class="field">
          {t("newsroom.prov.tipo")}
          <select value={draft.procedencia.tipo} data-testid="room-prov-tipo" onChange={(e) => patchProv({ tipo: (e.currentTarget as HTMLSelectElement).value as NewsDraft["procedencia"]["tipo"] })}>
            {PROVENANCE_TIPOS.map((p) => (
              <option key={p} value={p}>
                {t(`newsroom.prov.${p}`)}
              </option>
            ))}
          </select>
        </label>
        <div class="grid2">
          <label class="field">
            {t("newsroom.prov.sistema")}
            <input type="text" value={draft.procedencia.sistema} onInput={(e) => patchProv({ sistema: (e.currentTarget as HTMLInputElement).value })} />
          </label>
          <label class="field">
            {t("newsroom.prov.version")}
            <input type="text" value={draft.procedencia.version} onInput={(e) => patchProv({ version: (e.currentTarget as HTMLInputElement).value })} />
          </label>
        </div>
        <label class="radio">
          <input type="checkbox" checked={draft.procedencia.revisado_por_hablante} onChange={(e) => patchProv({ revisado_por_hablante: (e.currentTarget as HTMLInputElement).checked })} />
          {t("newsroom.prov.revisado")}
        </label>
      </fieldset>

      <div class="card room-publish">
        <p class="tr-note">{t("newsroom.publish.hint")}</p>
        <button type="button" class="btn primary" data-testid="room-publish" disabled={busy} onClick={() => void onPublish()}>
          {t(busy ? "newsroom.publish.working" : "newsroom.publish")}
        </button>
        {busy && (
          <div class="synth-bar" role="progressbar" aria-label={t("newsroom.publish.working")}>
            <i />
          </div>
        )}
        <p role="alert" class="token-msg" data-testid="room-error">
          {error}
        </p>
        {result && (
          <p role="status" class="room-ok" data-testid="room-result">
            {t("newsroom.result", { id: result.id, a: result.conAudio, b: result.bloqueados })}{" "}
            <a class="btn" href={newsHref(result.id, "C4")} data-testid="room-open">
              {t("newsroom.result.open")}
            </a>
          </p>
        )}
      </div>
    </section>
  );
}
