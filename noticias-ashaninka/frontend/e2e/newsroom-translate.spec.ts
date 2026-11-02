// Traducción BiTAM en la sala de redacción (MejoraEIntegracion, Fase 3). El servicio BiTAM no corre
// en E2E: se simulan `/api/news/translate` y su estado con page.route. Las cadenas "cni" son
// MARCADORES de prueba evidentes, no asháninka (nunca se inventa texto en la lengua).
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Route } from "@playwright/test";

const TOKEN = "e2e-admin-token-0123456789";

const DISPONIBLE = { disponible: true, motivo: null, modelo: "BiTAM es2cni", version: "bitam_v5_run_e2e", dispositivo: "cuda:0", fake: false };
const BORRADOR = {
  titulo_cni: "PRUEBA-CNI-TITULO Satipo",
  paragraphs: ["PRUEBA-CNI-1 PRUEBA-CNI-2", "PRUEBA-CNI-3"],
  oraciones: [
    { parrafo: -1, es: "Lluvias en Satipo", cni_modelo: "prueba-cni-titulo satipo", cni: "PRUEBA-CNI-TITULO Satipo" },
    { parrafo: 0, es: "Llovió mucho.", cni_modelo: "prueba-cni-1", cni: "PRUEBA-CNI-1" },
    { parrafo: 0, es: "El río creció.", cni_modelo: "prueba-cni-2", cni: "PRUEBA-CNI-2" },
    { parrafo: 1, es: "No hay heridos.", cni_modelo: "prueba-cni-3", cni: "PRUEBA-CNI-3" },
  ],
  procedencia: { tipo: "traduccion_automatica", sistema: "BiTAM es2cni", version: "bitam_v5_run_e2e", revisado_por_hablante: false, revisor_id: null },
  modelo: "BiTAM es2cni",
  segundos: 2.5,
  avisos: ["Traducción automática (BiTAM, chrF++ ≈ 25): es un borrador; debe revisarla un hablante antes de usarla en el experimento."],
};

const fulfill = (route: Route, status: number, body: unknown) =>
  route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });

async function abrirRedaccion(page: Page, estado: unknown = DISPONIBLE) {
  await page.route("**/api/news/translate/status", (r) => fulfill(r, 200, estado));
  await page.goto("/?nosw=1");
  await page.getByTestId("role-admin").click();
  await page.getByTestId("token-input").fill(TOKEN);
  await page.getByTestId("token-submit").click();
  await expect(page.getByTestId("token-ok")).toBeVisible();
  await page.getByRole("navigation", { name: "Principal" }).getByRole("link", { name: "Sala de redacción" }).click();
  await expect(page.getByTestId("room-translate-card")).toBeVisible();
}

async function escribirCastellano(page: Page) {
  await page.getByTestId("room-es-title").fill("Lluvias en Satipo");
  await page.getByTestId("room-es-body").fill("Llovió mucho. El río creció.\n\nNo hay heridos.");
}

test("traduce: rellena el borrador, muestra pares y aviso, y la procedencia queda automática no revisada", async ({ page }) => {
  let peticion: { titulo_es?: string; cuerpo_es?: string; token?: string } = {};
  await page.route("**/api/news/translate", async (route) => {
    peticion = { ...(route.request().postDataJSON() as object), token: route.request().headers()["x-admin-token"] };
    await fulfill(route, 200, BORRADOR);
  });
  await abrirRedaccion(page);
  await expect(page.getByTestId("room-tr-ready")).toContainText("cuda:0");
  await escribirCastellano(page);
  await page.getByTestId("room-translate").click();

  await expect(page.getByTestId("room-tr-result")).toContainText("4 oraciones");
  expect(peticion).toEqual({ titulo_es: "Lluvias en Satipo", cuerpo_es: "Llovió mucho. El río creció.\n\nNo hay heridos.", token: TOKEN });
  await expect(page.getByTestId("room-title")).toHaveValue("PRUEBA-CNI-TITULO Satipo");
  await expect(page.getByTestId("room-par-0")).toHaveValue("PRUEBA-CNI-1 PRUEBA-CNI-2");
  await expect(page.getByTestId("room-par-1")).toHaveValue("PRUEBA-CNI-3");
  await expect(page.getByTestId("room-prov-tipo")).toHaveValue("traduccion_automatica");
  await expect(page.getByLabel("Revisada por un hablante")).not.toBeChecked();
  await expect(page.getByTestId("room-tr-aviso")).toContainText("hablante");

  await page.getByTestId("room-tr-pairs").locator("summary").click();
  await expect(page.getByTestId("room-tr-pairs").locator("tbody tr")).toHaveCount(4);
  await expect(page.getByTestId("room-tr-pairs")).toContainText("El río creció.");

  // el borrador sigue siendo editable y avisa si el castellano cambia después de traducir
  await page.getByTestId("room-par-1").fill("PRUEBA-CNI-3 corregido");
  await expect(page.getByTestId("room-tr-stale")).toHaveCount(0);
  await page.getByTestId("room-es-body").fill("Otra noticia distinta.");
  await expect(page.getByTestId("room-tr-stale")).toBeVisible();
});

test("no pisa texto en asháninka sin confirmar", async ({ page }) => {
  let llamadas = 0;
  await page.route("**/api/news/translate", (route) => {
    llamadas++;
    return fulfill(route, 200, BORRADOR);
  });
  await abrirRedaccion(page);
  await page.getByTestId("room-title").fill("TEXTO-PREVIO");
  await escribirCastellano(page);
  page.once("dialog", (d) => d.dismiss());
  await page.getByTestId("room-translate").click();
  await expect(page.getByTestId("room-title")).toHaveValue("TEXTO-PREVIO");
  expect(llamadas).toBe(0);
  page.once("dialog", (d) => d.accept());
  await page.getByTestId("room-translate").click();
  await expect(page.getByTestId("room-title")).toHaveValue("PRUEBA-CNI-TITULO Satipo");
  expect(llamadas).toBe(1);
});

for (const [status, detalle, esperado] of [
  [503, "Traductor no disponible: no se pudo conectar con el traductor", "no está disponible"],
  [422, "el cuerpo supera 8000 caracteres", "demasiado largo"],
  [502, "Error del traductor: el traductor respondió 500", "falló"],
  [403, "token", "rechazó el token"],
] as const) {
  test(`error ${status} visible y el borrador queda intacto`, async ({ page }) => {
    await page.route("**/api/news/translate", (route) => fulfill(route, status, { detail: detalle }));
    await abrirRedaccion(page);
    await escribirCastellano(page);
    await page.getByTestId("room-translate").click();
    await expect(page.getByTestId("room-tr-error")).toContainText(esperado);
    await expect(page.getByTestId("room-title")).toHaveValue("");
    await expect(page.getByTestId("room-tr-result")).toHaveCount(0);
  });
}

test("traductor no disponible: lo declara, desactiva el botón y permite volver a comprobar", async ({ page }) => {
  await abrirRedaccion(page, { disponible: false, motivo: "traductor no configurado: defina NA_TRANSLATOR_URL" });
  await expect(page.getByTestId("room-pending")).toContainText("NA_TRANSLATOR_URL");
  await expect(page.getByTestId("room-translate")).toBeDisabled();
  await page.unroute("**/api/news/translate/status");
  await page.route("**/api/news/translate/status", (r) => fulfill(r, 200, DISPONIBLE));
  await page.getByTestId("room-tr-recheck").click();
  await expect(page.getByTestId("room-tr-ready")).toBeVisible();
  await expect(page.getByTestId("room-translate")).toBeEnabled();
});

test("cancelar una traducción en curso", async ({ page }) => {
  await page.route("**/api/news/translate", async () => {
    /* nunca responde: el usuario cancela */
  });
  await abrirRedaccion(page);
  await escribirCastellano(page);
  await page.getByTestId("room-translate").click();
  await expect(page.getByRole("progressbar")).toBeVisible();
  await page.getByTestId("room-tr-cancel").click();
  await expect(page.getByTestId("room-tr-error")).toContainText("cancelada");
  await expect(page.getByTestId("room-translate")).toBeEnabled();
});

test("accesibilidad (axe) de la redacción con el borrador traducido, en claro y oscuro", async ({ page }) => {
  await page.route("**/api/news/translate", (route) => fulfill(route, 200, BORRADOR));
  for (const tema of ["light", "dark"] as const) {
    await page.goto("/?nosw=1#/ajustes");
    await page.getByTestId("theme-select").selectOption(tema);
    await abrirRedaccion(page);
    await escribirCastellano(page);
    await page.getByTestId("room-translate").click();
    await expect(page.getByTestId("room-tr-result")).toBeVisible();
    await page.getByTestId("room-tr-pairs").locator("summary").click();
    const r = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
    const graves = r.violations.filter((v) => v.impact === "critical" || v.impact === "serious").map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`);
    expect(graves, `redacción ${tema}`).toEqual([]);
  }
});
