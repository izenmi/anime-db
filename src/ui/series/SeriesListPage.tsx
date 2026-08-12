import { getSeries, getWorks } from "../../data/manifest";
import { useAsyncData } from "../common/useAsyncData";
import { Loading, ErrorState } from "../common/Status";
import { useSeo } from "../common/useSeo";
import { SeriesCard } from "./SeriesCard";

export function SeriesListPage() {
  const state = useAsyncData(getSeries, []);
  // カードのキービジュアル・スタジオ・テーマは works.json 側にある(SeriesGenerated は workIds のみ)。
  const worksState = useAsyncData(getWorks, []);
  const worksById = new Map(
    (worksState.status === "ready" ? worksState.data : []).map((w) => [w.id, w]),
  );
  const worksOf = (ids: string[]) =>
    ids.map((id) => worksById.get(id)).filter((w) => w !== undefined);

  useSeo({
    title: "シリーズ一覧",
    description:
      state.status === "ready"
        ? `アニメシリーズ${state.data.length}件の一覧。収録作品数の多い順。シリーズごとに作品を新しい順で辿れます。`
        : undefined,
  });

  return (
    <div className="page">
      <h1>シリーズ一覧</h1>
      {state.status === "loading" && <Loading />}
      {state.status === "error" && <ErrorState error={state.error} />}
      {state.status === "ready" && (
        <>
          <p className="page-subtitle">{state.data.length}シリーズ</p>
          <div className="series-grid">
            {state.data.map((x) => (
              <SeriesCard series={x} works={worksOf(x.workIds)} key={x.id} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
