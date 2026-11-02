// C4 (voz + texto + avatar) y la degradación, con el visor y el modelo de la Fase 3.
import { expect, test, type Page } from "@playwright/test";
import { clickPlay, emittedTypes, openNews, waitFinished } from "./helpers";

const VRM = "/models/presentadora_provisional.vrm";

async function requireVrm(page: Page) {
  const r = await page.request.get(VRM);
  test.skip(!r.ok(), "falta el modelo VRM provisional (ver frontend/README.md); no se versiona");
}

const avatarEvents = (page: Page) =>
  page.evaluate(() =>
    (window as any).__app.events.emitted.filter((e: { type: string }) => e.type === "avatar-ok" || e.type === "degradacion"),
  );



  test("C4 degrada a imagen fija, registra sin-webgl y mantiene audio y texto", async ({ page }) => {
    await requireVrm(page);
    await openNews(page, 1, "C4");
    await expect(page.locator("[data-avatar-mode]")).toHaveAttribute("data-avatar-mode", "fijo", { timeout: 60_000 });
    await expect(page.getByAltText("Presentadora (imagen fija)")).toBeVisible();
    await expect(page.locator("canvas")).toHaveCount(0);
    const ev = await avatarEvents(page);
    expect(ev).toHaveLength(1);
    expect(ev[0].type).toBe("degradacion");
    expect(ev[0].payload.reason).toBe("sin-webgl");
    await expect(page.getByTestId("body")).toContainText("Tee otimimotena");
    await clickPlay(page);
    await waitFinished(page);
    expect(await emittedTypes(page)).toContain("segment-end");
  });

  test("el evento de degradación llega al servidor", async ({ page }) => {
    await requireVrm(page);
    await openNews(page, 1, "C4");
    await expect(page.locator("[data-avatar-mode]")).toHaveAttribute("data-avatar-mode", "fijo", { timeout: 60_000 });
    await page.evaluate(() => (window as any).__app.events.flush());
    const s = await (await page.request.get("/api/events/summary")).json();
    expect(s.por_tipo.degradacion).toBeGreaterThanOrEqual(1);
    expect(s.por_condicion.C4).toBeGreaterThanOrEqual(1);
  });
