// Fase 6: la política de seguridad de contenido (CSP) del servidor no bloquea nada de la PWA.
// Se escuchan los eventos `securitypolicyviolation` del navegador y los errores de consola.
import { expect, test } from "@playwright/test";
import { clickPlay, openNews, vigilarCsp, waitFinished, type Cond } from "./helpers";

test("el servidor envía la CSP y las cabeceras de seguridad con la PWA", async ({ page }) => {
  const r = await page.goto("/?nosw=1");
  const h = r!.headers();
  expect(h["content-security-policy"]).toContain("default-src 'self'");
  expect(h["content-security-policy"]).toContain("object-src 'none'");
  expect(h["x-content-type-options"]).toBe("nosniff");
  expect(h["x-frame-options"]).toBe("DENY");
  expect(h["strict-transport-security"]).toBeUndefined(); // HTTP local
});

for (const c of ["C1", "C2", "C3", "C4"] as Cond[]) {
  test(`${c}: cero violaciones de CSP (texto, audio, resaltado y avatar WebGL)`, async ({ page }) => {
    const verificar = await vigilarCsp(page);
    await openNews(page, 1, c);
    if (c === "C1") await expect(page.getByTestId("body")).toContainText("katsini");
    else {
      await clickPlay(page);
      await waitFinished(page);
    }
    if (c === "C4") await expect(page.locator(".avatar-slot")).toHaveAttribute("data-avatar-mode", /.+/);
    await verificar();
  });
}

test("traductor (con avatar), lista, ajustes y Service Worker: cero violaciones de CSP", async ({ page }) => {
  const verificar = await vigilarCsp(page);
  await page.goto("/");
  await expect(page.locator(".tr [data-avatar-mode]")).not.toHaveAttribute("data-avatar-mode", "cargando", { timeout: 60_000 });
  await page.goto("/#/noticias");
  await expect(page.locator(".news-list li").first()).toBeVisible();
  await page.evaluate(() => navigator.serviceWorker.ready);
  await page.goto("/#/ajustes");
  await expect(page.getByRole("heading", { level: 2 }).first()).toBeVisible();
  await verificar();
});
