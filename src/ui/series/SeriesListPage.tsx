import { getSeries } from "../../data/manifest";
import { useAsyncData } from "../common/useAsyncData";
import { Loading, ErrorState } from "../common/Status";
import { EntityList } from "../common/EntityList";
import { useSeo } from "../common/useSeo";

export function SeriesListPage() {
  const state = useAsyncData(getSeries, []);

  useSeo({
    title: "シリーズ一覧",
    description:
      state.status === "ready"
        ? `アニメシリーズ${state.data.length}件の一覧。シリーズごとに作品を放送順で辿れます。`
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
          <EntityList items={state.data} pathPrefix="/series" />
        </>
      )}
    </div>
  );
}
