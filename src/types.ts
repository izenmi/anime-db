// ---- source data (public/data/source/*.json, hand-authored, committed) ----

export interface ExternalLinks {
  wikipediaUrl?: string;
  officialUrl?: string;
}

export interface AwardResult {
  awardId: string;
  year: number;
  result: string; // free text: "グランプリ" / "作品賞" / "第1位" など
}

/** 放送終了 / 放送・制作継続中 / 不明。シリーズ単位登録なので「続編制作決定」も ongoing。 */
export type WorkStatus = "completed" | "ongoing" | "unknown";

export type SeasonQuarter = "winter" | "spring" | "summer" | "fall";

/** TVシリーズか、単独の劇場作品か。劇場版はTVシリーズの一部として扱い、単独作品のみ movie。 */
export type WorkFormat = "tv" | "movie" | "ova" | "ona";

/** 原作メディアの種別。姉妹サイトへの相互リンクとフィルターの軸。 */
export type OriginalType = "manga" | "lightnovel" | "novel" | "game" | "original" | "other";

export interface CastCredit {
  voiceActorId: string;
  /** 演じたキャラクター名。 */
  character: string;
}

export interface WorkSource {
  id: string;
  title: string;
  titleKana: string;
  /** 監督(ids into staff.json)。共同監督対応、最低1名必須。 */
  directorIds: string[];
  /** シリーズ構成(ids into staff.json)。明示クレジットがない作品では空でよい。 */
  seriesComposerIds: string[];
  /** アニメーション制作スタジオ(ids into studios.json)。共同制作対応、最低1社必須。 */
  studioIds: string[];
  /** 主要キャスト。裏取りコストを抑えるためMAIN級最大5名までにとどめる。 */
  cast: CastCredit[];
  themeIds: string[];
  /** 所属シリーズ(id into series.json)。単発作品では省略。 */
  seriesId?: string;
  format: WorkFormat;
  /** 放送開始クール(第1期)。劇場作品は公開年+公開時期のクール。 */
  season: { year: number; quarter: SeasonQuarter };
  /** シリーズ通算の期数。`scripts/backfill_seasons.py` が SEQUEL 連鎖から機械的に付ける派生値で、
   *  broadcastNote の「第N期」と同じ数え方(分割クールは1期と数える)。1期だけの作品では省略。 */
  seasonCount?: number;
  /** 最新シーズンの放送クール。作品一覧では `season`(第1期)ではなくこちらを見せる —
   *  長寿シリーズほど第1期の年は古く、いつまで続いているかが読めないため。
   *  同じく backfill_seasons.py が付ける派生値で、`season` と同じなら省略(読み手側で補う)。 */
  latestSeason?: { year: number; quarter: SeasonQuarter };
  /** 話数。続編・分割クールを含むシリーズ通算の概数でよい(注記はbroadcastNoteへ)。 */
  episodes?: number;
  /** 第2期・劇場版などシリーズ展開の自由記述。 */
  broadcastNote?: string;
  originalType: OriginalType;
  status: WorkStatus;
  /** 150〜250 chars, written from scratch. */
  synopsis: string;
  awardResults?: AwardResult[];
  /** AniListの作品ID。fetch-covers.mjs がキービジュアル取得のキーに使う(あいまい検索を避ける)。 */
  anilistId?: number;
  /** 姉妹サイトの原作作品ページへの相互リンク(当面は手動設定)。 */
  relatedNovelUrl?: string;
  relatedComicUrl?: string;
  relatedMysteryUrl?: string;
  relatedGameUrl?: string;
  externalLinks: ExternalLinks;
  sourceNote: string;
  updatedAt: string;
}

/** 監督・シリーズ構成の人物。game-dbのcompanies.jsonと同じ「単一ファイル複数ロール」方式で、
 *  directorIds と seriesComposerIds の両方から参照される(兼任が多いため)。 */
export interface StaffSource {
  id: string;
  name: string;
  nameKana: string;
  description: string;
  birthYear?: number;
  externalLinks: ExternalLinks;
  sourceNote: string;
  updatedAt: string;
}

export interface StudioSource {
  id: string;
  name: string;
  nameKana: string;
  parentCompany?: string;
  description: string;
  foundedYear?: number;
  externalLinks: ExternalLinks;
  sourceNote: string;
  updatedAt: string;
}

export type VoiceActorSource = StaffSource;

/** シリーズ(〈物語〉シリーズ等)。1作でも「シリーズものである」ことに意味があるので、
 *  該当作品が1本でもエンティティ化してよい。 */
export interface SeriesSource {
  id: string;
  name: string;
  nameKana: string;
  description?: string;
  externalLinks: ExternalLinks;
  sourceNote: string;
  updatedAt: string;
}

export interface ThemeSource {
  id: string;
  name: string;
  description?: string;
  /** そのタグが付いていると知ること自体が展開のネタバレになるもの(どんでん返し等)だけ true。 */
  spoiler?: boolean;
}

export interface AwardSource {
  id: string;
  name: string;
  organizer: string;
  description: string;
  firstYear?: number;
  externalLinks: ExternalLinks;
  sourceNote: string;
  updatedAt: string;
}

// ---- generated data (public/data/generated/*.json, built by scripts/generate-manifest.mjs) ----

export interface CastCreditGenerated extends CastCredit {
  voiceActorName: string;
}

/** Denormalized work: source fields plus resolved names for direct rendering. */
/** あらすじ・出典メモ・updatedAt は含まない — 作品詳細ページでしか使わないのに works.json の
 *  大きな割合を占めていたので work-texts.json に分けてある(WorkTexts / getWorkTexts)。 */
export interface WorkGenerated extends Omit<WorkSource, "synopsis" | "sourceNote" | "updatedAt"> {
  directorNames: string[];
  /** Resolved from seriesId at build time; absent for standalone works. */
  seriesName?: string;
  seriesComposerNames: string[];
  studioNames: string[];
  castGenerated: CastCreditGenerated[];
  themeNames: string[];
  /** Ids of this work's themes that carry `spoiler: true`, so WorkCard can drop them without
   *  having to fetch themes.json itself. */
  spoilerThemeIds: string[];
  awardSummaries: { awardId: string; awardName: string; year: number; result: string }[];
  /** Resolved at build time from public/data/source/covers-cache.json (see scripts/fetch-covers.mjs).
   *  Absent when no key visual could be matched — callers must fall back to the placeholder. */
  coverUrl?: string;
  /** Ids of similar works, best first, computed at build time by generate-manifest.mjs.
   *  Only present in generated/works.json — the copies embedded in the cross-reference lists
   *  omit it to keep those files small. */
  relatedWorkIds?: string[];
}

/** スタッフ詳細ページ用: 監督作品とシリーズ構成作品を分けて持つ(game-dbのroles方式)。 */
export interface StaffGenerated {
  id: string;
  name: string;
  nameKana: string;
  description: string;
  externalLinks: ExternalLinks;
  workCount: number;
  /** 実データは works.json 側。表示側で id から引き直す。 */
  directedWorkIds: string[];
  composedWorkIds: string[];
}

export interface StudioGenerated {
  id: string;
  name: string;
  nameKana: string;
  description: string;
  externalLinks: ExternalLinks;
  workCount: number;
  /** 実データは works.json 側。表示側で id から引き直す。 */
  workIds: string[];
}

export interface VoiceActorRole {
  character: string;
  /** 実データは works.json 側。表示側で id から引き直す。 */
  workId: string;
}

export interface VoiceActorGenerated {
  id: string;
  name: string;
  nameKana: string;
  description: string;
  externalLinks: ExternalLinks;
  workCount: number;
  /** Sorted by season.year ascending — the order the actor's filmography unfolded. */
  roles: VoiceActorRole[];
}

export interface SeriesGenerated {
  id: string;
  name: string;
  nameKana: string;
  description?: string;
  externalLinks: ExternalLinks;
  workCount: number;
  /** Sorted by season ascending — シリーズを追う順で固定表示するため。 */
  /** 実データは works.json 側。表示側で id から引き直す。 */
  workIds: string[];
}

export interface ThemeGenerated extends ThemeSource {
  workCount: number;
  /** 実データは works.json 側。表示側で id から引き直す。 */
  workIds: string[];
}

export interface AwardWinner {
  workId: string;
  workTitle: string;
  year: number;
  result: string;
  /** 並べ替え用に result から取り出した順位。順位表記がないものは大賞系=0 / その他=900。 */
  rank: number;
}

export interface AwardGenerated extends AwardSource {
  workCount: number;
  winners: AwardWinner[];
}

/** 作品詳細ページだけが読む長文(generated/work-texts.json)。キーは作品id。 */
export type WorkTexts = Record<string, { synopsis: string; sourceNote: string }>;

export interface Counts {
  works: number;
  series: number;
  staff: number;
  studios: number;
  voiceActors: number;
  themes: number;
  awards: number;
}
