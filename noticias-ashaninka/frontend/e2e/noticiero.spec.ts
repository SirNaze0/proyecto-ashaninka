// Diseño de noticiero (v0): sin roles (QuitarAdmin), sala de redacción abierta con carga de archivos,
// publicación real (news → process → build), estudio C4 centrado y accesibilidad en claro y oscuro.
// Corre en su propio servidor (proyecto «noticiero»): publicar añade noticias a su base de datos.
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { clickPlay, waitFinished } from "./helpers";

// Texto del corpus de prueba del servidor E2E (el mismo de las noticias ficticias): no es asháninka inventado
const CUERPO = "Tee otimimotena katsini.\n\nOkantzi kemetsa. Tzimatsi kitaiteri.";

async function abrirPortada(page: Page) {
  await page.goto("/?nosw=1");
}

const TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];
async function serious(page: Page) {
  const r = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  return r.violations.filter((v) => v.impact === "critical" || v.impact === "serious").map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`);
}

test("Sin roles: cualquiera ve la sala de redacción, sin selector ni token", async ({ page }) => {
  await page.goto("/?nosw=1");
  const nav = page.getByRole("navigation", { name: "Principal" });
  await expect(nav.getByRole("link", { name: "Traductor" })).toBeVisible();
  await expect(page.getByTestId("role-admin")).toHaveCount(0);
  await expect(page.getByTestId("token-input")).toHaveCount(0);
  await nav.getByRole("link", { name: "Sala de redacción" }).click();
  await expect(page.getByRole("heading", { level: 2 })).toHaveText("Sala de redacción");
  // entrar directamente por la URL también funciona
  await page.goto("/?nosw=1#/redaccion");
  await expect(page).toHaveURL(/#\/redaccion$/);
  await expect(page.getByRole("heading", { level: 2 })).toHaveText("Sala de redacción");
});

test("Redacción: importa un lote JSON, publica con voz por lotes y la abre en el estudio C4", async ({ page }) => {
  await abrirPortada(page);
  await page.getByRole("navigation", { name: "Principal" }).getByRole("link", { name: "Sala de redacción" }).click();

  const lote = [
    { titulo_cni: "PRUEBA-A (ficticia)", cuerpo_cni: CUERPO, procedencia: { tipo: "traduccion_humana", sistema: "equipo E2E" } },
    { titulo_cni: "PRUEBA-B (ficticia)", cuerpo_cni: CUERPO, procedencia: { tipo: "traduccion_humana" } },
  ];
  await page.getByTestId("room-file").setInputFiles({ name: "lote.json", mimeType: "application/json", buffer: Buffer.from(JSON.stringify(lote)) });
  await expect(page.getByTestId("room-file-msg")).toContainText("2 noticia(s)");
  await expect(page.getByTestId("room-batch").locator("li")).toHaveCount(2);
  await expect(page.getByTestId("room-title")).toHaveValue("PRUEBA-A (ficticia)");
  await expect(page.getByTestId("room-prov-tipo")).toHaveValue("traduccion_humana");

  await page.getByTestId("room-publish").click();
  await expect(page.getByTestId("room-result")).toContainText("publicada", { timeout: 60_000 });
  await expect(page.getByTestId("room-error")).toHaveText("");
  await page.getByTestId("room-open").click();

  await expect(page.locator("article.pres")).toHaveAttribute("data-condition", "C4");
  await expect(page.locator("article.pres")).toHaveClass(/pres-centrado/);
  await expect(page.locator(".stage .lower-third")).toContainText("Noticia en asháninka");
  await expect(page.locator(".pres .avatar-slot")).not.toHaveAttribute("data-avatar-mode", "cargando", { timeout: 60_000 });
  await expect(page.getByTestId("body")).toContainText("Tee otimimotena");
  await clickPlay(page);
  await waitFinished(page);
  // la noticia publicada también está en el catálogo público (portada)
  await page.getByRole("navigation", { name: "Principal" }).getByRole("link", { name: "Noticias" }).click();
  await expect(page.locator(".news-list li")).toHaveCount(4);
  await expect(page.locator(".news-list").getByText("PRUEBA-A (ficticia)")).toBeVisible();
});

test("Redacción: pegado rápido, procedencia obligatoria y errores del servidor visibles", async ({ page }) => {
  await abrirPortada(page);
  await page.getByRole("navigation", { name: "Principal" }).getByRole("link", { name: "Sala de redacción" }).click();
  await page.getByTestId("room-publish").click();
  await expect(page.getByTestId("room-error")).toContainText("falta el título");
  await page.getByText("Pegado rápido de texto").click();
  await page.getByTestId("room-paste").fill(`Título: PRUEBA-C (ficticia)\n\n${CUERPO}`);
  await page.getByTestId("room-paste-apply").click();
  await expect(page.getByTestId("room-title")).toHaveValue("PRUEBA-C (ficticia)");
  await expect(page.getByTestId("room-par-1")).toHaveValue(/Okantzi/);
  // una traducción automática no puede declararse revisada
  await page.getByLabel("Revisada por un hablante").check();
  await page.getByTestId("room-publish").click();
  await expect(page.getByTestId("room-error")).toContainText("automática revisada");
});

test("Estudio C4: alterna entre estudio centrado y lectura paralela", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto("/?nosw=1#/noticia/1?c=C4");
  await expect(page.locator("article.pres")).toHaveClass(/pres-centrado/);
  const stage = await page.locator(".stage").boundingBox();
  const body = await page.getByTestId("body").boundingBox();
  expect(stage && body && body.y >= stage.y + stage.height - 1).toBe(true); // teleprompter bajo el escenario
  await page.getByTestId("layout-paralela").click();
  await expect(page.locator("article.pres")).toHaveClass(/pres-paralela/);
  await expect(page.getByTestId("play")).toBeVisible();
});

test("accesibilidad (axe) del noticiero en claro y oscuro: portada, estudio, redacción", async ({ page }) => {
  // sin transiciones: axe medía la opacidad de .btn a mitad de camino (deshabilitado → habilitado)
  await page.emulateMedia({ reducedMotion: "reduce" });
  for (const tema of ["light", "dark"] as const) {
    await page.goto("/?nosw=1#/ajustes");
    await page.getByTestId("theme-select").selectOption(tema);
    await expect(page.locator("html")).toHaveAttribute("data-theme", tema);
    await page.goto(`/?nosw=1#/noticias`);
    await expect(page.locator(".news-list li").first()).toBeVisible();
    expect(await serious(page), `portada ${tema}`).toEqual([]);
    await page.goto(`/?nosw=1#/noticia/1?c=C4`);
    await expect(page.locator(".pres .avatar-slot")).not.toHaveAttribute("data-avatar-mode", "cargando", { timeout: 60_000 });
    await expect(page.getByTestId("body")).toContainText("Tee otimimotena");
    expect(await serious(page), `estudio ${tema}`).toEqual([]);
    await page.goto(`/?nosw=1#/ajustes`);
    expect(await serious(page), `ajustes ${tema}`).toEqual([]);
  }
  await abrirPortada(page);
  await page.getByRole("navigation", { name: "Principal" }).getByRole("link", { name: "Sala de redacción" }).click();
  await expect(page.getByTestId("room-pending")).toBeVisible();
  expect(await serious(page), "redacción").toEqual([]);
});
