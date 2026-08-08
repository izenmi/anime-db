import { useParams } from "react-router-dom";
import { getStudio } from "../../data/manifest";
import { useAsyncData } from "../common/useAsyncData";
import { Loading, ErrorState, EmptyState } from "../common/Status";
import { WorkCard } from "../common/WorkCard";
import { useWorkFilter } from "../common/useWorkFilter";
import { BASE_PATH, SITE_NAME, breadcrumbJsonLd, useSeo } from "../common/useSeo";

export function StudioDetailPage() {
  const { id } = useParams<{ id: string }>();
  const state = useAsyncData(() => getStudio(id!), [id]);
  const studio = state.status === "ready" ? state.data : undefined;
  const { sorted, controls, hasActiveFilters } = useWorkFilter(studio?.works);

  useSeo({
    title: studio?.name,
    description: studio
      ? `スタジオ「${studio.name}」の制作アニメ${studio.workCount}作品一覧。${studio.description}`.slice(0, 160)
      : undefined,
    jsonLd: studio
      ? [
          {
            "@context": "https://schema.org",
            "@type": "Organization",
            name: studio.name,
            ...(studio.description && { description: studio.description }),
            ...(studio.externalLinks.wikipediaUrl && { sameAs: [studio.externalLinks.wikipediaUrl] }),
          },
          breadcrumbJsonLd([
            { name: SITE_NAME, path: BASE_PATH },
            { name: "スタジオ一覧", path: `${BASE_PATH}studios` },
            { name: studio.name, path: `${BASE_PATH}studios/${id}` },
          ]),
        ]
      : undefined,
  });

  return (
    <div className="page">
      {state.status === "loading" && <Loading />}
      {state.status === "error" && <ErrorState error={state.error} />}
      {state.status === "ready" && !state.data && <EmptyState text="見つかりませんでした。" />}
      {state.status === "ready" && state.data && (
        <>
          <h1>{state.data.name}</h1>
          <p className="page-subtitle">{state.data.workCount}作品</p>
          {state.data.description && <p>{state.data.description}</p>}
          {state.data.externalLinks.wikipediaUrl && (
            <p>
              <a href={state.data.externalLinks.wikipediaUrl} target="_blank" rel="noreferrer">
                Wikipediaで見る
              </a>
            </p>
          )}
          {controls}
          <p className="page-subtitle">
            {hasActiveFilters ? `${sorted.length}件 / 全${state.data.works.length}件` : `${sorted.length}件`}
          </p>
          {sorted.length === 0 && <EmptyState />}
          <div className="work-grid">
            {sorted.map((w) => (
              <WorkCard work={w} key={w.id} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
