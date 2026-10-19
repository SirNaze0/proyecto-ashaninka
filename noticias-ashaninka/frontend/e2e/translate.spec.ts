// Pantalla de traducción como entrada principal. El traductor está pendiente de integración: la
// pantalla lo dice, no envía el texto a ningún lugar y no muestra ninguna traducción.
import { expect, test } from "@playwright/test";
import { clickPlay, waitFinished } from "./helpers";

test("la entrada principal es el traductor, con el avatar al costado del texto", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto("/?nosw=1");
  await expect(page.getByRole("heading", { level: 2 })).toHaveText("Traducir al asháninka");
  await expect(page.getByTestId("tr-pending")).toContainText("pendiente de integración");
  await expect(page.getByTestId("tr-output")).toHaveAttribute("data-estado", "inicial");
  const slot = page.locator(".tr [data-avatar-mode]");
  await expect(slot).not.toHaveAttribute("data-avatar-mode", "cargando", { timeout: 60_000 });
  await expect(page.getByText("La presentadora es un avatar sintético")).toBeVisible();
  // avatar a la izquierda del campo de texto, a la misma altura
  const a = (await slot.boundingBox())!;
  const t = (await page.getByTestId("tr-input").boundingBox())!;
  expect(a.x + a.width).toBeLessThanOrEqual(t.x);
  expect(t.y).toBeLessThan(a.y + a.height);
});

test("sin traductor integrado: estado pendiente, ninguna petición y ninguna traducción", async ({ page }) => {
  await page.goto("/?nosw=1");
  // la carga diferida del avatar (three, VRM, texturas) termina antes de escuchar las peticiones
  await expect(page.locator(".tr [data-avatar-mode]")).not.toHaveAttribute("data-avatar-mode", "cargando", { timeout: 60_000 });
  const submit = page.getByTestId("tr-submit");
  await expect(submit).toBeDisabled();
  await page.getByTestId("tr-input").fill("Buenos días a todas las comunidades.");
  await expect(submit).toBeEnabled();
  const reqs: string[] = [];
  page.on("request", (r) => {
    const u = new URL(r.url());
    if (u.protocol !== "blob:") reqs.push(`${r.method()} ${u.pathname}`);
  });
  await submit.click();
  const out = page.getByTestId("tr-output");
  await expect(out).toHaveAttribute("data-estado", "pendiente");
  await expect(out).toContainText("El texto no se envió a ningún lugar");
  await expect(out.locator("[lang=cni]")).toHaveCount(0);
  await page.waitForTimeout(500);
  // ninguna petición de traducción: como mucho, la cola de eventos de la PWA
  expect(reqs.filter((r) => r !== "POST /api/events" && !/^GET \/(assets|models)\//.test(r))).toEqual([]);
  // editar el texto vuelve al estado inicial
  await page.getByTestId("tr-input").fill("Otro texto");
  await expect(out).toHaveAttribute("data-estado", "inicial");
});

test("navegación: traductor → noticias → noticia C4 (voz y avatar) → lista → traductor", async ({ page }) => {
  await page.goto("/?nosw=1");
  await page.getByTestId("tr-to-news").click();
  await expect(page).toHaveURL(/#\/noticias$/);
  await expect(page.locator(".news-list li")).toHaveCount(3);
  await page.getByLabel("Modo de presentación").selectOption("C4");
  await page.locator(".news-link").first().click();
  await expect(page.locator("article.pres")).toHaveAttribute("data-condition", "C4");
  await expect(page.locator(".pres .avatar-slot")).not.toHaveAttribute("data-avatar-mode", "cargando", { timeout: 60_000 });
  await clickPlay(page);
  await waitFinished(page);
  await page.getByRole("link", { name: "Volver a la lista" }).click();
  await expect(page).toHaveURL(/#\/noticias$/);
  await page.getByRole("navigation", { name: "Principal" }).getByRole("link", { name: "Traductor" }).click();
  await expect(page.getByRole("heading", { level: 2 })).toHaveText("Traducir al asháninka");
  await page.locator(".brand").click();
  await expect(page.getByTestId("tr-pending")).toBeVisible();
});
