// Service Worker (modo sin conexión), cola de eventos y accesibilidad (axe-core).
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { ADMIN, clickPlay, openNews, waitFinished } from "./helpers";

test("sin conexión: tras guardar la noticia, la app abre y se reproduce completa desde la caché", async ({ page, context }) => {
  await openNews(page, 1, "C3", true);
  await page.evaluate(() => navigator.serviceWorker.ready);
  await expect.poll(() => page.evaluate(() => !!navigator.serviceWorker.controller), { timeout: 20_000 }).toBe(true);
  await expect(page.getByTestId("body")).toContainText("Tee otimimotena");
  await page.getByTestId("save-offline").click();
  await expect(page.getByTestId("save-status")).toContainText("Guardada", { timeout: 30_000 });

  await context.setOffline(true);
  await page.reload();
  await expect(page.getByRole("heading", { level: 2 })).toHaveText("PRUEBA-1 (ficticia)");
  await expect(page.getByTestId("body")).toContainText("Okantzi kemetsa.");
  await expect(page.getByTestId("play")).toBeEnabled();
  await clickPlay(page);
  await waitFinished(page);
  const types: string[] = await page.evaluate(() => (window as any).__app.events.emitted.map((e: { type: string }) => e.type));
  expect(types.filter((t) => t === "segment-end")).toHaveLength(3);

  // la lista también abre sin red y marca la noticia guardada
  await page.goto("/#/");
  await expect(page.locator(".news-list li").first()).toContainText("Guardada para uso sin conexión");
  await context.setOffline(false);
});

test("el Service Worker contesta 206 a las peticiones Range de audio desde la caché", async ({ page, context }) => {
  await openNews(page, 1, "C2", true);
  await expect.poll(() => page.evaluate(() => !!navigator.serviceWorker.controller), { timeout: 20_000 }).toBe(true);
  await page.getByTestId("save-offline").click();
  await expect(page.getByTestId("save-status")).toContainText("Guardada", { timeout: 30_000 });
  const url = await page.evaluate(async () => {
    const m = await (await fetch("/static/news/1/manifest.json")).json();
    return m.segments[0].audio.opus as string;
  });
  await context.setOffline(true);
  const r = await page.evaluate(async (u) => {
    const res = await fetch(u, { headers: { Range: "bytes=0-9" } });
    return { status: res.status, range: res.headers.get("content-range"), len: (await res.arrayBuffer()).byteLength };
  }, url);
  expect(r.status).toBe(206);
  expect(r.len).toBe(10);
  expect(r.range).toMatch(/^bytes 0-9\/\d+$/);
  await context.setOffline(false);
});

test("los eventos generados sin red se guardan y llegan al servidor al volver, sin duplicados", async ({ page, context }) => {
  await openNews(page, 1, "C3");
  await expect(page.getByTestId("body")).toBeVisible();
  const before = (await (await page.request.get("/api/events/summary", { headers: ADMIN })).json()).total as number;
  await context.setOffline(true);
  await page.evaluate(async () => {
    const q = (window as any).__app.events;
    await q.emit("pause", { idx: 1 });
    await q.emit("rate", { rate: 1.25 });
    await q.emit("play", { idx: 2 });
  });
  expect(await page.evaluate(() => (window as any).__app.events.pending())).toBeGreaterThanOrEqual(3);
  await context.setOffline(false);
  await expect
    .poll(async () => (await (await page.request.get("/api/events/summary", { headers: ADMIN })).json()).total as number, { timeout: 20_000 })
    .toBeGreaterThanOrEqual(before + 3);
  await expect.poll(() => page.evaluate(() => (window as any).__app.events.pending())).toBe(0);
  // reenviar lo mismo no duplica (event_id)
  const sent = await page.evaluate(() => (window as any).__app.events.emitted.slice(0, 5));
  const r = await page.request.post("/api/events", { data: { events: sent } });
  expect((await r.json()).nuevos).toBe(0);
});

const TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];
async function serious(page: import("@playwright/test").Page) {
  const r = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  return r.violations.filter((v) => v.impact === "critical" || v.impact === "serious").map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`);
}

test("accesibilidad (axe-core, WCAG 2.1 A/AA): sin violaciones críticas ni graves", async ({ page }) => {
  await page.goto("/?nosw=1");
  await expect(page.locator(".news-list li")).toHaveCount(3);
  expect(await serious(page), "lista").toEqual([]);
  await page.goto("/?nosw=1#/ajustes");
  await expect(page.getByRole("heading", { name: "Ajustes" })).toBeVisible();
  expect(await serious(page), "ajustes").toEqual([]);
  for (const c of ["C1", "C2", "C3"] as const) {
    await openNews(page, 2, c);
    await expect(page.getByRole("heading", { level: 2 })).toBeVisible();
    await expect(page.locator("article.pres")).toHaveAttribute("data-condition", c);
    await page.waitForTimeout(500);
    expect(await serious(page), c).toEqual([]);
  }
  await openNews(page, 2, "C4");
  await expect(page.locator("[data-avatar-mode]")).not.toHaveAttribute("data-avatar-mode", "cargando", { timeout: 60_000 });
  expect(await serious(page), "C4").toEqual([]);
});
