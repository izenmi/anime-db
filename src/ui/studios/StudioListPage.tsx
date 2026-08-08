import { getStudios } from "../../data/manifest";
import { useAsyncData } from "../common/useAsyncData";
import { Loading, ErrorState } from "../common/Status";
import { EntityList } from "../common/EntityList";
import { useSeo } from "../common/useSeo";

export function StudioListPage() {
  const state = useAsyncData(getStudios, []);

  useSeo({
    title: "スタジオ一覧",
    description:
      state.status === "ready"
        ? `アニメーション制作スタジオ${state.data.length}社の一覧。五十音順に探せます。`
        : undefined,
  });

  return (
    <div className="page">
      <h1>スタジオ一覧</h1>
      {state.status === "loading" && <Loading />}
      {state.status === "error" && <ErrorState error={state.error} />}
      {state.status === "ready" && (
        <>
          <p className="page-subtitle">{state.data.length}社</p>
          <EntityList items={state.data} pathPrefix="/studios" />
        </>
      )}
    </div>
  );
}
