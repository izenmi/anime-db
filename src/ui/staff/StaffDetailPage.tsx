import { useParams } from "react-router-dom";
import { getStaffMember } from "../../data/manifest";
import { useAsyncData } from "../common/useAsyncData";
import { Loading, ErrorState, EmptyState } from "../common/Status";
import { WorkCard } from "../common/WorkCard";
import { BASE_PATH, SITE_NAME, breadcrumbJsonLd, useSeo } from "../common/useSeo";

/** 監督作品とシリーズ構成作品を2セクションに分けて表示する(game-dbの開発/発売ロール方式)。
 *  各セクションは放送時期の昇順固定 — 「このスタッフの歩み」を時系列で辿るのがこのページの用。 */
export function StaffDetailPage() {
  const { id } = useParams<{ id: string }>();
  const state = useAsyncData(() => getStaffMember(id!), [id]);
  const person = state.status === "ready" ? state.data : undefined;

  useSeo({
    title: person?.name,
    description: person
      ? `「${person.name}」が監督・シリーズ構成を務めたアニメ${person.workCount}作品を放送順に紹介。${person.description}`.slice(0, 160)
      : undefined,
    jsonLd: person
      ? [
          {
            "@context": "https://schema.org",
            "@type": "Person",
            name: person.name,
            ...(person.description && { description: person.description }),
            ...(person.externalLinks.wikipediaUrl && { sameAs: [person.externalLinks.wikipediaUrl] }),
          },
          breadcrumbJsonLd([
            { name: SITE_NAME, path: BASE_PATH },
            { name: "スタッフ一覧", path: `${BASE_PATH}staff` },
            { name: person.name, path: `${BASE_PATH}staff/${id}` },
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
          {state.data.directedWorks.length > 0 && (
            <>
              <h2 className="home-section__heading font-display">監督作品</h2>
              <div className="work-grid">
                {state.data.directedWorks.map((w) => (
                  <WorkCard work={w} key={w.id} />
                ))}
              </div>
            </>
          )}
          {state.data.composedWorks.length > 0 && (
            <>
              <h2 className="home-section__heading font-display">シリーズ構成作品</h2>
              <div className="work-grid">
                {state.data.composedWorks.map((w) => (
                  <WorkCard work={w} key={w.id} />
                ))}
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
