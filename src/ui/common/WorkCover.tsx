import { useState } from "react";

const COVER_COLORS = ["blue", "pink", "mint", "yellow", "peach", "purple"] as const;

function colorFor(title: string): (typeof COVER_COLORS)[number] {
  let sum = 0;
  for (let i = 0; i < title.length; i++) sum += title.charCodeAt(i);
  return COVER_COLORS[sum % COVER_COLORS.length];
}

/** Real key visual when one was resolved (public/data/source/covers-cache.json, built by
 *  `npm run fetch-covers` — see scripts/fetch-covers.mjs), falling back to a generated
 *  placeholder (title on a pastel card) when absent or the image fails to load. We don't host
 *  the artwork ourselves; the cache stores AniList CDN URLs, so a broken/removed image
 *  degrades back to the placeholder automatically. */
export function WorkCover({ title, coverUrl, size = "sm" }: { title: string; coverUrl?: string; size?: "sm" | "lg" }) {
  const [broken, setBroken] = useState(false);
  if (coverUrl && !broken) {
    return (
      <img
        className={`work-cover work-cover--${size} work-cover--image`}
        src={coverUrl}
        alt={title}
        loading="lazy"
        onError={() => setBroken(true)}
      />
    );
  }
  return (
    <div className={`work-cover work-cover--${size} work-cover--${colorFor(title)}`}>
      <span className="work-cover__title">{title}</span>
    </div>
  );
}

const AMAZON_AFFILIATE_TAG = "izenmi-22";

/** Amazonへの購入リンク(検索URL形式のみ)。アニメはシリーズ単位登録でBD/DVDの版が多数あるため、
 *  個別商品ページへの直リンクは持たない。`extra` は「Blu-ray」等の絞り込み語。 */
export function amazonSearchUrl(title: string, extra?: string): string {
  const query = extra ? `${title} ${extra}` : title;
  const params = new URLSearchParams({ k: query, tag: AMAZON_AFFILIATE_TAG });
  return `https://www.amazon.co.jp/s?${params.toString()}`;
}

/** 配信サービスへのリンクも検索URL形式のみ(movie-dbと同じ思想)。作品ごとの配信有無・
 *  配信先IDを持つとラインアップ変動で古くなる(=誤リンクになる)ため、意図的にデータ化しない。 */
export function netflixSearchUrl(title: string): string {
  return `https://www.netflix.com/search?q=${encodeURIComponent(title)}`;
}

/** Prime VideoはAmazonの動画カテゴリ検索(i=instant-video)。アフィリエイトタグも有効。 */
export function primeVideoSearchUrl(title: string): string {
  const params = new URLSearchParams({ k: title, i: "instant-video", tag: AMAZON_AFFILIATE_TAG });
  return `https://www.amazon.co.jp/s?${params.toString()}`;
}

export function danimeSearchUrl(title: string): string {
  return `https://animestore.docomo.ne.jp/animestore/sch_pc?searchKey=${encodeURIComponent(title)}`;
}
