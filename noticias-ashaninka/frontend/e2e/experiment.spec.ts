// Fase 5: sesión experimental completa en Chromium real (servidor con --experimento).
// Consentimiento → 4 bloques en el orden de Williams → cuestionarios → final → exportación.
import AxeBuilder from "@axe-core/playwright";
import { type Page, expect, test } from "@playwright/test";
import { inflateRawSync } from "node:zlib";
import { ADMIN, clickPlay, vigilarCsp, waitFinished } from "./helpers";

// Material del servidor: noticias 1-4 (la 5 tiene un bloqueado y el selector la descarta)
const NEWS = [1, 2, 3, 4];

// Misma tabla que backend/app/experiment/latin.py (el vector común lo prueba vitest)
const WILLIAMS = [
  ["C1", "C2", "C4", "C3"],
  ["C2", "C3", "C1", "C4"],
  ["C3", "C4", "C2", "C1"],
  ["C4", "C1", "C3", "C2"],
];
const esperado = (i: number) => {
  const d = Math.floor(i / 4) % 4;
  return WILLIAMS[i % 4].map((c, k) => ({ c, news: NEWS[(k + d) % 4] }));
};

/** Lee un ZIP simple (entradas con tamaños en la cabecera local, como las escribe Python). */
function leerZip(buf: Buffer): Record<string, string> {
  const out: Record<string, string> = {};
  let p = 0;
  while (buf.readUInt32LE(p) === 0x04034b50) {
    const method = buf.readUInt16LE(p + 8);
    const csize = buf.readUInt32LE(p + 18);
    const nlen = buf.readUInt16LE(p + 26);
    const xlen = buf.readUInt16LE(p + 28);
    const name = buf.subarray(p + 30, p + 30 + nlen).toString("utf8");
    const data = buf.subarray(p + 30 + nlen + xlen, p + 30 + nlen + xlen + csize);
    out[name] = (method === 8 ? inflateRawSync(data) : data).toString("utf8");
    p += 30 + nlen + xlen + csize;
  }
  return out;
}

function csv(texto: string): Record<string, string>[] {
  const [cab, ...filas] = texto.trim().split("\n");
  const cols = cab.split(",");
  return filas.map((f) => Object.fromEntries(f.split(",").map((v, i) => [cols[i], v])));
}

async function iniciar(page: Page, code: string) {
  await page.goto("/?nosw=1#/experimento");
  await expect(page.getByTestId("exp-consent")).toBeVisible();
  await page.getByTestId("exp-code-input").fill(code);
  await page.getByTestId("exp-accept").check();
  await page.getByTestId("exp-start").click();
}

async function responderPost(page: Page) {
  for (const [id, v] of [["comp_1", 1], ["comp_2", 0], ["comp_3", 1], ["comp_4", 1], ["esfuerzo", 5], ["acep_facilidad", 4], ["acep_agrado", 3], ["acep_confianza", 5]] as const)
    await page.getByTestId(`q-${id}-${v}`).check();
}

async function verBloque(page: Page, k: number, cond: string) {
  await expect(page).toHaveURL(new RegExp(`#/experimento/bloque/${k}$`));
  await expect(page.getByTestId("exp-progress")).toHaveText(`Noticia ${k + 1} de 4`);
  await expect(page.locator("article.pres")).toHaveAttribute("data-condition", cond);
  await expect(page.getByLabel("Modo de presentación")).toHaveCount(0); // sin selector de condición
  await expect(page.getByTestId("exp-continue")).toBeDisabled();
  // el participante no puede cambiar la condición ni salir, ni por la URL ni con «atrás»
  // (el bloque se reinicia: se vuelve a presentar desde el principio)
  await page.evaluate(() => (location.hash = "#/noticia/1?c=C1"));
  await expect(page).toHaveURL(new RegExp(`#/experimento/bloque/${k}$`));
  await page.evaluate(() => (location.hash = "#/"));
  await expect(page).toHaveURL(new RegExp(`#/experimento/bloque/${k}$`));
  await expect(page.locator("article.pres")).toHaveAttribute("data-condition", cond);
  await expect(page.getByTestId("exp-progress")).toHaveText(`Noticia ${k + 1} de 4`);
  if (cond === "C1") {
    await expect(page.getByTestId("body")).toContainText("katsini");
    await page.getByTestId("read-done").click();
  } else {
    await clickPlay(page);
    await waitFinished(page);
  }
  await expect(page.getByTestId("exp-continue")).toBeEnabled();
}

test("sesión completa: 4 condiciones en orden de Williams, cuestionarios, cierre y exportación", async ({ page, context }) => {
  const verificarCsp = await vigilarCsp(page);
  await iniciar(page, "P007"); // índice 6: fila 2 de Williams, noticias rotadas 1
  const seq = esperado(6);
  expect(seq.map((s) => s.c)).toEqual(["C3", "C4", "C2", "C1"]);

  for (let k = 0; k < 4; k++) {
    await verBloque(page, k, seq[k].c);

    await page.getByTestId("exp-continue").click();
    await expect(page).toHaveURL(new RegExp(`#/experimento/cuestionario/${k}$`));
    // enviar vacío no avanza
    await page.getByTestId("q-send").click();
    await expect(page.getByTestId("q-error")).toBeVisible();
    await expect(page).toHaveURL(new RegExp(`#/experimento/cuestionario/${k}$`));
    if (k === 0) {
      const axe = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
      expect(axe.violations.filter((v) => v.impact === "critical" || v.impact === "serious")).toEqual([]);
    }
    await responderPost(page);
    await page.getByTestId("q-send").click();
    if (k === 1) {
      // recarga a mitad de la sesión: se reanuda en el mismo lugar con la misma condición
      await expect(page).toHaveURL(new RegExp("#/experimento/bloque/2$"));
      await page.reload();
      await expect(page).toHaveURL(new RegExp("#/experimento/bloque/2$"));
      await expect(page.locator("article.pres")).toHaveAttribute("data-condition", seq[2].c);
      await expect(page.getByTestId("exp-code")).toHaveText("Participante P007");
    }
  }

  // cuestionario final, sin conexión: las respuestas esperan en la cola y se envían al volver la red
  await expect(page).toHaveURL(/#\/experimento\/final$/);
  await context.setOffline(true);
  await page.getByTestId("q-rank_C1-1").check();
  for (const c of ["C2", "C3", "C4"]) await page.getByTestId(`q-rank_${c}-1`).check();
  for (const [id, v] of [["variante", "otra"], ["edad_rango", "30-44"], ["alfabetizacion", "lee_bien"], ["familiaridad_tec", "media"]] as const)
    await page.getByTestId(`q-${id}-${v}`).check();
  await page.getByTestId("q-send").click(); // ranking repetido: no avanza
  await expect(page.getByTestId("q-rank_C1-error")).toBeVisible();
  await expect(page).toHaveURL(/#\/experimento\/final$/);
  for (const [c, v] of [["C1", 4], ["C2", 3], ["C3", 1], ["C4", 2]] as const) await page.getByTestId(`q-rank_${c}-${v}`).check();
  await page.getByTestId("q-comentario").fill("Me gustó la voz.");
  await page.getByTestId("q-send").click();
  await expect(page).toHaveURL(/#\/experimento\/fin$/);
  await expect(page.getByTestId("exp-end-status")).toHaveAttribute("data-estado", "pendiente");
  await context.setOffline(false);
  await expect(page.getByTestId("exp-end-status")).toHaveAttribute("data-estado", "ok", { timeout: 30_000 });
  await expect(page.getByTestId("exp-end-status")).toHaveText("Sus respuestas se enviaron completas.");

  // terminada la sesión la navegación vuelve a ser libre
  await page.goto("/?nosw=1#/noticias");
  await expect(page.locator(".news-list li").first()).toBeVisible();

  // exportación: eventos y respuestas llegaron al servidor (los eventos salen por la cola, con espera)
  let tablas: Record<string, string> = {};
  await expect
    .poll(async () => {
      const r = await page.request.get("/api/experiment/export", { headers: ADMIN });
      tablas = leerZip(await r.body());
      const bl = csv(tablas["bloques.csv"] ?? "");
      return bl.length === 4 && bl.every((b) => Number(b.t_pantalla_ms) > 0 && b.completado === "1");
    }, { timeout: 30_000 })
    .toBe(true);

  const bloques = csv(tablas["bloques.csv"]).sort((a, b) => Number(a.posicion) - Number(b.posicion));
  expect(bloques.map((b) => b.condicion)).toEqual(seq.map((s) => s.c));
  expect(bloques.map((b) => Number(b.news_id))).toEqual(seq.map((s) => s.news));
  expect(bloques.every((b) => b.participante === "P007" && b.piloto === "0")).toBe(true);
  expect(bloques.map((b) => [Number(b.comprension), Number(b.esfuerzo), Number(b.aceptabilidad)])).toEqual(Array(4).fill([0.75, 5, 4]));
  for (const b of bloques) {
    if (b.condicion === "C1") expect(Number(b.t_escucha_ms)).toBe(0);
    else expect(Number(b.t_escucha_ms)).toBeGreaterThan(0);
  }
  const ses = csv(tablas["sesiones.csv"]);
  expect(ses).toHaveLength(1);
  expect(ses[0]).toMatchObject({ participante: "P007", estado: "completa", bloques_completados: "4", variante: "otra", rank_C3: "1" });
  expect(tablas["eventos.csv"].split("\n")[0]).not.toContain("session_id");
  const manifest = JSON.parse(tablas["manifest.json"]);
  expect(manifest.incluye_piloto).toBe(false);
  await verificarCsp(); // la CSP del servidor no bloqueó nada en todo el recorrido
  // sin token la exportación está cerrada
  expect((await page.request.get("/api/experiment/export")).status()).toBe(403);
});

test("abandonar pide confirmación, registra el abandono y libera la navegación", async ({ page }) => {
  await iniciar(page, "P010");
  await expect(page).toHaveURL(/#\/experimento\/bloque\/0$/);
  await page.getByTestId("exp-abandon").click();
  await expect(page.getByRole("alertdialog")).toBeVisible();
  await page.getByTestId("exp-abandon-yes").click();
  await expect(page).toHaveURL(/#\/$/);
  // #/ es la pantalla de traducción (entrada principal); la lista sigue accesible
  await expect(page.getByTestId("tr-pending")).toBeVisible();
  await page.goto("/?nosw=1#/noticias");
  await expect(page.locator(".news-list li").first()).toBeVisible();
  const r = await (await page.request.get("/api/experiment/sessions/P010")).json();
  expect(r.estado).toBe("abandonada");
});

test("el consentimiento es obligatorio y el código se valida; uno ya usado en otro dispositivo se rechaza", async ({ page }) => {
  await page.goto("/?nosw=1#/experimento");
  await expect(page.getByTestId("consent-pending")).toContainText("PENDIENTE-COMITE-ETICA");
  await expect(page.getByTestId("exp-start")).toBeDisabled();
  await page.getByTestId("exp-code-input").fill("Juan Perez");
  await page.getByTestId("exp-accept").check();
  await page.getByTestId("exp-start").click();
  await expect(page.getByTestId("exp-error")).toContainText("código no es válido");
  // el mismo código ya fue tomado por otro dispositivo
  const otro = await page.request.post("/api/experiment/sessions", {
    data: { participant_code: "P011", session_id: "a".repeat(32), consent: true, consent_version: "x" },
  });
  expect(otro.status()).toBe(201);
  await page.getByTestId("exp-code-input").fill("P011");
  await page.getByTestId("exp-start").click();
  await expect(page.getByTestId("exp-error")).toContainText("ya está en uso");
  const axe = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(axe.violations.filter((v) => v.impact === "critical" || v.impact === "serious")).toEqual([]);
});
