// Avisos éticos (tarea 4.5): voz y avatar sintéticos, licencia no comercial y variante dialectal.
import { useApp } from "../ctx";
import type { Notices as N } from "../types";

export interface NoticesProps {
  notices: N | null;
  variant?: string;
  avatar: boolean;
  pseudo: boolean;
}

export function Notices({ notices, variant, avatar, pseudo }: NoticesProps) {
  const { t } = useApp();
  const license = notices?.license ?? "CC-BY-NC-4.0";
  return (
    <aside class="notices" aria-label="Avisos">
      <p class="notice-synthetic">{notices?.synthetic_voice ?? t("notice.synthetic")}</p>
      {avatar && <p>{t("notice.avatar")}</p>}
      <p>{t("notice.license", { l: license })}</p>
      {variant && <p class="variant">{t("news.variant", { v: variant })}</p>}
      {pseudo && <p class="pseudo">{t("list.pseudo")}</p>}
    </aside>
  );
}
