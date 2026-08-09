import { Link } from "react-router-dom";
import type { WorkGenerated } from "../../types";
import { WorkCover } from "./WorkCover";
import { ORIGINAL_TYPE_LABEL, displaySeason, seasonLabel } from "./labels";

/** カード上のバッジは狭いので、一覧では短い表記を出す(詳細ページは FORMAT_LABEL のまま)。 */
const FORMAT_BADGE: Record<string, string> = { movie: "劇場", ova: "OVA", ona: "ONA" };

/** Fuller card for the main work list page: key-visual thumbnail on the left, and a right-hand
 *  column (title/director/studio/awards + clickable theme tags). The whole card navigates to
 *  the work page via a "stretched link" (`work-card__cover-link`, an absolutely-positioned
 *  <Link> covering the entire card) rather than a `<div onClick>` — that keeps the click target
 *  a real `<a>` so middle-click/ctrl-click "open in new tab" and keyboard nav work natively. The
 *  theme tags' own `<Link>`s are layered above it (`position: relative` in CSS) so they still
 *  navigate to their own theme page instead of the work page.
 *
 *  Spoiler themes are filtered out here rather than merely styled: a card shows up in list
 *  views, search results and cross-reference sections, so a reader scrolling past would be
 *  spoiled without ever choosing to look. They're revealed on WorkDetailPage behind a click. */
export function WorkCard({ work }: { work: WorkGenerated }) {
  const visibleThemes = work.themeIds
    .map((id, i) => ({ id, name: work.themeNames[i] }))
    .filter((t) => !work.spoilerThemeIds.includes(t.id));
  // 一覧のクールは最新シーズン基準(displaySeason)。「全4期」と並べて初めて、その年が
  // 第1期ではなく最新シーズンのものだと読めるので、期数バッジは日付のすぐ隣に置く。
  const season = displaySeason(work);

  return (
    <div className="work-card">
      <Link to={`/works/${work.id}`} className="work-card__cover-link" aria-label={work.title} />
      <WorkCover title={work.title} coverUrl={work.coverUrl} size="sm" />
      <div className="work-card__content">
        <div className="work-card__title">{work.title}</div>
        <div className="work-card__meta">
          <span className={`season-badge season-badge--quiet season-badge--${season.quarter}`}>
            {seasonLabel(season)}
          </span>
          {work.seasonCount != null && (
            <>
              {" "}
              <span className="season-badge season-badge--quiet">全{work.seasonCount}期</span>
            </>
          )}
          {work.format !== "tv" && (
            <span className="season-badge season-badge--quiet season-badge--movie">
              {FORMAT_BADGE[work.format]}
            </span>
          )}
          {" "}
          監督: {work.directorNames.join("・")} / {work.studioNames.join("・")}
          {work.episodes != null && ` / 全${work.episodes}話`}
          {` / ${ORIGINAL_TYPE_LABEL[work.originalType]}`}
        </div>
        {work.seriesName && <div className="work-card__series">{work.seriesName}</div>}
        {work.castGenerated.length > 0 && (
          <div className="work-card__meta">出演: {work.castGenerated.map((c) => c.voiceActorName).join("・")}</div>
        )}
        {work.awardSummaries.length > 0 && (
          <div className="work-card__awards">
            {work.awardSummaries.slice(0, 2).map((a) => (
              <span className="chip award-chip" key={`${a.awardId}-${a.year}-${a.result}`}>
                {a.awardName} {a.result}
              </span>
            ))}
          </div>
        )}
        {visibleThemes.length > 0 && (
          <div className="chip-row">
            {visibleThemes.map((t) => (
              <Link className="chip" to={`/themes/${t.id}`} key={t.id}>
                {t.name}
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/** 表紙表示モード(`?view=covers`)のカード。書影だけを大きく並べる。カード全体がそのまま
 *  <Link> なので WorkCard のような stretched link は要らない。文字が一切出ないぶん、タイトルは
 *  `title`(ホバーで出るツールチップ)と `aria-label`(読み上げ・キーボード操作)の両方で補う。 */
export function WorkCoverCard({ work: item }: { work: WorkGenerated }) {
  return (
    <Link to={`/works/${item.id}`} className="work-cover-card" title={item.title} aria-label={item.title}>
      <WorkCover title={item.title} coverUrl={item.coverUrl} size="xl" />
    </Link>
  );
}
