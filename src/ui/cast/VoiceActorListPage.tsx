import { getVoiceActors } from "../../data/manifest";
import { useAsyncData } from "../common/useAsyncData";
import { Loading, ErrorState } from "../common/Status";
import { EntityList } from "../common/EntityList";
import { useSeo } from "../common/useSeo";

export function VoiceActorListPage() {
  const state = useAsyncData(getVoiceActors, []);

  useSeo({
    title: "声優一覧",
    description:
      state.status === "ready"
        ? `声優${state.data.length}人の一覧。声優ごとに主演作品を放送順で辿れます。`
        : undefined,
  });

  return (
    <div className="page">
      <h1>声優一覧</h1>
      <p className="page-subtitle">各作品の主要キャスト(最大5名)のみ収録しています。</p>
      {state.status === "loading" && <Loading />}
      {state.status === "error" && <ErrorState error={state.error} />}
      {state.status === "ready" && (
        <>
          <p className="page-subtitle">{state.data.length}人</p>
          <EntityList items={state.data} pathPrefix="/cast" />
        </>
      )}
    </div>
  );
}
