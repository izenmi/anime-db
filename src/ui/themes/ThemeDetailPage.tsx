import { useMemo } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { getTheme } from "../../data/manifest";
import { useAsyncData } from "../common/useAsyncData";
import { Loading, ErrorState, EmptyState } from "../common/Status";
import { matchesKeyword, themeOptionsOf } from "../common/useWorkFilter";
import { BASE_PATH, SITE_NAME, breadcrumbJsonLd, useSeo } from "../common/useSeo";
import { ORIGINAL_TYPE_LABEL, seasonSortKey } from "../common/labels";
import { WorkGrid } from "../common/WorkGrid";
import { useCoverView } from "../common/useCoverView";

const ORIGINAL_TYPE_OPTIONS = (Object.entries(ORIGINAL_TYPE_LABEL) as [string, string][]).map(
  ([value, label]) => ({ value, label }),
);

const SORT_OPTIONS: { value: string; label: string }[] = [
  { value: "year-desc", label: "放送時期が新しい順" },
  { value: "year-asc", label: "放送時期が古い順" },
  { value: "kana", label: "五十音順" },
];

export function ThemeDetailPage() {
  const { id } = useParams<{ id: string }>();
  const state = useAsyncData(() => getTheme(id!), [id]);
  const { coverView, toggle } = useCoverView();
  const theme = state.status === "ready" ? state.data : undefined;

  useSeo({
    title: theme?.name,
    // A spoiler tag's own page keeps its description generic: the meta description is what shows
    // up in search results, where nobody has opted in to seeing which works carry the tag.
    description: theme
      ? theme.spoiler
        ? `「${theme.name}」タグの作品一覧。ネタバレを含むため、未視聴作品がある場合は閲覧にご注意ください。`
        : `「${theme.name}」テーマのアニメ${theme.workCount}作品一覧。${theme.description ?? ""}`.trim()
      : undefined,
    jsonLd: theme
      ? breadcrumbJsonLd([
          { name: SITE_NAME, path: BASE_PATH },
          { name: "テーマ一覧", path: `${BASE_PATH}themes` },
          { name: theme.name, path: `${BASE_PATH}themes/${id}` },
        ])
      : undefined,
  });

  const [params, setParams] = useSearchParams();
  const q = params.get("q") ?? "";
  // このページ自身のテーマは全作品が持っていて絞り込みにならないので選択肢から外す
  const other = params.get("theme") ?? "";
  const originalType = params.get("originalType") ?? "";
  const sort = params.get("sort") ?? "year-desc";

  const options = useMemo(
    () => themeOptionsOf(state.status === "ready" ? state.data?.works : undefined, id),
    [state, id],
  );

  const filtered = useMemo(() => {
    if (state.status !== "ready" || !state.data) return [];
    const keyword = q.trim().toLowerCase();
    return state.data.works.filter((w) => {
      if (!matchesKeyword(w, keyword)) return false;
      if (other && !w.themeIds.includes(other)) return false;
      if (originalType && w.originalType !== originalType) return false;
      return true;
    });
  }, [state, originalType, q, other]);

  const sorted = useMemo(() => {
    if (sort === "year-asc") return [...filtered].sort((a, b) => seasonSortKey(a) - seasonSortKey(b));
    if (sort === "year-desc") return [...filtered].sort((a, b) => seasonSortKey(b) - seasonSortKey(a));
    if (sort === "kana") return [...filtered].sort((a, b) => a.titleKana.localeCompare(b.titleKana, "ja"));
    return filtered;
  }, [filtered, sort]);

  function updateParam(key: string, value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
  }

  function clearFilters() {
    const next = new URLSearchParams(params);
    for (const key of ["q", "theme", "originalType"]) {
      next.delete(key);
    }
    setParams(next, { replace: true });
  }

  const hasActiveFilters = Boolean(q || other || originalType);

  return (
    <div className="page">
      {state.status === "loading" && <Loading />}
      {state.status === "error" && <ErrorState error={state.error} />}
      {state.status === "ready" && !state.data && <EmptyState text="見つかりませんでした。" />}
      {state.status === "ready" && state.data && (
        <>
          <h1>{state.data.name}</h1>
          {state.data.spoiler && (
            <p className="spoiler-banner">
              このタグはネタバレを含みます。以下の作品は、このタグが付いていること自体が展開の手がかりになります。
            </p>
          )}
          <p className="page-subtitle">{state.data.workCount}作品</p>
          {state.data.description && <p>{state.data.description}</p>}
          <div className="filter-row">
            <input
              type="search"
              value={q}
              placeholder="タイトル・監督で絞り込み"
              aria-label="タイトル・監督で絞り込み"
              onChange={(e) => updateParam("q", e.target.value)}
            />
            {options.length > 0 && (
              <select value={other} onChange={(e) => updateParam("theme", e.target.value)}>
                <option value="">他のテーマで絞り込み</option>
                {options.map((o) => (
                  <option value={o.value} key={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            )}
            <select value={originalType} onChange={(e) => updateParam("originalType", e.target.value)}>
              <option value="">原作種別で絞り込み</option>
              {ORIGINAL_TYPE_OPTIONS.map((o) => (
                <option value={o.value} key={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
            <select
              value={sort}
              onChange={(e) => updateParam("sort", e.target.value === "year-desc" ? "" : e.target.value)}
            >
              {SORT_OPTIONS.map((o) => (
                <option value={o.value} key={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
            {hasActiveFilters && (
              <button type="button" className="filter-clear-btn" onClick={clearFilters}>
                フィルターをクリア
              </button>
            )}
            {toggle}
          </div>
          {sorted.length === 0 && <EmptyState />}
          <WorkGrid works={sorted} coverView={coverView} />
        </>
      )}
    </div>
  );
}
