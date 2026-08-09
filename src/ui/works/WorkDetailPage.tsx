import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getWork, getWorks } from "../../data/manifest";
import { useAsyncData } from "../common/useAsyncData";
import { Loading, ErrorState, EmptyState } from "../common/Status";
import { WorkCard } from "../common/WorkCard";
import { WorkCover, amazonSearchUrl, danimeSearchUrl, netflixSearchUrl, primeVideoSearchUrl } from "../common/WorkCover";
import { BASE_PATH, DEFAULT_OG_IMAGE, SITE_NAME, breadcrumbJsonLd, useSeo } from "../common/useSeo";
import { FORMAT_LABEL, ORIGINAL_TYPE_LABEL, STATUS_LABEL, seasonLabel } from "../common/labels";
import type { WorkGenerated } from "../../types";

function workJsonLd(id: string, w: WorkGenerated) {
  return [
    {
      "@context": "https://schema.org",
      "@type": w.format === "movie" ? "Movie" : "TVSeries",
      name: w.title,
      inLanguage: "ja",
      director: w.directorNames.map((name) => ({ "@type": "Person", name })),
      productionCompany: w.studioNames.map((name) => ({ "@type": "Organization", name })),
      ...(w.castGenerated.length > 0 && {
        actor: w.castGenerated.map((c) => ({ "@type": "Person", name: c.voiceActorName })),
      }),
      datePublished: String(w.season.year),
      ...(w.format === "tv" && w.episodes != null && { numberOfEpisodes: w.episodes }),
      // Spoiler tags are left out of the structured data too — search snippets are exactly the
      // place a reader would meet them without having chosen to.
      genre: w.themeIds.filter((tid) => !w.spoilerThemeIds.includes(tid)).map((tid) => w.themeNames[w.themeIds.indexOf(tid)]),
      description: w.synopsis,
      ...(w.coverUrl && { image: w.coverUrl }),
      ...(w.awardSummaries.length > 0 && {
        award: w.awardSummaries.map((a) => `${a.awardName} ${a.result}(${a.year})`),
      }),
    },
    breadcrumbJsonLd([
      { name: SITE_NAME, path: BASE_PATH },
      { name: "作品一覧", path: `${BASE_PATH}works` },
      { name: w.title, path: `${BASE_PATH}works/${id}` },
    ]),
  ];
}

const SISTER_LINKS: { key: keyof WorkGenerated; label: string }[] = [
  { key: "relatedNovelUrl", label: "原作小説をらのべDBで見る →" },
  { key: "relatedComicUrl", label: "原作コミックをまんがDBで見る →" },
  { key: "relatedMysteryUrl", label: "原作小説をミステリDBで見る →" },
  { key: "relatedGameUrl", label: "原作ゲームをゲームDBで見る →" },
];

export function WorkDetailPage() {
  const { id } = useParams<{ id: string }>();
  const state = useAsyncData(() => getWork(id!), [id]);
  const work = state.status === "ready" ? state.data : undefined;
  // Deliberately component-local and not persisted: every visit to a work page starts with the
  // spoiler tags hidden, even if the reader revealed them on a different work a moment ago.
  const [spoilersShown, setSpoilersShown] = useState(false);

  // getWorks() resolves from the same cached works.json that getWork() above already pulled,
  // so this costs no extra request.
  const allWorksState = useAsyncData(getWorks, []);
  const relatedWorks = useMemo(() => {
    if (allWorksState.status !== "ready" || !work?.relatedWorkIds) return [];
    const byId = new Map(allWorksState.data.map((x) => [x.id, x]));
    return work.relatedWorkIds
      .map((relatedId) => byId.get(relatedId))
      .filter((x): x is WorkGenerated => Boolean(x));
  }, [allWorksState, work]);

  useSeo({
    title: work?.title,
    description: work
      ? `${work.title}(${seasonLabel(work.season)}/${work.studioNames.join("・")})のあらすじ・スタッフ・キャスト・受賞歴をまとめて紹介。${work.synopsis.slice(0, 60)}…`
      : undefined,
    image: work?.coverUrl ?? DEFAULT_OG_IMAGE,
    jsonLd: work ? workJsonLd(id!, work) : undefined,
  });

  const openThemes = work ? work.themeIds.filter((tid) => !work.spoilerThemeIds.includes(tid)) : [];
  const spoilerThemes = work ? work.spoilerThemeIds : [];
  const themeName = (tid: string) => work!.themeNames[work!.themeIds.indexOf(tid)];

  return (
    <div className="page">
      {state.status === "loading" && <Loading />}
      {state.status === "error" && <ErrorState error={state.error} />}
      {state.status === "ready" && !state.data && <EmptyState text="見つかりませんでした。" />}
      {state.status === "ready" && state.data && (
        <>
          <div className="work-detail__hero">
            <div className="work-detail__hero-cover">
              <WorkCover title={state.data.title} coverUrl={state.data.coverUrl} size="lg" />
              <a
                className="cover-link"
                href={netflixSearchUrl(state.data.title)}
                target="_blank"
                rel="noreferrer"
              >
                Netflixで探す
              </a>
              <a
                className="cover-link"
                href={primeVideoSearchUrl(state.data.title)}
                target="_blank"
                rel="noreferrer"
              >
                Prime Videoで探す
              </a>
              <a
                className="cover-link"
                href={danimeSearchUrl(state.data.title)}
                target="_blank"
                rel="noreferrer"
              >
                dアニメストアで探す
              </a>
              <a
                className="cover-link"
                href={amazonSearchUrl(state.data.title, "Blu-ray")}
                target="_blank"
                rel="noreferrer"
              >
                AmazonでBlu-rayを探す
              </a>
            </div>
            <div className="work-card__body">
              <h1>{state.data.title}</h1>
              <p className="page-subtitle">
                <span className={`season-badge season-badge--${state.data.season.quarter}`}>
                  {seasonLabel(state.data.season)}
                </span>{" "}
                {FORMAT_LABEL[state.data.format]}
                {state.data.episodes != null && ` / 全${state.data.episodes}話`}
                {" / "}
                {STATUS_LABEL[state.data.status]}
                {" / "}
                {ORIGINAL_TYPE_LABEL[state.data.originalType]}
              </p>
              <p className="page-subtitle">
                監督:{" "}
                {state.data.directorIds.map((staffId, i) => (
                  <span key={staffId}>
                    {i > 0 && "・"}
                    <Link to={`/staff/${staffId}`}>{state.data!.directorNames[i]}</Link>
                  </span>
                ))}
                {state.data.seriesComposerIds.length > 0 && (
                  <>
                    {" / "}シリーズ構成:{" "}
                    {state.data.seriesComposerIds.map((staffId, i) => (
                      <span key={staffId}>
                        {i > 0 && "・"}
                        <Link to={`/staff/${staffId}`}>{state.data!.seriesComposerNames[i]}</Link>
                      </span>
                    ))}
                  </>
                )}
              </p>
              <p className="page-subtitle">
                制作:{" "}
                {state.data.studioIds.map((studioId, i) => (
                  <span key={studioId}>
                    {i > 0 && "・"}
                    <Link to={`/studios/${studioId}`}>{state.data!.studioNames[i]}</Link>
                  </span>
                ))}
              </p>
              {state.data.seriesId && state.data.seriesName && (
                <p className="page-subtitle">
                  <Link to={`/series/${state.data.seriesId}`}>{state.data.seriesName}</Link>
                </p>
              )}
              {state.data.castGenerated.length > 0 && (
                <p className="page-subtitle">
                  出演:{" "}
                  {state.data.castGenerated.map((c, i) => (
                    <span key={c.voiceActorId}>
                      {i > 0 && "・"}
                      <Link to={`/cast/${c.voiceActorId}`}>{c.voiceActorName}</Link>
                      <span className="cast-character">({c.character})</span>
                    </span>
                  ))}
                </p>
              )}
              {state.data.broadcastNote && <p className="page-subtitle">{state.data.broadcastNote}</p>}

              {openThemes.length > 0 && (
                <div className="chip-row">
                  {openThemes.map((themeId) => (
                    <Link className="chip" to={`/themes/${themeId}`} key={themeId}>
                      {themeName(themeId)}
                    </Link>
                  ))}
                </div>
              )}

              {spoilerThemes.length > 0 && (
                <div className="spoiler-block">
                  {spoilersShown ? (
                    <>
                      <p className="spoiler-block__note">ネタバレを含むタグ</p>
                      <div className="chip-row">
                        {spoilerThemes.map((themeId) => (
                          <Link className="chip spoiler-chip" to={`/themes/${themeId}`} key={themeId}>
                            {themeName(themeId)}
                          </Link>
                        ))}
                      </div>
                    </>
                  ) : (
                    <button type="button" className="spoiler-toggle" onClick={() => setSpoilersShown(true)}>
                      ネタバレを含むタグを表示({spoilerThemes.length}件)
                    </button>
                  )}
                </div>
              )}

              {state.data.awardSummaries.length > 0 && (
                <div className="chip-row">
                  {state.data.awardSummaries.map((a) => (
                    <Link className="chip award-chip" to={`/awards/${a.awardId}`} key={`${a.awardId}-${a.year}-${a.result}`}>
                      {a.awardName} {a.result}({a.year})
                    </Link>
                  ))}
                </div>
              )}
            </div>
          </div>

          <p>{state.data.synopsis}</p>

          {state.data.externalLinks.wikipediaUrl && (
            <p>
              <a href={state.data.externalLinks.wikipediaUrl} target="_blank" rel="noreferrer">
                Wikipediaで見る
              </a>
            </p>
          )}
          {state.data.externalLinks.officialUrl && (
            <p>
              <a href={state.data.externalLinks.officialUrl} target="_blank" rel="noreferrer">
                公式サイト
              </a>
            </p>
          )}

          {SISTER_LINKS.map(({ key, label }) => {
            const url = state.data![key];
            return typeof url === "string" && url ? (
              <p key={key}>
                <a className="sister-link" href={url}>
                  {label}
                </a>
              </p>
            ) : null;
          })}

          {relatedWorks.length > 0 && (
            <div className="home-section">
              <h2 className="home-section__heading font-display">この作品が好きなら</h2>
              <div className="work-grid">
                {relatedWorks.map((related) => (
                  <WorkCard key={related.id} work={related} />
                ))}
              </div>
            </div>
          )}

          <p className="source-note">{state.data.sourceNote}</p>
        </>
      )}
    </div>
  );
}
