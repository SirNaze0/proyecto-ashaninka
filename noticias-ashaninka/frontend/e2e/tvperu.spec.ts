// Tablón con noticias automáticas de TV Perú (NoticiasTVPeru). El servidor E2E tiene la función apagada
// (NA_FEED_ENABLED=false) y no contacta a TV Perú: los ciclos se simulan con page.route. La noticia
// «automática» es una de las ficticias del servidor marcada como tal en la respuesta (no hay texto inventado).
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Route } from "@playwright/test";

const FUENTE = "https://www.tvperu.gob.pe/noticias/nacionales/noticia-ficticia-de-prueba";
const ESTADO = {
  habilitado: true,
  fuente: "TV Perú",
  fuente_url: "https://www.tvperu.gob.pe/rss.xml",
  intervalo_min: 0,
  intervalos_permitidos: [0, 15, 30, 60, 180, 360],
  max_por_ciclo: 3,
  ejecutando: false,
  ultima_ejecucion: null as string | null,
  proxima_ejecucion: null as string | null,
  ultimo_resultado: null as unknown,
  items: { pendiente: 0, publicada: 0, error: 0, descartada: 0 },
};
const fulfill = (route: Route, status: number, body: unknown) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });

/** Marca la noticia 1 del servidor E2E como traducción automática de TV Perú (lista, meta y detalle). */
async function marcarAutomatica(page: Page) {
  const marcar = (x: Record<string, unknown>) =>
    x.id === 1 ? { ...x, traduccion_automatica: true, fuente_url: FUENTE, fuente_nombre: "TV Perú", procedencia_tipo: "traduccion_automatica" } : x;
  await page.route(/\/api\/catalog(\?.*)?$/, async (route) => {
    const r = await route.fetch();
    await fulfill(route, r.status(), ((await r.json()) as Record<string, unknown>[]).map(marcar));
  });
  await page.route(/\/api\/catalog\/1(\/meta)?$/, async (route) => {
    const r = await route.fetch();
    await fulfill(route, r.status(), marcar((await r.json()) as Record<string, unknown>));
  });
}

test("servidor real con la función apagada: la barra lo dice y desactiva los controles", async ({ page }) => {
  await page.goto("/?nosw=1#/noticias");
  await expect(page.getByTestId("feedbar")).toBeVisible();
  await expect(page.getByTestId("feed-status")).toContainText("apagada en el servidor");
  await expect(page.getByTestId("feed-refresh")).toBeDisabled();
  await expect(page.getByTestId("feed-interval")).toBeDisabled();
});

test("cambia el intervalo, refresca ahora y recarga el tablón al terminar el ciclo", async ({ page }) => {
  let estado = { ...ESTADO };
  const peticiones: { metodo: string; cuerpo: unknown }[] = [];
  await page.route("**/api/feed/status", (r) => fulfill(r, 200, estado));
  await page.route("**/api/feed/config", async (r) => {
    const cuerpo = r.request().postDataJSON() as { intervalo_min: number };
    peticiones.push({ metodo: r.request().method(), cuerpo });
    estado = { ...estado, intervalo_min: cuerpo.intervalo_min, proxima_ejecucion: new Date(Date.now() + 15 * 60_000).toISOString() };
    await fulfill(r, 200, estado);
  });
  await page.route("**/api/feed/run", async (r) => {
    peticiones.push({ metodo: r.request().method(), cuerpo: null });
    estado = { ...estado, ejecutando: true };
    await fulfill(r, 202, { iniciado: true });
  });
  let pedidasCatalogo = 0;
  page.on("request", (req) => {
    if (/\/api\/catalog\?orden=recientes$/.test(req.url())) pedidasCatalogo++;
  });

  await page.goto("/?nosw=1#/noticias");
  await expect(page.getByTestId("feed-status")).toContainText("Aún no se ha actualizado");
  await page.getByTestId("feed-interval").selectOption("15");
  await expect(page.getByTestId("feed-status")).toContainText("próxima en 15 min");
  expect(peticiones[0]).toEqual({ metodo: "PUT", cuerpo: { intervalo_min: 15 } });

  await page.getByTestId("feed-refresh").click();
  await expect(page.getByTestId("feed-refresh")).toBeDisabled();
  await expect(page.getByTestId("feed-status")).toContainText("Actualizando");
  const antes = pedidasCatalogo;
  // el servidor termina el ciclo: 3 publicadas
  estado = {
    ...estado,
    ejecutando: false,
    ultima_ejecucion: new Date().toISOString(),
    ultimo_resultado: { inicio: "x", nuevas: 15, publicadas: [1, 2, 3].map((i) => ({ news_id: i, url: FUENTE })), errores: 0, pendientes: 12, motivo: null },
  };
  await expect(page.getByTestId("feed-status")).toContainText("3 publicadas, 12 en cola", { timeout: 15_000 });
  await expect(page.getByTestId("feed-refresh")).toBeEnabled();
  await expect.poll(() => pedidasCatalogo).toBeGreaterThan(antes); // el tablón se recargó
});

test("traductor caído: el estado muestra el motivo", async ({ page }) => {
  await page.route("**/api/feed/status", (r) =>
    fulfill(r, 200, {
      ...ESTADO,
      ultima_ejecucion: new Date(Date.now() - 5 * 60_000).toISOString(),
      ultimo_resultado: { inicio: "x", nuevas: 15, publicadas: [], errores: 0, pendientes: 15, motivo: "traductor no disponible: sin configurar" },
    }),
  );
  await page.goto("/?nosw=1#/noticias");
  await expect(page.getByTestId("feed-status")).toContainText("hace 5 min");
  await expect(page.getByTestId("feed-status")).toContainText("sin publicar: traductor no disponible");
});

test("la noticia automática lleva etiqueta en el tablón y aviso con enlace a la fuente al abrirla", async ({ page }) => {
  await marcarAutomatica(page);
  await page.goto("/?nosw=1#/noticias");
  const tarjeta = page.locator(".news-list li", { has: page.getByTestId("auto-tag") });
  await expect(tarjeta).toHaveCount(1);
  await expect(tarjeta).toContainText("Fuente: TV Perú");
  await page.goto("/?nosw=1#/noticia/1?c=C1");
  const aviso = page.getByTestId("auto-notice");
  await expect(aviso).toContainText("Traducción automática de una noticia de TV Perú, sin revisar");
  const enlace = page.getByTestId("source-link");
  await expect(enlace).toHaveAttribute("href", FUENTE);
  await expect(enlace).toHaveAttribute("rel", /noopener/);
  await expect(enlace).toHaveAttribute("target", "_blank");
});

test("accesibilidad (axe) del tablón con la barra de TV Perú, en claro y oscuro", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.route("**/api/feed/status", (r) => fulfill(r, 200, { ...ESTADO, intervalo_min: 30 }));
  await marcarAutomatica(page);
  for (const tema of ["light", "dark"] as const) {
    await page.emulateMedia({ colorScheme: tema, reducedMotion: "reduce" });
    await page.goto("/?nosw=1#/noticias");
    await expect(page.getByTestId("feedbar")).toBeVisible();
    await expect(page.getByTestId("auto-tag")).toBeVisible();
    const r = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
    const graves = r.violations.filter((v) => v.impact === "critical" || v.impact === "serious").map((v) => v.id);
    expect(graves, tema).toEqual([]);
  }
});
