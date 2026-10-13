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



  test("C4 con la CPU 20× más lenta degrada por fps-bajos", async ({ page }) => {
    test.setTimeout(240_000);
    await requireVrm(page);
    const cdp = await page.context().newCDPSession(page);
    await cdp.send("Emulation.setCPUThrottlingRate", { rate: 20 });
    await openNews(page, 1, "C4");
    await expect(page.locator("[data-avatar-mode]")).toHaveAttribute("data-avatar-mode", "fijo", { timeout: 200_000 });
    const ev = await avatarEvents(page);
    expect(ev[0].payload.reason).toBe("fps-bajos");
    expect(ev[0].payload.fps).toBeLessThan(20);
  });
