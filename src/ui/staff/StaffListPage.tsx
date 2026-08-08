import { getStaff } from "../../data/manifest";
import { useAsyncData } from "../common/useAsyncData";
import { Loading, ErrorState } from "../common/Status";
import { EntityList } from "../common/EntityList";
import { useSeo } from "../common/useSeo";

export function StaffListPage() {
  const state = useAsyncData(getStaff, []);

  useSeo({
    title: "スタッフ一覧",
    description:
      state.status === "ready"
        ? `アニメの監督・シリーズ構成${state.data.length}人の一覧。五十音順に探せます。`
        : undefined,
  });

  return (
    <div className="page">
      <h1>スタッフ一覧</h1>
      <p className="page-subtitle">監督・シリーズ構成を収録しています。</p>
      {state.status === "loading" && <Loading />}
      {state.status === "error" && <ErrorState error={state.error} />}
      {state.status === "ready" && (
        <>
          <p className="page-subtitle">{state.data.length}人</p>
          <EntityList items={state.data} pathPrefix="/staff" />
        </>
      )}
    </div>
  );
}
