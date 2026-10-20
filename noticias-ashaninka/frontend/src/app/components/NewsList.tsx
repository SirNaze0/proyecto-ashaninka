import { useEffect, useState } from "preact/hooks";
import { useApp } from "../ctx";
import { fetchCatalog } from "../data";
import { isSaved } from "../offline";
import { newsHref } from "../router";
import { CONDITIONS, type CatalogItem, type Condition } from "../types";

export function NewsList() {
  const { t, online } = useApp();
  const [items, setItems] = useState<CatalogItem[] | null>(null);
  const [saved, setSaved] = useState<Set<number>>(new Set());
  const [error, setError] = useState(false);
  const [cond, setCond] = useState<Condition>("C3");

  useEffect(() => {
    let dead = false;
    fetchCatalog()
      .then(async (list) => {
        if (dead) return;
        setItems(list);
        const s = new Set<number>();
        for (const i of list) if (await isSaved(i.id)) s.add(i.id);
        if (!dead) setSaved(s);
      })
      .catch(() => !dead && setError(true));
    return () => {
      dead = true;
    };
  }, [online]);

  return (
    <section aria-labelledby="list-h">
      <h2 id="list-h">{t("list.title")}</h2>
      {!online && <p class="banner" role="status">{t("offline.banner")}</p>}
      <label class="field">
        {t("list.condition")}
        <select value={cond} onChange={(e) => setCond((e.currentTarget as HTMLSelectElement).value as Condition)}>
          {CONDITIONS.map((c) => (
            <option key={c} value={c}>
              {t(`cond.${c}`)}
            </option>
          ))}
        </select>
      </label>
      {error && <p role="alert">{t("list.error")}</p>}
      {!items && !error && <p role="status">{t("list.loading")}</p>}
      {items && items.length === 0 && <p>{t("list.empty")}</p>}
      {items && items.length > 0 && <p class="tr-note">{t("list.count", { n: items.length })}</p>}
      <ul class="news-list">
        {items?.map((n, i) => (
          <li key={n.id} class={i === 0 ? "news-featured" : undefined}>
            <a class="news-link" href={newsHref(n.id, cond)}>
              {i === 0 && <span class="news-flag">{t("list.featured")}</span>}
              <span class="news-title" lang="cni">
                {n.titulo_cni}
              </span>
              <span class="news-meta">
                <span class="pill">{t("news.numbered", { n: n.id })}</span>
                <span class="pill">{n.variante_dialectal}</span>
                {n.procedencia_tipo === "corpus_americasnlp" && <span class="pill pill-warn">{t("list.pseudo")}</span>}
                {n.segmentos_con_audio === 0 ? (
                  <span class="pill pill-warn">{t("list.noAudio")}</span>
                ) : (
                  <span class="pill pill-ok">{t("list.audioReady")}</span>
                )}
                {n.segmentos_bloqueados > 0 && n.segmentos_con_audio > 0 && (
                  <span class="pill pill-warn">{t("list.blocked", { n: n.segmentos_bloqueados })}</span>
                )}
                {saved.has(n.id) && <span class="pill pill-ok">{t("list.saved")}</span>}
              </span>
              <span class="news-open" aria-hidden="true">
                {t("list.openStudio")} →
              </span>
            </a>
          </li>
        ))}
      </ul>
    </section>
  );
}
