// Visor reproducible de la Fase 3: carga una noticia ya sintetizada (modo por lotes), reproduce
// sus segmentos con el avatar y expone `window.__visor` para que Playwright mida y capture.
import { render } from "preact";
import { useEffect, useRef, useState } from "preact/hooks";
import { AvatarViewer } from "../avatar/viewer";
import { VisemeTrack, type VisemeBlock } from "../avatar/viseme-track";
import { createAvatar, type AvatarHandle } from "../avatar/create-avatar";
import { decide, probeFps, webglAvailable } from "../avatar/degradation";
import { calibrateMouth, captureSignal } from "../avatar/measure";

interface ManifestSegment {
  idx: number;
  text_orig: string;
  tts_ready: boolean;
  audio: { opus: string; mp3: string } | null;
  timings: string | null;
  duration_s: number | null;
}
interface Manifest {
  news_id: number;
  titulo_cni: string;
  notices: { synthetic_voice: string };
  segments: ManifestSegment[];
}

const params = new URLSearchParams(location.search);
const VRM_URL = params.get("vrm") ?? "/models/presentadora_provisional.vrm";
const FALLBACK = "/presentadora_fija.svg";
const FRAMING = params.get("framing") === "rostro" ? "rostro" : "busto";
const DETERMINISTIC = params.get("deterministic") === "1";
const SIZE = Number(params.get("size") ?? 360);

declare global {
  interface Window {
    __visor?: Record<string, unknown>;
  }
}

function Visor() {
  const host = useRef<HTMLDivElement>(null);
  const audio = useRef<HTMLAudioElement>(null);
  const [manifest, setManifest] = useState<Manifest | null>(null);
  const [handle, setHandle] = useState<AvatarHandle | null>(null);
  const [idx, setIdx] = useState(0);
  const [error, setError] = useState("");
  const newsId = params.get("news") ?? "1";

  useEffect(() => {
    fetch(`/static/news/${newsId}/manifest.json`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`manifiesto ${r.status}`))))
      .then(setManifest)
      .catch((e) => setError(String(e)));
  }, [newsId]);

  useEffect(() => {
    if (!host.current) return;
    createAvatar(host.current, {
      vrmUrl: VRM_URL,
      fallbackImage: FALLBACK,
      width: SIZE,
      height: SIZE,
      framing: FRAMING,
      deterministic: DETERMINISTIC,
    })
      .then(setHandle)
      .catch((e) => setError(String(e)));
  }, []);

  async function loadSegment(i: number) {
    const seg = manifest?.segments[i];
    if (!seg?.tts_ready || !seg.audio || !seg.timings || !audio.current) return false;
    const t = await (await fetch(seg.timings)).json();
    handle?.viewer?.setTrack(new VisemeTrack(t.visemes as VisemeBlock));
    audio.current.src = seg.audio.opus;
    setIdx(i);
    return true;
  }

  useEffect(() => {
    if (!handle || !audio.current) return;
    handle.viewer?.attachAudio(audio.current);
    window.__visor = {
      ready: true,
      manifest,
      loadSegment,
      viewer: handle.viewer,
      mode: handle.mode,
      events: handle.events,
      VisemeTrack,
      AvatarViewer,
      webglAvailable,
      probeFps,
      decide,
      calibrateMouth,
      captureSignal,
    };
  }, [handle, manifest]);

  const seg = manifest?.segments[idx];
  return (
    <main style="font-family:system-ui;max-width:760px;margin:1rem auto;padding:0 16px">
      <h1>{manifest?.titulo_cni ?? "Visor del avatar (Fase 3)"}</h1>
      <p style="color:#555">{manifest?.notices.synthetic_voice}</p>
      {error && <p role="alert">{error}</p>}
      <div ref={host} style={`width:${SIZE}px;height:${SIZE}px`} />
      <p aria-live="polite">{seg?.text_orig}</p>
      <audio ref={audio} controls style="width:100%" />
      <div>
        {manifest?.segments.map((s) => (
          <button key={s.idx} disabled={!s.tts_ready} onClick={() => loadSegment(s.idx)}>
            Oración {s.idx + 1}
          </button>
        ))}
        {["saludo-apertura", "asentir", "despedida"].map((g) => (
          <button key={g} onClick={() => handle?.viewer?.playGesture(g)}>
            {g}
          </button>
        ))}
      </div>
      <p>
        Modo: <b>{handle?.mode ?? "cargando…"}</b>
      </p>
    </main>
  );
}

render(<Visor />, document.getElementById("app") as HTMLElement);
