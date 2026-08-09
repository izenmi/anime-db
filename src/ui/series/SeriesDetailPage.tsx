import { useParams } from "react-router-dom";
import { getSeriesItem } from "../../data/manifest";
import { useAsyncData } from "../common/useAsyncData";
import { Loading, ErrorState, EmptyState } from "../common/Status";
import { WorkCard } from "../common/WorkCard";
import { BASE_PATH, SITE_NAME, breadcrumbJsonLd, useSeo } from "../common/useSeo";

/** シリーズの作品を新しい順(放送順の逆)固定で表示する。最新作から辿れるほうが探しやすい
 *  という判断で、キャスト詳細と同じ思想でソート切替は置かない。 */
export function SeriesDetailPage() {
  const { id } = useParams<{ id: string }>();
  const state = useAsyncData(() => getSeriesItem(id!), [id]);
  const series = state.status === "ready" ? state.data : undefined;

  useSeo({
    title: series?.name,
    description: series
      ? `${series.name}の収録${series.workCount}作品を新しい順に紹介。${series.description ?? ""}`.slice(0, 160)
      : undefined,
    jsonLd: series
      ? [
          breadcrumbJsonLd([
            { name: SITE_NAME, path: BASE_PATH },
            { name: "シリーズ一覧", path: `${BASE_PATH}series` },
            { name: series.name, path: `${BASE_PATH}series/${id}` },
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
          <p className="page-subtitle">{state.data.workCount}作品(新しい順)</p>
          {state.data.description && <p>{state.data.description}</p>}
          {state.data.externalLinks.wikipediaUrl && (
            <p>
              <a href={state.data.externalLinks.wikipediaUrl} target="_blank" rel="noreferrer">
                Wikipediaで見る
              </a>
            </p>
          )}
          {state.data.works.length === 0 && <EmptyState text="作品が登録されていません。" />}
          <div className="work-grid">
            {state.data.works.map((w) => (
              <WorkCard work={w} key={w.id} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
