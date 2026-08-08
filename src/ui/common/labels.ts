import type { OriginalType, SeasonQuarter, WorkGenerated } from "../../types";

export const QUARTER_LABEL: Record<SeasonQuarter, string> = {
  winter: "冬",
  spring: "春",
  summer: "夏",
  fall: "秋",
};

export const QUARTER_ORDER: Record<SeasonQuarter, number> = {
  winter: 0,
  spring: 1,
  summer: 2,
  fall: 3,
};

/** 「2024年夏」のような放送クールの表示文字列。 */
export function seasonLabel(season: { year: number; quarter: SeasonQuarter }): string {
  return `${season.year}年${QUARTER_LABEL[season.quarter]}`;
}

/** 年内のクール順まで含めた並べ替えキー(昇順)。 */
export function seasonSortKey(w: WorkGenerated): number {
  return w.season.year * 4 + QUARTER_ORDER[w.season.quarter];
}

export const ORIGINAL_TYPE_LABEL: Record<OriginalType, string> = {
  manga: "漫画原作",
  lightnovel: "ライトノベル原作",
  novel: "小説原作",
  game: "ゲーム原作",
  original: "オリジナル",
  other: "その他原作",
};

export const STATUS_LABEL: Record<string, string> = {
  completed: "放送終了",
  ongoing: "放送・制作中",
  unknown: "不明",
};

export const FORMAT_LABEL: Record<string, string> = {
  tv: "TVアニメ",
  movie: "劇場アニメ",
};
