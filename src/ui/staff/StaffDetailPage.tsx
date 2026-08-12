import { useParams } from "react-router-dom";
import { getStaffMember, getWorksByIds } from "../../data/manifest";
import { useAsyncData } from "../common/useAsyncData";
import { Loading, ErrorState, EmptyState } from "../common/Status";
import { BASE_PATH, SITE_NAME, breadcrumbJsonLd, useSeo } from "../common/useSeo";
import { WorkGrid } from "../common/WorkGrid";
import { useCoverView } from "../common/useCoverView";

/** 監督作品とシリーズ構成作品を2セクションに分けて表示する(game-dbの開発/発売ロール方式)。
 *  各セクションは放送時期の昇順固定 — 「このスタッフの歩み」を時系列で辿るのがこのページの用。 */
export function StaffDetailPage() {
  const { id } = useParams<{ id: string }>();
  const state = useAsyncData(() => getStaffMember(id!), [id]);
  const { coverView, toggle } = useCoverView();
  const person = state.status === "ready" ? state.data : undefined;

  // 作品の実データは works.json 側にある(StaffGenerated は id しか持たない)。
  const directedState = useAsyncData(
    () => (person ? getWorksByIds(person.directedWorkIds) : Promise.resolve([])),
    [person],
  );
  const composedState = useAsyncData(
    () => (person ? getWorksByIds(person.composedWorkIds) : Promise.resolve([])),
    [person],
  );
  const directedWorks = directedState.status === "ready" ? directedState.data : [];
  const composedWorks = composedState.status === "ready" ? composedState.data : [];

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
          <div className="filter-row">{toggle}</div>
          {directedWorks.length > 0 && (
            <>
              <h2 className="home-section__heading font-display">監督作品</h2>
              <WorkGrid works={directedWorks} coverView={coverView} />
            </>
          )}
          {composedWorks.length > 0 && (
            <>
              <h2 className="home-section__heading font-display">シリーズ構成作品</h2>
              <WorkGrid works={composedWorks} coverView={coverView} />
            </>
          )}
        </>
      )}
    </div>
  );
}
