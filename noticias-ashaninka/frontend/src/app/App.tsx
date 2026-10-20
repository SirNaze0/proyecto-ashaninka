import { render } from "preact";
import { useEffect, useMemo, useState } from "preact/hooks";
import { ExperimentFlow } from "./components/ExperimentFlow";
import { NewsList } from "./components/NewsList";
import { Presentation } from "./components/Presentation";
import { SettingsView } from "./components/Settings";
import { TranslatePanel } from "./components/TranslatePanel";
import { Ctx } from "./ctx";
import { EventQueue, IdbStore, MemoryStore, getSessionId } from "./events";
import {
  ExperimentController,
  IdbKeyStore,
  IdbResponseStore,
  MemoryKeyStore,
  MemoryResponseStore,
  ResponseQueue,
  guardia,
} from "./experiment";
import { translate } from "./i18n";
import { Masthead } from "./components/Masthead";
import { Newsroom } from "./components/Newsroom";
import { type Role, puedeVerRedaccion } from "./role";
import { NEWS_HREF, type Route, newsHref, parseHash } from "./router";
import { TEXT_SCALES, loadSettings, saveSettings } from "./settings";

function makeQueue(): EventQueue {
  const store = typeof indexedDB === "undefined" ? new MemoryStore() : new IdbStore();
  return new EventQueue(store, { sessionId: getSessionId() });
}

function makeExperiment(events: EventQueue): ExperimentController {
  const idb = typeof indexedDB !== "undefined";
  return new ExperimentController(
    idb ? new IdbKeyStore() : new MemoryKeyStore(),
    new ResponseQueue(idb ? new IdbResponseStore() : new MemoryResponseStore()),
    events,
  );
}

export function App() {
  const [route, setRoute] = useState<Route>(() => parseHash(location.hash));
  const [settings, setSettings] = useState(loadSettings);
  const [online, setOnline] = useState(navigator.onLine);
  const events = useMemo(makeQueue, []);
  const experiment = useMemo(() => makeExperiment(events), [events]);
  const [, setExpTick] = useState(0);
  // Rol de la interfaz; el token vive solo en memoria (ver role.ts)
  const [role, setRole] = useState<Role>("ciudadano");
  const [token, setToken] = useState<string | null>(null);
  const [studioId, setStudioId] = useState<number | null>(null);

  useEffect(() => {
    const onHash = () => setRoute(parseHash(location.hash));
    const on = () => {
      setOnline(true);
      // al volver la red se vacía la cola de eventos acumulada sin conexión
      void events.flush().then((n) => {
        if (n > 0) void events.emit("offline-sync", { count: n });
      });
    };
    const off = () => setOnline(false);
    const hidden = () => document.visibilityState === "hidden" && void events.flush();
    window.addEventListener("hashchange", onHash);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    document.addEventListener("visibilitychange", hidden);
    void events.flush();
    return () => {
      window.removeEventListener("hashchange", onHash);
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
      document.removeEventListener("visibilitychange", hidden);
    };
  }, [events]);

  // Fase 5: estado de la sesión experimental (IndexedDB) y su cola de respuestas
  useEffect(() => {
    (window as unknown as { __exp?: unknown }).__exp = experiment;
    const unsub = experiment.subscribe(() => setExpTick((n) => n + 1));
    void experiment.load().then(() => void experiment.responses.flush());
    const on = () => void experiment.responses.flush();
    window.addEventListener("online", on);
    return () => {
      unsub();
      window.removeEventListener("online", on);
    };
  }, [experiment]);

  // Con una sesión activa solo existe la ruta de la fase actual: no se puede cambiar la condición
  // (ni por el selector ni editando ?c= en la URL) ni salir a la lista.
  useEffect(() => {
    if (!experiment.loaded) return;
    const destino = guardia(experiment.state, location.hash);
    if (destino) location.replace(destino);
  }, [route, experiment.loaded, experiment.state]);

  useEffect(() => {
    if (route.name === "news") setStudioId(route.id);
  }, [route]);

  // La sala de redacción solo existe para el administrador verificado
  const redaccionOk = puedeVerRedaccion(role, token);
  useEffect(() => {
    if (route.name === "newsroom" && !redaccionOk) location.replace(NEWS_HREF);
  }, [route, redaccionOk]);

  useEffect(() => {
    document.documentElement.dataset.theme = settings.theme === "auto" ? "" : settings.theme;
    document.documentElement.lang = "es"; // la interfaz cae al castellano mientras cni.json esté pendiente
    saveSettings(settings);
  }, [settings]);

  const ctx = useMemo(
    () => ({
      t: (key: string, vars?: Record<string, string | number>) => translate(settings.lang, key, vars),
      lang: settings.lang,
      settings,
      setSettings,
      events,
      experiment,
      online,
      role,
      token,
    }),
    [settings, events, experiment, online, role, token],
  );

  const enSesion = experiment.state?.estado === "activa";

  return (
    <Ctx.Provider value={ctx}>
      <a class="skip" href="#main">
        {ctx.t("skip")}
      </a>
      <Masthead
        route={route}
        enSesion={enSesion}
        role={role}
        token={token}
        onRole={setRole}
        onToken={setToken}
        studioHref={studioId === null ? null : newsHref(studioId, "C4")}
      />
      <main id="main" tabIndex={-1} style={`--scale:${TEXT_SCALES[settings.textSize]}`}>
        {route.name === "translate" && <TranslatePanel />}
        {route.name === "list" && <NewsList />}
        {route.name === "settings" && <SettingsView />}
        {route.name === "newsroom" && redaccionOk && <Newsroom />}
        {route.name === "experiment" && <ExperimentFlow route={route} />}
        {route.name === "news" && <Presentation key={`${route.id}-${route.condition}`} id={route.id} condition={route.condition} />}
      </main>
      {!enSesion && (
        <footer class="site-foot">
          <p>{ctx.t("footer.text")}</p>
        </footer>
      )}
    </Ctx.Provider>
  );
}

export function mount(el: HTMLElement): void {
  render(<App />, el);
}
