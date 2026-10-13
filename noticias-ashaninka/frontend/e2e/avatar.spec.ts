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

  test("C4: el avatar se carga de forma diferida, hay texto resaltado y audio, y se registra avatar-ok", async ({ page }) => {
    await requireVrm(page);
    const reqs: string[] = [];
    page.on("request", (r) => reqs.push(new URL(r.url()).pathname));
    await openNews(page, 1, "C4");
    // fuera del paquete inicial: three y el VRM solo se piden al entrar en C4
    await expect(page.locator("[data-avatar-mode]")).toHaveAttribute("data-avatar-mode", "avatar", { timeout: 60_000 });
    expect(reqs.some((p) => p.includes("three"))).toBe(true);
    expect(reqs).toContain(VRM);
    await expect(page.locator("canvas")).toHaveCount(1);
    await expect(page.getByText("avatar sintético")).toBeVisible();
    const ev = await avatarEvents(page);
    expect(ev.map((e: { type: string }) => e.type)).toEqual(["avatar-ok"]);
    await clickPlay(page);
    await expect(page.locator(".hl").first()).toBeVisible();
    await waitFinished(page);
    // la boca se movió con el audio: el visor llegó a evaluar visemas
    const t = await page.evaluate(() => (window as any).__app.R.handle.viewer.time);
    expect(t).toBeGreaterThan(0.5);
  });

  test("C1, C2 y C3 no descargan three ni el modelo del avatar", async ({ page }) => {
    for (const c of ["C1", "C2", "C3"] as const) {
      const reqs: string[] = [];
      const on = (r: { url(): string }) => reqs.push(new URL(r.url()).pathname);
      page.on("request", on);
      await openNews(page, 1, c);
      await page.waitForTimeout(800);
      page.off("request", on);
      expect(reqs.filter((p) => p.includes("three") || p.endsWith(".vrm") || p.includes("viewer") || p.includes("AvatarPanel")), c).toEqual([]);
    }
  });
