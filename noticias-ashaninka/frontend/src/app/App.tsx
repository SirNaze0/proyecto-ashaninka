import { render } from "preact";
import { useEffect, useMemo, useState } from "preact/hooks";
import { NewsList } from "./components/NewsList";
import { Presentation } from "./components/Presentation";
import { SettingsView } from "./components/Settings";
import { Ctx } from "./ctx";
import { EventQueue, IdbStore, MemoryStore, getSessionId } from "./events";
import { translate } from "./i18n";
import { type Route, parseHash } from "./router";
import { TEXT_SCALES, loadSettings, saveSettings } from "./settings";

function makeQueue(): EventQueue {
  const store = typeof indexedDB === "undefined" ? new MemoryStore() : new IdbStore();
  return new EventQueue(store, { sessionId: getSessionId() });
}

export function App() {
  const [route, setRoute] = useState<Route>(() => parseHash(location.hash));
  const [settings, setSettings] = useState(loadSettings);
  const [online, setOnline] = useState(navigator.onLine);
  const events = useMemo(makeQueue, []);

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

  useEffect(() => {
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
      online,
    }),
    [settings, events, online],
  );

  return (
    <Ctx.Provider value={ctx}>
      <a class="skip" href="#main">
        {ctx.t("skip")}
      </a>
      <header class="top">
        <a class="brand" href="#/">
          {ctx.t("appTitle")}
        </a>
        <nav aria-label="Principal">
          <a href="#/ajustes">{ctx.t("nav.settings")}</a>
        </nav>
      </header>
      <main id="main" tabIndex={-1} style={`--scale:${TEXT_SCALES[settings.textSize]}`}>
        {route.name === "list" && <NewsList />}
        {route.name === "settings" && <SettingsView />}
        {route.name === "news" && <Presentation key={`${route.id}-${route.condition}`} id={route.id} condition={route.condition} />}
      </main>
    </Ctx.Provider>
  );
}

export function mount(el: HTMLElement): void {
  render(<App />, el);
}
