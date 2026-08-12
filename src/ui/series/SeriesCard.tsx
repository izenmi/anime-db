import { Link } from "react-router-dom";
import type { SeriesGenerated } from "../../types";
import { WorkCover } from "../common/WorkCover";
import { QUARTER_ORDER, displaySeason, seasonLabel } from "../common/labels";

const COVER_COUNT = 4;
const THEME_COUNT = 4;
const STUDIO_COUNT = 2;

/** シリーズ一覧のカード。名前と件数だけの行だと、そのシリーズが何の作品なのか一覧から分からない。
 *  トップの作品カードと同じ密度になるよう、キービジュアル・放送クールの範囲・制作スタジオ・
 *  テーマまで出す。
 *
 *  表示する値はすべて `series.works`(build時にクールの昇順で入っている)から導出していて、
 *  シリーズ側に持たせた項目はない。作品を足せばそのまま更新される。 */
export function SeriesCard({ series }: { series: SeriesGenerated }) {
  const works = series.works;
  // series.json の並び順に依存せず、最古クールと最新クールを自分で取り直す
  // (シリーズによっては新しい順で入っており、そのままだと「2026年冬〜2005年冬」と逆に出る)。
  const key = (s: { year: number; quarter: keyof typeof QUARTER_ORDER }) =>
    s.year * 10 + QUARTER_ORDER[s.quarter];
  const seasons = works.map((w) => w.season);
  const latest = works.map((w) => displaySeason(w));
  const first = seasons.length > 0 ? seasons.reduce((a, b) => (key(b) < key(a) ? b : a)) : undefined;
  const last = latest.length > 0 ? latest.reduce((a, b) => (key(b) > key(a) ? b : a)) : undefined;

  const studios = [...new Set(works.flatMap((w) => w.studioNames))];
  // ネタバレテーマは WorkCard と同じ理由で伏せる(一覧を眺めるだけで割れてしまうため)
  const themeCounts = new Map<string, { name: string; n: number }>();
  for (const w of works) {
    const hidden = new Set(w.spoilerThemeIds);
    w.themeIds.forEach((id, i) => {
      if (hidden.has(id)) return;
      const e = themeCounts.get(id) ?? { name: w.themeNames[i] ?? id, n: 0 };
      e.n += 1;
      themeCounts.set(id, e);
    });
  }
  const themes = [...themeCounts.entries()]
    .sort((a, b) => b[1].n - a[1].n || a[1].name.localeCompare(b[1].name, "ja"))
    .slice(0, THEME_COUNT);

  return (
    <div className="series-card">
      <Link to={`/series/${series.id}`} className="work-card__cover-link" aria-label={series.name} />
      <div className="series-card__covers">
        {works.slice(0, COVER_COUNT).map((w) => (
          <WorkCover title={w.title} coverUrl={w.coverUrl} size="sm" key={w.id} />
        ))}
      </div>
      <div className="series-card__content">
        <div className="series-card__title">
          {series.name}
          <span className="entity-list__count">{series.workCount}作</span>
        </div>
        {first && (
          <div className="work-card__meta">
            <span className={`season-badge season-badge--quiet season-badge--${first.quarter}`}>
              {last && (last.year !== first.year || last.quarter !== first.quarter)
                ? `${seasonLabel(first)}〜${seasonLabel(last)}`
                : seasonLabel(first)}
            </span>{" "}
            {studios.slice(0, STUDIO_COUNT).join("・")}
            {studios.length > STUDIO_COUNT && ` ほか${studios.length - STUDIO_COUNT}社`}
          </div>
        )}
        {themes.length > 0 && (
          <div className="chip-row">
            {themes.map(([id, t]) => (
              <Link className="chip" to={`/themes/${id}`} key={id}>
                {t.name}
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
