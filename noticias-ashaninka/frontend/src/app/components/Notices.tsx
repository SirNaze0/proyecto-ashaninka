// Avisos éticos (tarea 4.5): voz y avatar sintéticos, licencia no comercial y variante dialectal.
// Los avisos de voz solo se muestran donde hay voz (C2–C4); la variante y la marca de
// pseudo-noticia, siempre.
import { useApp } from "../ctx";
import type { Notices as N } from "../types";

export interface NoticesProps {
  notices: N | null;
  variant?: string;
  voice: boolean;
  avatar: boolean;
  pseudo: boolean;
}

export function Notices({ notices, variant, voice, avatar, pseudo }: NoticesProps) {
  const { t } = useApp();
  // Mientras no llega el manifiesto se asume la voz MMS (CC-BY-NC): mejor avisar de más que de menos
  const license = notices?.license ?? "CC-BY-NC-4.0";
  const nonCommercial = notices ? notices.commercial_use === false : true;
  return (
    <aside class="notices" aria-label="Avisos">
      {voice && <p class="notice-synthetic">{notices?.synthetic_voice ?? t("notice.synthetic")}</p>}
      {voice && avatar && <p>{t("notice.avatar")}</p>}
      {voice && <p>{t("notice.license", { l: license })}</p>}
      {voice && nonCommercial && <p>{t("notice.noncommercial")}</p>}
      {variant && <p class="variant">{t("news.variant", { v: variant })}</p>}
      {pseudo && <p class="pseudo">{t("list.pseudo")}</p>}
    </aside>
  );
}
