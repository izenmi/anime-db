import { useMemo } from "react";
import { Link } from "react-router-dom";
import { getWorks } from "../../data/manifest";
import { useAsyncData } from "../common/useAsyncData";
import { Loading, ErrorState, EmptyState } from "../common/Status";
import { colorForYear } from "../common/yearColor";
import { QUARTER_LABEL, QUARTER_ORDER, seasonSortKey } from "../common/labels";
import { useSeo } from "../common/useSeo";
import type { SeasonQuarter, WorkGenerated } from "../../types";

interface QuarterGroup {
  quarter: SeasonQuarter;
  works: WorkGenerated[];
}

interface YearGroup {
  year: number;
  quarters: QuarterGroup[];
}

/** 放送クール年表: 年(降順)→クール(冬→春→夏→秋)で全作品をグルーピングした一枚もの。
 *  「あのクールに何をやっていたか」を辿るページなのでカードではなくコンパクトなリスト表示。 */
export function TimelinePage() {
  const worksState = useAsyncData(getWorks, []);

  const years = useMemo<YearGroup[]>(() => {
    if (worksState.status !== "ready") return [];
    const byYear = new Map<number, Map<SeasonQuarter, WorkGenerated[]>>();
    for (const w of worksState.data) {
      if (!byYear.has(w.season.year)) byYear.set(w.season.year, new Map());
      const quarters = byYear.get(w.season.year)!;
      if (!quarters.has(w.season.quarter)) quarters.set(w.season.quarter, []);
      quarters.get(w.season.quarter)!.push(w);
    }
    return [...byYear.entries()]
      .sort((a, b) => b[0] - a[0])
      .map(([year, quarters]) => ({
        year,
        quarters: [...quarters.entries()]
          .sort((a, b) => QUARTER_ORDER[a[0]] - QUARTER_ORDER[b[0]])
          .map(([quarter, list]) => ({
            quarter,
            works: [...list].sort((a, b) => seasonSortKey(a) - seasonSortKey(b) || a.titleKana.localeCompare(b.titleKana, "ja")),
          })),
      }));
  }, [worksState]);

  useSeo({
    title: "放送クール年表",
    description:
      worksState.status === "ready"
        ? `収録アニメ${worksState.data.length}作品を放送クール(年×季節)ごとに並べた年表。各クールの作品を一望できます。`
        : undefined,
  });

  return (
    <div className="page">
      <h1>放送クール年表</h1>
      {worksState.status === "loading" && <Loading />}
      {worksState.status === "error" && <ErrorState error={worksState.error} />}
      {worksState.status === "ready" && years.length === 0 && <EmptyState />}
      {worksState.status === "ready" && years.length > 0 && (
        <>
          <p className="page-subtitle">{worksState.data.length}作品</p>
          {years.map((yearGroup) => (
            <div className="home-section" key={yearGroup.year}>
              <h2 className="home-section__heading font-display">
                <span className={`winner-year winner-year--${colorForYear(yearGroup.year)}`}>{yearGroup.year}</span>年
              </h2>
              {yearGroup.quarters.map((quarterGroup) => (
                <div key={quarterGroup.quarter}>
                  <h3 className="timeline-quarter">
                    <span className={`season-badge season-badge--${quarterGroup.quarter}`}>
                      {QUARTER_LABEL[quarterGroup.quarter]}
                    </span>
                  </h3>
                  <ul className="winner-list">
                    {quarterGroup.works.map((w) => (
                      <li key={w.id}>
                        <Link to={`/works/${w.id}`}>{w.title}</Link>
                        <span className="entity-list__count">
                          {" "}
                          {w.studioNames.join("・")}
                          {w.format === "movie" && " / 劇場"}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          ))}
        </>
      )}
    </div>
  );
}
