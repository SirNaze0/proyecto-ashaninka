import { expect, type Page } from "@playwright/test";

export type Cond = "C1" | "C2" | "C3" | "C4";

/** Token administrativo del servidor de pruebas (scripts/e2e_server.py): /api/events/summary lo exige. */
export const ADMIN = { "x-admin-token": "e2e-admin-token-0123456789" };

/** Abre una noticia en una condición. `sw=false` evita registrar el Service Worker. */
export async function openNews(page: Page, id: number, c: Cond, sw = false) {
  await page.goto(`/${sw ? "" : "?nosw=1"}#/noticia/${id}?c=${c}`);
}

export async function clickPlay(page: Page) {
  const play = page.getByTestId("play");
  await expect(play).toBeEnabled();
  await play.click();
}

export async function waitFinished(page: Page, timeout = 45_000) {
  await expect(page.getByTestId("status")).toHaveText("Fin de la noticia", { timeout });
}

/** Tipos de evento emitidos por la página, en orden. */
export async function emittedTypes(page: Page): Promise<string[]> {
  return page.evaluate(() => (window as any).__app.events.emitted.map((e: { type: string }) => e.type));
}

/** Registra en `window.__seq` cada fragmento que recibe la clase `hl` ("seg:span"). */
export async function recordHighlights(page: Page) {
  await page.evaluate(() => {
    const w = window as any;
    w.__seq = [];
    new MutationObserver((ms) => {
      for (const m of ms) {
        const el = m.target as HTMLElement;
        if (el.classList?.contains("hl")) w.__seq.push(`${el.closest("[data-seg]")?.getAttribute("data-seg")}:${el.getAttribute("data-span")}`);
      }
    }).observe(document.body, { subtree: true, attributes: true, attributeFilter: ["class"] });
  });
}

/** Fragmentos que deben resaltarse, según los tiempos del servidor (mismo criterio que highlight.ts). */
export async function expectedHighlights(page: Page, id: number): Promise<string[]> {
  const m = await (await page.request.get(`/static/news/${id}/manifest.json`)).json();
  const out: string[] = [];
  for (const s of m.segments) {
    if (!s.timings) continue;
    const tm = await (await page.request.get(s.timings)).json();
    tm.spans.forEach((sp: { orig_text: string; t0: number; t1: number }, i: number) => {
      if (sp.t1 > sp.t0 && /[\p{L}\p{N}]/u.test(sp.orig_text)) out.push(`${s.idx}:${i}`);
    });
  }
  return out;
}

export function dedupe(seq: string[]): string[] {
  return seq.filter((x, i) => x !== seq[i - 1]);
}

/** Fase 6: registra violaciones de CSP (evento del navegador y errores de consola); `await` del resultado las exige vacías. */
export async function vigilarCsp(page: Page) {
  const consola: string[] = [];
  page.on("console", (m) => {
    if (/content security policy|refused to/i.test(m.text())) consola.push(m.text());
  });
  await page.addInitScript(() => {
    (window as any).__csp = [];
    document.addEventListener("securitypolicyviolation", (e) =>
      (window as any).__csp.push(`${e.violatedDirective} ${e.blockedURI}`),
    );
  });
  return async () => {
    const dom = await page.evaluate(() => (window as any).__csp as string[]);
    expect([...dom, ...consola]).toEqual([]);
  };
}
