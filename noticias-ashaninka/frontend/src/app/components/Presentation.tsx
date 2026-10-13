// Componente único de presentación con las 4 condiciones experimentales (tarea 4.6):
//   C1 solo texto · C2 solo voz · C3 voz + texto resaltado · C4 voz + texto + avatar.
// Segmentos bloqueados (sin P2d): nunca se sintetizan; en C3/C4 se muestran como solo texto con su
// aviso y en C2 se omiten con un aviso, sin detener la reproducción continua.
import type { ComponentType } from "preact";
import { useEffect, useRef, useState } from "preact/hooks";
import { AudioClock } from "../../avatar/clock";
import type { AvatarHandle } from "../../avatar/create-avatar";
import type { DegradationEvent } from "../../avatar/degradation";
import { VisemeTrack } from "../../avatar/viseme-track";
import { useApp } from "../ctx";
import { fetchDetail, fetchManifest, fetchMeta, fetchTimings, streamSynthesis } from "../data";
import { Highlighter, spansMatch } from "../highlight";
import { saveNews } from "../offline";
import { SegmentPlayer, type PlayerState } from "../player";
import { type PlayerItem, RATES, nextPlayable, pickSource } from "../queue";
import { TEXT_SCALES } from "../settings";
import type { CatalogMeta, Condition, Notices as NoticesT, SegTimings, Seg } from "../types";
import { Notices } from "./Notices";

const VRM_URL = "/models/presentadora_provisional.vrm";
const FALLBACK_IMG = "/presentadora_fija.svg";

interface View {
  status: "loading" | "ready" | "error";
  segs: Seg[];
  notices: NoticesT | null;
  title: string;
  modo: "lotes" | "bajo-demanda";
  complete: boolean;
}

interface AvatarPanelProps {
  vrmUrl: string;
  fallbackImage: string;
  width?: number;
  height?: number;
  onReady?: (h: AvatarHandle) => void;
  onEvent?: (e: DegradationEvent) => void;
}

const probe = typeof Audio === "undefined" ? null : new Audio();
const canPlay = (m: string) => probe?.canPlayType(m) ?? "";

function toItem(s: Seg): PlayerItem {
  return {
    idx: s.idx,
    paragraph: s.paragraph_idx,
    url: s.tts_ready && s.audio ? pickSource(s.audio, canPlay) : null,
    blockedReason: s.blocked_reason,
  };
}

function groupByParagraph(segs: Seg[]): Seg[][] {
  const out: Seg[][] = [];
  for (const s of segs) {
    const last = out[out.length - 1];
    if (last && last[0].paragraph_idx === s.paragraph_idx) last.push(s);
    else out.push([s]);
  }
  return out;
}

function SegmentText(props: { seg: Seg; timings: SegTimings | undefined; label: string | null; now: boolean }) {
  const { seg, timings, label, now } = props;
  const spans = timings && spansMatch(timings.spans, seg.text_orig) ? timings.spans : null;
  return (
    <span
      class={`seg${label ? " seg-blocked" : ""}${now ? " seg-now" : ""}`}
      data-seg={seg.idx}
      data-blocked={label ? "1" : undefined}
    >
      {spans
        ? spans.map((s, i) => (
            <span key={i} data-span={i}>
              {s.orig_text}
            </span>
          ))
        : seg.text_orig}
      {label && <span class="badge"> ({label})</span>}{" "}
    </span>
  );
}

export function Presentation({ id, condition }: { id: number; condition: Condition }) {
  const { t, events, settings } = useApp();
  const audioMode = condition !== "C1";
  const showText = condition !== "C2";
  const sync = condition === "C3" || condition === "C4";

  const [view, setView] = useState<View>({
    status: "loading",
    segs: [],
    notices: null,
    title: "",
    modo: "lotes",
    complete: false,
  });
  const [meta, setMeta] = useState<CatalogMeta | null>(null);
  const [pstate, setPstate] = useState<PlayerState>("idle");
  const [current, setCurrent] = useState(-1);
  const [rate, setRate] = useState(1);
  const [blockedNow, setBlockedNow] = useState(-1);
  const [, setTick] = useState(0);
  const [avatarMode, setAvatarMode] = useState<string | null>(null);
  const [Panel, setPanel] = useState<ComponentType<AvatarPanelProps> | null>(null);
  const [save, setSave] = useState<{ s: "idle" | "saving" | "done" | "error"; n: number }>({ s: "idle", n: 0 });
  const bodyRef = useRef<HTMLDivElement>(null);
  const R = useRef({
    player: null as SegmentPlayer | null,
    hl: null as Highlighter | null,
    clocks: new Map<HTMLAudioElement, AudioClock>(),
    activeClock: null as AudioClock | null,
    timings: new Map<number, SegTimings>(),
    pending: new Map<number, Promise<SegTimings | null>>(),
    handle: null as AvatarHandle | null,
    curIdx: -1,
    segs: [] as Seg[],
    greeted: false,
  }).current;

  function ensure(seg: Seg | undefined): Promise<SegTimings | null> {
    if (!seg?.timings) return Promise.resolve(null);
    let p = R.pending.get(seg.idx);
    if (!p) {
      p = fetchTimings(seg.timings)
        .then((tm) => {
          R.timings.set(seg.idx, tm);
          setTick((n) => n + 1);
          return tm;
        })
        .catch(() => null);
      R.pending.set(seg.idx, p);
    }
    return p;
  }

  // ------------------------------------------------------------ carga de datos y reproductor
  useEffect(() => {
    let dead = false;
    const ac = new AbortController();
    R.timings.clear();
    R.pending.clear();
    R.curIdx = -1;
    R.greeted = false;
    R.segs = [];
    setView({ status: "loading", segs: [], notices: null, title: "", modo: "lotes", complete: false });
    setCurrent(-1);
    setPstate("idle");
    events.setContext(condition, id);
    void events.emit("view-start", { mode: condition });

    let player: SegmentPlayer | null = null;
    if (audioMode) {
      player = new SegmentPlayer({
        onState: setPstate,
        onEvent: (type, payload) => void events.emit(type, payload ?? {}),
        onBlocked: (item) => {
          setBlockedNow(item.idx);
          window.setTimeout(() => setBlockedNow((b) => (b === item.idx ? -1 : b)), 2500);
        },
        onFinished: () => {
          R.handle?.viewer?.playGesture("despedida");
        },
        onSegmentEnd: () => {},
        onSegmentStart: (item, pos, audio) => {
          R.curIdx = item.idx;
          setCurrent(item.idx);
          const clock = R.clocks.get(audio) ?? null;
          clock?.reset();
          R.activeClock = clock;
          if (!sync) return;
          R.hl?.reset();
          const seg = R.segs.find((s) => s.idx === item.idx);
          void ensure(seg).then((tm) => {
            if (!tm || R.curIdx !== item.idx) return;
            R.hl?.setSegment(item.idx, tm.spans);
            R.handle?.viewer?.setTrack(new VisemeTrack(tm.visemes));
          });
          const next = nextPlayable(player?.items ?? [], pos);
          if (next >= 0 && player) void ensure(R.segs.find((s) => s.idx === player?.items[next].idx));
          if (condition === "C4") {
            R.handle?.viewer?.attachAudio(audio);
            if (!R.greeted) {
              R.greeted = true;
              R.handle?.viewer?.playGesture("saludo-apertura");
            }
          }
        },
      });
      player.setRate(1);
      player.elements.forEach((a) => R.clocks.set(a, new AudioClock(a)));
      R.player = player;
    }
    (window as unknown as { __app?: unknown }).__app = { player, events, R, condition, id };

    const prefetchAll = async (segs: Seg[]) => {
      for (const s of segs) if (s.tts_ready && !dead) await ensure(s);
    };

    (async () => {
      try {
        if (condition === "C1") {
          const d = await fetchDetail(id);
          if (dead) return;
          const segs: Seg[] = d.parrafos.flat().map((s) => ({
            ...s,
            audio: null,
            duration_s: null,
            timings: null,
          }));
          R.segs = segs;
          setMeta(d as unknown as CatalogMeta);
          setView({ status: "ready", segs, notices: null, title: d.titulo_cni, modo: "lotes", complete: true });
          return;
        }
        void fetchMeta(id)
          .then((m) => !dead && setMeta(m))
          .catch(() => {});
        const m = await fetchManifest(id);
        if (dead) return;
        if (m) {
          R.segs = m.segments;
          player?.append(m.segments.map(toItem), true);
          player?.prime();
          setView({ status: "ready", segs: m.segments, notices: m.notices, title: m.titulo_cni, modo: "lotes", complete: true });
          if (sync) void prefetchAll(m.segments);
          return;
        }
        // Respaldo bajo demanda: el servidor entrega una oración por línea a medida que la genera
        setView((v) => ({ ...v, status: "ready", modo: "bajo-demanda" }));
        await streamSynthesis(
          id,
          {
            onMeta: (notices) => setView((v) => ({ ...v, notices })),
            onSegment: (seg) => {
              R.segs = [...R.segs, seg];
              player?.append([toItem(seg)], false);
              if (R.segs.length === 1) player?.prime();
              setView((v) => ({ ...v, segs: R.segs }));
              if (sync) void ensure(seg);
            },
            onDone: () => {
              player?.markComplete();
              setView((v) => ({ ...v, complete: true }));
            },
          },
          ac.signal,
        );
      } catch {
        if (!dead) setView((v) => ({ ...v, status: "error" }));
      }
    })();

    return () => {
      dead = true;
      ac.abort();
      player?.dispose();
      R.player = null;
      R.hl?.reset();
      R.activeClock = null;
      void events.emit("view-end", { mode: condition });
    };
  }, [id, condition]);

  // ------------------------------------------------------------ resaltado (C3, C4)
  useEffect(() => {
    if (!sync || view.status !== "ready" || !bodyRef.current) return;
    const hl = new Highlighter(bodyRef.current, () => R.activeClock?.now() ?? null);
    R.hl = hl;
    hl.start();
    return () => {
      hl.stop();
      R.hl = null;
    };
  }, [sync, view.status, id, condition]);

  // ------------------------------------------------------------ avatar (C4): carga diferida
  useEffect(() => {
    if (condition !== "C4") return;
    let dead = false;
    void import("../../avatar/AvatarPanel").then((m) => !dead && setPanel(() => m.AvatarPanel));
    return () => {
      dead = true;
      R.handle = null;
    };
  }, [condition]);

  // ------------------------------------------------------------ teclado
  useEffect(() => {
    if (!audioMode) return;
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement | null)?.tagName ?? "";
      if (["INPUT", "SELECT", "TEXTAREA", "BUTTON", "A"].includes(tag)) return;
      if (e.key === " ") {
        e.preventDefault();
        R.player?.toggle();
      } else if (e.key === "ArrowLeft") R.player?.repeatParagraph();
      else if (e.key === "ArrowRight") R.player?.nextParagraph();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [audioMode]);

  // ------------------------------------------------------------ acciones
  const onAvatarReady = (h: AvatarHandle) => {
    R.handle = h;
    setAvatarMode(h.mode);
    const p = R.player;
    if (h.viewer && p && p.cur >= 0) {
      h.viewer.attachAudio(p.audio);
      const tm = R.timings.get(R.curIdx);
      if (tm) h.viewer.setTrack(new VisemeTrack(tm.visemes));
    }
  };
  const onAvatarEvent = (e: DegradationEvent) =>
    void events.emit(e.type, { reason: e.reason ?? null, fps: e.fps ?? null, user_agent: e.userAgent });

  const doSave = async () => {
    setSave({ s: "saving", n: 0 });
    try {
      const n = await saveNews(id, audioMode);
      setSave({ s: "done", n });
      void events.emit("save-offline", { count: n });
    } catch {
      setSave({ s: "error", n: 0 });
    }
  };

  const playable = view.segs.filter((s) => s.tts_ready && s.audio);
  const pos = playable.findIndex((s) => s.idx === current);
  const blockedCount = view.segs.filter((s) => !s.tts_ready).length;
  const paragraphs = groupByParagraph(view.segs);
  const title = condition === "C2" ? t("news.numbered", { n: id }) : (meta?.titulo_cni ?? view.title);
  const showLabel = (s: Seg) => (audioMode && !s.tts_ready ? t("block.label") : null);

  return (
    <article class={`pres pres-${condition}`} data-condition={condition} aria-labelledby="pres-h">
      <a class="back" href="#/">
        {t("news.back")}
      </a>
      <h2 id="pres-h" lang={condition === "C2" ? undefined : "cni"}>
        {title}
      </h2>
      <Notices
        notices={audioMode ? view.notices : null}
        variant={meta?.variante_dialectal}
        avatar={condition === "C4"}
        pseudo={!!meta && meta.procedencia_tipo === "corpus_americasnlp"}
      />
      {view.status === "loading" && <p role="status">{t("news.loading")}</p>}
      {view.status === "error" && <p role="alert">{t("news.error")}</p>}
      {audioMode && view.modo === "bajo-demanda" && (
        <p class="mode" role="note">
          {t("news.mode.demanda")}
        </p>
      )}

      {condition === "C4" && (
        <div class="avatar-slot" data-avatar-mode={avatarMode ?? "cargando"}>
          {Panel && (
            <Panel vrmUrl={VRM_URL} fallbackImage={FALLBACK_IMG} width={320} height={320} onReady={onAvatarReady} onEvent={onAvatarEvent} />
          )}
          {avatarMode === "fijo" && <p class="mode">{t("avatar.fallback")}</p>}
        </div>
      )}

      {audioMode && (
        <div class="controls" role="group" aria-label={t("player.group")}>
          <button
            type="button"
            class="btn primary"
            data-testid="play"
            disabled={view.segs.length === 0}
            onClick={() => R.player?.toggle()}
          >
            {pstate === "playing" ? t("player.pause") : t("player.play")}
          </button>
          <button type="button" class="btn" data-testid="repeat" disabled={pstate === "idle"} onClick={() => R.player?.repeatParagraph()}>
            {t("player.repeat")}
          </button>
          <button type="button" class="btn" data-testid="next-par" disabled={pstate === "idle"} onClick={() => R.player?.nextParagraph()}>
            {t("player.nextParagraph")}
          </button>
          <fieldset class="rates">
            <legend>{t("player.rate")}</legend>
            {RATES.map((r) => (
              <label key={r} class="radio">
                <input
                  type="radio"
                  name="rate"
                  checked={rate === r}
                  onChange={() => {
                    setRate(r);
                    R.player?.setRate(r);
                  }}
                />
                {String(r).replace(".", ",")}×
              </label>
            ))}
          </fieldset>
          <p class="progress" role="status" data-testid="status">
            {pstate === "buffering"
              ? t("player.buffering")
              : pstate === "finished"
                ? t("player.finished")
                : pos >= 0
                  ? t("player.progress", { i: pos + 1, n: playable.length })
                  : ""}
          </p>
        </div>
      )}

      {condition === "C2" && blockedCount > 0 && (
        <p class="banner" role="note" data-testid="c2-blocked">
          {t("block.c2")}
        </p>
      )}

      {showText && view.status === "ready" && (
        <div
          class="body"
          ref={bodyRef}
          lang="cni"
          data-testid="body"
          style={`font-size:${TEXT_SCALES[settings.textSize]}em`}
        >
          {paragraphs.map((par) => (
            <p class="par" key={par[0].idx}>
              {par.map((s) => (
                <SegmentText key={s.idx} seg={s} timings={R.timings.get(s.idx)} label={showLabel(s)} now={blockedNow === s.idx} />
              ))}
            </p>
          ))}
        </div>
      )}

      <div class="offline">
        <button type="button" class="btn" onClick={doSave} disabled={save.s === "saving"} data-testid="save-offline">
          {save.s === "saving" ? t("offline.saving") : t("offline.save")}
        </button>
        <span role="status" data-testid="save-status">
          {save.s === "done" && t("offline.done", { n: save.n })}
          {save.s === "error" && t("offline.error")}
        </span>
      </div>
    </article>
  );
}
