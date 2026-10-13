// Flujo guiado del experimento (Fase 5): consentimiento → 4 × (noticia + cuestionario) → final → fin.
// La condición de cada bloque la fija el cuadrado de Williams del participante; con una sesión activa
// no hay selector de condición ni navegación libre (lo impone la guardia de rutas de App.tsx).
// Texto del consentimiento e ítems de comprensión: marcadores pendientes del comité y del hablante;
// no se inventa ningún texto en asháninka.
import { useEffect, useRef, useState } from "preact/hooks";
import { useApp } from "../ctx";
import {
  type Answers,
  ExperimentError,
  type ExperimentState,
  type ItemDef,
  validarRespuestas,
} from "../experiment";
import type { Route } from "../router";
import { Presentation } from "./Presentation";

type ExpRoute = Extract<Route, { name: "experiment" }>;

export function ExperimentFlow({ route }: { route: ExpRoute }) {
  const { experiment: ex, t } = useApp();
  const s = ex.state;
  if (!ex.loaded) return <p role="status">{t("news.loading")}</p>;
  if (!s || s.estado === "abandonada") return <Consent />;
  if (s.estado === "completa") return <End s={s} />;
  return (
    <div class="exp" data-testid="exp-flow" data-fase={s.fase}>
      <Bar s={s} />
      {route.step === "bloque" && s.fase === "bloque" && <Block s={s} />}
      {route.step === "cuestionario" && s.fase === "cuestionario" && (
        <Questionnaire
          key={`post-${s.posicion}`}
          kind="post_noticia"
          defs={s.instrumentos.post_noticia}
          heading={t("exp.q.heading", { k: s.posicion + 1, n: s.bloques.length })}
          note={t("exp.q.interviewer")}
          onSubmit={(a) => ex.enviarPostNoticia(a)}
        />
      )}
      {route.step === "final" && s.fase === "final" && (
        <Questionnaire
          key="final"
          kind="final"
          defs={s.instrumentos.final}
          heading={t("exp.final.heading")}
          note={t("exp.final.rank")}
          onSubmit={(a) => ex.enviarFinal(a)}
        />
      )}
      {route.step === "fin" && s.fase === "fin" && <End s={s} />}
    </div>
  );
}

// ------------------------------------------------------------------ indicador de pasos (solo visual)
// Consentimiento → Noticia 1..4 → Preguntas finales → Fin. Igual en las 4 condiciones.
function Steps({ actual, total }: { actual: number; total: number }) {
  const { t } = useApp();
  const pasos = [
    t("exp.step.consent"),
    ...Array.from({ length: total }, (_, k) => t("exp.step.block", { k: k + 1 })),
    t("exp.step.final"),
    t("exp.step.end"),
  ];
  return (
    <ol class="steps" aria-label={t("exp.steps")} data-testid="exp-steps">
      {pasos.map((p, i) => (
        <li key={i} class={i < actual ? "done" : undefined} aria-current={i === actual ? "step" : undefined}>
          {p}
        </li>
      ))}
    </ol>
  );
}

function pasoActual(s: ExperimentState): number {
  if (s.fase === "bloque" || s.fase === "cuestionario") return 1 + s.posicion;
  return s.fase === "final" ? 1 + s.bloques.length : 2 + s.bloques.length;
}

// ------------------------------------------------------------------ barra: participante y abandono
function Bar({ s }: { s: ExperimentState }) {
  const { experiment: ex, t } = useApp();
  const [asking, setAsking] = useState(false);
  return (
    <div class="exp-bar" data-testid="exp-bar">
      <span data-testid="exp-code">{t("exp.session", { code: s.participant_code })}</span>
      {s.piloto && (
        <span class="badge" role="note" data-testid="exp-pilot">
          {t("exp.pilot")}
        </span>
      )}
      {!asking ? (
        <button type="button" class="btn" data-testid="exp-abandon" onClick={() => setAsking(true)}>
          {t("exp.abandon")}
        </button>
      ) : (
        <span role="alertdialog" aria-label={t("exp.abandon")} class="exp-confirm">
          {t("exp.abandon.confirm")}{" "}
          <button type="button" class="btn" data-testid="exp-abandon-yes" onClick={() => void ex.abandonar().then(() => (location.hash = "#/"))}>
            {t("exp.abandon.yes")}
          </button>{" "}
          <button type="button" class="btn primary" onClick={() => setAsking(false)}>
            {t("exp.abandon.no")}
          </button>
        </span>
      )}
      <Steps actual={pasoActual(s)} total={s.bloques.length} />
    </div>
  );
}

// ------------------------------------------------------------------ consentimiento y código
function Consent() {
  const { experiment: ex, t } = useApp();
  const [code, setCode] = useState("");
  const [accepted, setAccepted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const prev = ex.state;

  const submit = async (e: Event) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await ex.start(code);
      location.hash = "#/experimento/bloque/" + (ex.state?.posicion ?? 0);
    } catch (err) {
      if (err instanceof ExperimentError) {
        const detalle = err.message;
        setError(err.tipo === "conflicto" ? t("exp.error.conflicto", { detalle }) : t(`exp.error.${err.tipo}`));
      } else setError(t("exp.error.red"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section class="exp" data-testid="exp-consent" aria-labelledby="consent-h">
      <Steps actual={0} total={4} />
      <h2 id="consent-h">{t("exp.consent.heading")}</h2>
      {prev?.estado === "abandonada" && (
        <p class="banner" role="note">
          {t("exp.abandon")}: {prev.participant_code}
        </p>
      )}
      <p class="banner" role="note" data-testid="consent-pending">
        {t("exp.consent.pending")}
      </p>
      <p class="mode" role="note">
        {t("exp.consent.audioPending")}
      </p>
      <p>{t("exp.consent.noPii")}</p>
      <form onSubmit={submit} noValidate>
        <p>
          <label for="exp-code">{t("exp.code")}</label>
          <br />
          <input
            id="exp-code"
            data-testid="exp-code-input"
            type="text"
            autocomplete="off"
            autocapitalize="characters"
            aria-describedby="exp-code-hint"
            value={code}
            onInput={(e) => setCode((e.target as HTMLInputElement).value)}
          />
        </p>
        <p id="exp-code-hint" class="mode">
          {t("exp.code.hint")}
        </p>
        <p>
          <label class="radio">
            <input
              type="checkbox"
              data-testid="exp-accept"
              checked={accepted}
              onChange={(e) => setAccepted((e.target as HTMLInputElement).checked)}
            />
            {t("exp.consent.accept")}
          </label>
        </p>
        {error && (
          <p role="alert" data-testid="exp-error">
            {error}
          </p>
        )}
        <button type="submit" class="btn primary" data-testid="exp-start" disabled={!accepted || code.trim() === "" || busy}>
          {busy ? t("exp.starting") : t("exp.start")}
        </button>
        {prev && (
          <button type="button" class="btn" onClick={() => void ex.olvidar()}>
            {t("exp.end.new")}
          </button>
        )}
      </form>
    </section>
  );
}

// ------------------------------------------------------------------ bloque (la noticia en su condición)
function Block({ s }: { s: ExperimentState }) {
  const { experiment: ex, events, t } = useApp();
  const b = s.bloques[s.posicion];
  const [done, setDone] = useState(false);
  const busy = useRef(false);

  useEffect(() => {
    setDone(false);
    events.setContext(b.condicion, b.news_id);
    void events.emit("block-start", { posicion: b.posicion });
  }, [b.posicion, b.news_id, b.condicion]);

  const next = async () => {
    if (busy.current) return;
    busy.current = true;
    try {
      await ex.terminarBloque(done);
      location.hash = `#/experimento/cuestionario/${s.posicion}`;
    } finally {
      busy.current = false;
    }
  };

  return (
    <section aria-label={t("exp.block", { k: s.posicion + 1, n: s.bloques.length })}>
      <p class="exp-progress" data-testid="exp-progress">
        {t("exp.block", { k: s.posicion + 1, n: s.bloques.length })}
      </p>
      <Presentation key={`${b.news_id}-${b.condicion}`} id={b.news_id} condition={b.condicion} experiment onDone={() => setDone(true)} />
      <p role="status" data-testid="exp-wait">
        {!done && (b.condicion === "C1" ? t("exp.waitRead") : t("exp.waitEnd"))}
      </p>
      <button type="button" class="btn primary" data-testid="exp-continue" disabled={!done} onClick={() => void next()}>
        {t("exp.continue")}
      </button>
    </section>
  );
}

// ------------------------------------------------------------------ cuestionarios
function ItemField(props: {
  d: ItemDef;
  value: string | number | undefined;
  error: string | undefined;
  onChange: (v: string | number) => void;
}) {
  const { t } = useApp();
  const { d, value, error, onChange } = props;
  const pending = d.status.startsWith("PENDIENTE");
  const legend = (
    <>
      {d.etiqueta}
      {d.opcional && ` ${t("exp.final.optional")}`}
      {pending && <span class="badge"> ({t("exp.q.pending")})</span>}
    </>
  );
  if (d.tipo === "texto") {
    return (
      <p>
        <label for={`q-${d.id}`}>{legend}</label>
        <br />
        <textarea
          id={`q-${d.id}`}
          data-testid={`q-${d.id}`}
          rows={3}
          maxLength={d.max}
          value={String(value ?? "")}
          aria-invalid={error ? "true" : undefined}
          onInput={(e) => onChange((e.target as HTMLTextAreaElement).value)}
        />
        {error === "pii" && <span role="alert"> {t("exp.q.missing")}</span>}
      </p>
    );
  }
  const opciones: { v: string | number; label: string }[] =
    d.tipo === "binario"
      ? [
          { v: 1, label: t("exp.q.correct") },
          { v: 0, label: t("exp.q.incorrect") },
        ]
      : d.tipo === "entero"
        ? Array.from({ length: (d.max ?? 0) - (d.min ?? 0) + 1 }, (_, i) => ({ v: (d.min ?? 0) + i, label: String((d.min ?? 0) + i) }))
        : (d.opciones ?? []).map((o) => ({ v: o, label: o.replace(/_/g, " ") }));
  return (
    <fieldset class={`q-item q-${d.tipo}`} aria-invalid={error ? "true" : undefined} data-testid={`q-${d.id}`}>
      <legend>{legend}</legend>
      {opciones.map((o) => (
        <label key={String(o.v)} class="radio">
          <input
            type="radio"
            name={d.id}
            data-testid={`q-${d.id}-${o.v}`}
            checked={value === o.v}
            onChange={() => onChange(o.v)}
          />
          {o.label}
        </label>
      ))}
      {error && error !== "pii" && (
        <span role="alert" data-testid={`q-${d.id}-error`}>
          {" "}
          {error === "ranking" ? t("exp.final.rankError") : t("exp.q.missing")}
        </span>
      )}
    </fieldset>
  );
}

function Questionnaire(props: {
  kind: "post_noticia" | "final";
  defs: ItemDef[];
  heading: string;
  note: string;
  onSubmit: (a: Answers) => Promise<void>;
}) {
  const { t } = useApp();
  const [answers, setAnswers] = useState<Answers>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);

  const submit = async (e: Event) => {
    e.preventDefault();
    const err = validarRespuestas(props.defs, answers);
    setErrors(err);
    if (Object.keys(err).length > 0) return;
    setBusy(true);
    setFailed(false);
    try {
      await props.onSubmit(answers);
      // la guardia de rutas lleva al siguiente paso
    } catch {
      setFailed(true);
      setBusy(false);
    }
  };

  return (
    <form class="q" data-testid="q-form" data-kind={props.kind} onSubmit={submit} noValidate aria-labelledby="q-h">
      <h2 id="q-h">{props.heading}</h2>
      <p class="mode" role="note">
        {props.note}
      </p>
      {props.defs.map((d) => (
        <ItemField
          key={d.id}
          d={d}
          value={answers[d.id] as string | number | undefined}
          error={errors[d.id]}
          onChange={(v) => setAnswers((a) => ({ ...a, [d.id]: v }))}
        />
      ))}
      {(Object.keys(errors).length > 0 || failed) && (
        <p role="alert" data-testid="q-error">
          {t("exp.q.missing")}
        </p>
      )}
      <button type="submit" class="btn primary" data-testid="q-send" disabled={busy}>
        {t("exp.q.send")}
      </button>
    </form>
  );
}

// ------------------------------------------------------------------ cierre
function End({ s }: { s: ExperimentState }) {
  const { experiment: ex, online, t } = useApp();
  const [estado, setEstado] = useState<"sync" | "pendiente" | "ok">(s.estado === "completa" ? "ok" : online ? "sync" : "pendiente");
  const running = useRef(false);

  const run = async () => {
    if (running.current) return;
    running.current = true;
    setEstado("sync");
    try {
      setEstado((await ex.cerrar()) ? "ok" : "pendiente");
    } finally {
      running.current = false;
    }
  };

  useEffect(() => {
    if (s.estado !== "completa" && online) void run();
  }, [online]);

  return (
    <section class="exp" data-testid="exp-end" aria-labelledby="end-h">
      <h2 id="end-h">{t("exp.end.heading")}</h2>
      <p role="status" data-testid="exp-end-status" data-estado={estado}>
        {estado === "sync" && t("exp.end.syncing")}
        {estado === "pendiente" && t("exp.end.pending")}
        {estado === "ok" && t("exp.end.done")}
      </p>
      {estado === "pendiente" && (
        <button type="button" class="btn" data-testid="exp-retry" onClick={() => void run()}>
          {t("exp.end.retry")}
        </button>
      )}
      {estado === "ok" && (
        <button type="button" class="btn" data-testid="exp-new" onClick={() => void ex.olvidar().then(() => (location.hash = "#/experimento"))}>
          {t("exp.end.new")}
        </button>
      )}
    </section>
  );
}
