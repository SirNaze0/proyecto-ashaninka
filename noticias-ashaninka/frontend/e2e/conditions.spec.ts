// Condiciones C1–C4, resaltado sincronizado, segmentos bloqueados y respaldo bajo demanda.
import { expect, test } from "@playwright/test";
import { clickPlay, dedupe, emittedTypes, expectedHighlights, openNews, recordHighlights, waitFinished } from "./helpers";

const count = (xs: string[], t: string) => xs.filter((x) => x === t).length;

test("la lista muestra las noticias y enlaza con la condición elegida", async ({ page }) => {
  await page.goto("/?nosw=1");
  await expect(page.locator(".news-list li")).toHaveCount(3);
  await page.getByLabel("Modo de presentación").selectOption("C2");
  await expect(page.locator(".news-link").first()).toHaveAttribute("href", "#/noticia/1?c=C2");
  await page.locator(".news-link").first().click();
  await expect(page.getByRole("heading", { level: 2 })).toHaveText("Noticia 1");
});

test("C1: solo texto, sin controles de voz y sin ninguna petición de audio ni de avatar", async ({ page }) => {
  const reqs: string[] = [];
  page.on("request", (r) => reqs.push(new URL(r.url()).pathname));
  await openNews(page, 1, "C1");
  await expect(page.getByTestId("body")).toContainText("Tee otimimotena katsini");
  await expect(page.getByTestId("body")).toContainText("Tzimatsi kitaiteri");
  await expect(page.getByTestId("play")).toHaveCount(0);
  await page.waitForTimeout(500);
  expect(reqs.filter((p) => p.startsWith("/static/") || p.startsWith("/models/") || p.includes("three") || p.includes("viewer"))).toEqual([]);
  await expect(page.locator("canvas")).toHaveCount(0);
});

test("C2: solo voz, con aviso de voz sintética, sin texto en asháninka y sin avatar", async ({ page }) => {
  await openNews(page, 1, "C2");
  await expect(page.getByRole("heading", { level: 2 })).toHaveText("Noticia 1");
  await expect(page.getByText("Voz sintética generada por computadora")).toBeVisible();
  await expect(page.getByText("Licencia de la voz:")).toBeVisible();
  await expect(page.getByTestId("body")).toHaveCount(0);
  await expect(page.locator("canvas")).toHaveCount(0);
  await expect(page.locator("body")).not.toContainText("otimimotena");
  await clickPlay(page);
  await waitFinished(page);
  const ev = await emittedTypes(page);
  expect(count(ev, "segment-start")).toBe(3);
  expect(count(ev, "segment-end")).toBe(3);
  await expect(page.locator("body")).not.toContainText("otimimotena");
});

test("C3: resalta cada palabra, en orden y sin omitir ninguna, mientras suena el audio", async ({ page }) => {
  await openNews(page, 1, "C3");
  await expect(page.getByTestId("body")).toContainText("Tee otimimotena");
  // espera a que los 3 segmentos tengan sus fragmentos dibujados
  await expect(page.locator("[data-span]").first()).toBeAttached();
  await recordHighlights(page);
  await clickPlay(page);
  await waitFinished(page);
  const seq = dedupe(await page.evaluate(() => (window as any).__seq as string[]));
  const expected = await expectedHighlights(page, 1);
  expect(expected.length).toBeGreaterThanOrEqual(6);
  expect(seq).toEqual(expected);
  // el desfase del resaltado frente al reloj del audio queda registrado (medición formal: eval/fase4)
  const log = await page.evaluate(() => (window as any).__app.R.hl?.log ?? []);
  expect(log.length).toBe(expected.length);
  for (const c of log) expect(Math.abs(c.clock_t - c.t0)).toBeLessThan(0.15);
  // el texto original no cambió
  await expect(page.getByTestId("body")).toContainText("Okantzi kemetsa.");
});

test("C3 con un segmento bloqueado: se ve como solo texto y la reproducción no se corta", async ({ page }) => {
  await openNews(page, 2, "C3");
  const blocked = page.locator("[data-blocked='1']");
  await expect(blocked).toHaveCount(1);
  await expect(blocked).toContainText("Irotake Pablo Lima ayer en Satipo");
  await expect(blocked).toContainText("Solo texto: este fragmento no tiene audio");
  await clickPlay(page);
  await waitFinished(page);
  const ev = await emittedTypes(page);
  expect(count(ev, "segment-start")).toBe(2); // los dos con audio, antes y después del bloqueado
  expect(count(ev, "blocked-shown")).toBe(1);
  expect(ev.indexOf("blocked-shown")).toBeGreaterThan(ev.indexOf("segment-end"));
  expect(ev.lastIndexOf("segment-start")).toBeGreaterThan(ev.indexOf("blocked-shown"));
});

test("C2 con un segmento bloqueado: se omite con un aviso y continúa", async ({ page }) => {
  await openNews(page, 2, "C2");
  await expect(page.getByTestId("c2-blocked")).toContainText("no tiene audio");
  await clickPlay(page);
  await waitFinished(page);
  expect(count(await emittedTypes(page), "segment-start")).toBe(2);
  await expect(page.locator("body")).not.toContainText("Irotake");
});

test("respaldo bajo demanda: sin manifiesto se reproduce el stream NDJSON", async ({ page }) => {
  await openNews(page, 3, "C3");
  await expect(page.getByText("Audio generado al momento")).toBeVisible();
  await expect(page.getByTestId("play")).toBeEnabled({ timeout: 30_000 });
  await clickPlay(page);
  await waitFinished(page);
  const ev = await emittedTypes(page);
  expect(count(ev, "segment-start")).toBe(2);
  await expect(page.getByTestId("body")).toContainText("Okantzi kemetsa.");
});

test("controles: velocidad, repetir párrafo y teclado", async ({ page }) => {
  await openNews(page, 1, "C3");
  await clickPlay(page);
  await expect(page.getByTestId("status")).toContainText("Oración 1 de 3");
  await page.getByLabel("1,25×").check();
  await expect.poll(() => page.evaluate(() => (window as any).__app.player.audio.playbackRate)).toBe(1.25);
  await page.locator("body").click({ position: { x: 5, y: 5 } }); // el foco sale del radio
  await page.keyboard.press("Space"); // pausa
  await expect(page.getByTestId("play")).toHaveText("Reproducir");
  await page.keyboard.press("Space"); // reanuda
  await expect(page.getByTestId("play")).toHaveText("Pausar");
  await page.getByTestId("repeat").click();
  expect(await emittedTypes(page)).toContain("repeat-paragraph");
  await waitFinished(page);
});

test("ajustes: tamaño de texto y aviso de que el asháninka está pendiente", async ({ page }) => {
  await page.goto("/?nosw=1#/ajustes");
  await page.getByLabel("Extra grande").check();
  await page.getByLabel("Idioma de la interfaz").selectOption("cni");
  await expect(page.getByText("pendientes de traducción por un hablante")).toBeVisible();
  await openNews(page, 1, "C1");
  const fs = await page.getByTestId("body").evaluate((e) => getComputedStyle(e).fontSize);
  expect(parseFloat(fs)).toBeGreaterThanOrEqual(30); // 2× de 16 px
});
