import "./styles.css";
import "./noticiero.css";
import { mount } from "./App";

mount(document.getElementById("app") as HTMLElement);

// Service Worker (tarea 4.4). Solo con HTTPS o localhost; un fallo no afecta a la app.
if ("serviceWorker" in navigator && !new URLSearchParams(location.search).has("nosw")) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(() => {});
  });
}
