# anime-db

TVアニメ・劇場アニメを制作スタジオ・監督・シリーズ構成・声優・放送クール・受賞歴・テーマから検索できるファンデータベース。姉妹サイト6番目(2026-08-08作成)。**年表(/timeline)機能はユーザー指示で2026-08-09に削除済み(再提案しない)**。scaffoldのコピー元は**mystery-db**(人物系エンティティが最多で改造距離が最短だったため)。アーキテクチャ・デザインシステム・運用ノウハウはranobe-db系列をそのまま踏襲している。

- 公開URL: https://izenmi.github.io/anime-db/
- リポジトリ: `izenmi/anime-db`(public。GitHub Pagesは無料枠だとpublicでないと使えない)
- スタック: React 18 + TypeScript + Vite 5 + `react-router-dom`(`BrowserRouter`)

## データモデル上の判断(このサイト固有・最重要)

- **シリーズ単位で1エントリ**。『鬼滅の刃』は1件で、分割クール・続編・派生劇場版は`broadcastNote`(自由記述)に書く
- **〈物語〉シリーズのような「作品をまたぐシリーズ」は`series.json`のエンティティ**(作品から`seriesId`で任意参照。2026-08-09にエンティティ化、それ以前の`seriesName`表示用テキストを置換)。`/series`に一覧・詳細ページ(作品は放送順固定)、ナビタブと作品一覧の絞り込みもある。劇場作品は**単独作品のみ**`format: "movie"`で登録する(TVシリーズの劇場版は登録しない)
- **`season` はシリーズ第1期の放送開始クール** `{ year, quarter: winter|spring|summer|fall }`。埋め込みフィールドで、エンティティ化していない(game-dbの`platforms`と同じ考え方)
- **`episodes`は第1期の話数**を基本とし、通算話数は書かない(未検証の数値を作らないため)
- **スタッフは単一ファイル2ロール方式**: `staff.json`を`directorIds`(必須≥1)と`seriesComposerIds`(任意)の両方から参照する(game-dbのcompanies.jsonと同じ設計。監督と構成の兼任が多い)。スタッフ詳細ページは「監督作品」「シリーズ構成作品」の2セクション
- **`studioIds`は必須≥1**(共同制作対応)。「アニメーション制作」のみを登録し、製作委員会・製作(出資)は登録しない
- **声優は各作品の主要キャスト最大5名まで**(`cast: [{voiceActorId, character}]`、役名必須)。裏取りコスト制御のための上限で、apply_batch.pyが6名以上を拒否する。声優詳細ページは役名つき出演一覧(放送順固定)
- **`originalType`**: `manga|lightnovel|novel|game|original|other`。原作種別フィルターと姉妹サイトリンクの軸
- **姉妹サイトリンクは4方向**: `relatedNovelUrl`(らのべDB)/`relatedComicUrl`(まんがDB)/`relatedMysteryUrl`(ミステリDB)/`relatedGameUrl`(ゲームDB)。**当面は手動設定**。manga-dbの`link-sister-works.mjs`への統合は未着手(下記「既知の未着手事項」)
- spoilerタグ機構はmystery-dbからそのまま維持(「どんでん返し」「意外な正体」の2タグのみspoiler)。レコメンドのスコア計算からも除外される

## データフロー(source → generated)

- `public/data/source/*.json` … 一次データ(works/staff/studios/voiceActors/themes/awards + covers-cache)
- `public/data/generated/*.json` … `scripts/generate-manifest.mjs`が生成(`.gitignore`対象)
- 生成スクリプトの検証(失敗するとビルドが落ちる): 全id参照整合 / `directorIds`・`studioIds`空配列不可 / `format`・`season.quarter`・`originalType`のenum検証 / cast役名必須

## データ取得パイプライン(AniList一本柱)

**AniList GraphQL(`https://graphql.anilist.co`、認証不要)がIGDB(game-db)の役割を担う。**

- **`scripts/anilist.py`** … 共有ラッパ。**User-Agent必須**(urllib既定UAはCloudflareに403で弾かれる。2026-08-08に実際に踏んだ)。レート制限は公式90req/分だが実測30req/分程度に絞られる時期があるため既定2.2秒スリープ+429時Retry-After尊重
- **`scripts/suggest_candidates.py`** … 「人気順で未登録のTVアニメ」をカタログに列挙させる。出力は`タイトル|anilistId`形式でそのままprobeに渡せる。**AniListはSeason 2等を別エントリで持つ**ので、シリーズ単位登録の本サイトでは**候補一覧から第1期だけを目視で選ぶ**こと
- **`scripts/probe_anilist.py`** … 主力裏取りツール。works.jsonとの重複判定(タイトル正規化+anilistId)を検索前に行いDUPはネットワークアクセスしない。1候補につきスタジオ(isMain)・監督・シリーズ構成・MAINキャスト(日本語声優)・クール・話数・キービジュアルを1リクエストで取る
  - **staffは1ページ25件しか取らないため、人気作では監督がページ外に落ちる**(呪術廻戦・けいおん!等で実際に発生)。probeで監督が空のときはAniListのstaff全ページ走査(使い捨てスクリプト)かWikipedia日本語版のinfoboxで補完する。**フリーレンの監督はAniListのstaff走査でも出てこず、Wikipedia「葬送のフリーレン (アニメ)」のinfoboxで確認した**
  - 監督ロールは`Director`/`Chief Director`のみ採用(`Episode Director`・`Assistant Director`・`Sound Director`等を混ぜない)。構成は`Series Composition`
  - **AniListの人名表記が日本のクレジットと違うことがある**。実例: 朴性厚がハングル表記(박성후)、イシグロキョウヘイが漢字表記(石黒恭平)。日本のクレジット表記で登録し、sourceNoteに書き残す
- **`scripts/fetch-covers.mjs`** … works.jsonの`anilistId`をキーに`Media(id:)`で直接引くため、タイトル検索ベースの姉妹サイトと違い**あいまいマッチの誤ヒットが構造的に起きない**。画像はAniList CDN(`s4.anilist.co`)へのホットリンク。検証は`content-type`+実バイト数(content-lengthヘッダはHTTP/2で返らないことがある)。`--only`/`--force`(非破壊、失敗時は既存維持`[keep]`)/`--retry-misses`
- **`scripts/apply_batch.py`** … キーは`newStaff`/`newStudios`/`newVoiceActors`/`newSeries`/`newThemes`/`newAwards`/`works`。**applyは1回だけ**、実行前に既存id衝突件数をレポートで確認する
- **`scripts/find_people.py --names 新海誠 MAPPA 花澤香菜`** … staff/studios/voiceActorsの既存idをJSON全体を読まずに引く。バッチ前に必ず通す
- あらすじは150〜250字で**必ず独自要約**(AniListのdescriptionも転記禁止)。書き出し後に`[Ѐ-ӿ가-힯]`と`[A-Za-z]{4,}`で機械点検する(シード投入時にこの点検が「剣technique」「VRMMORPG」の混入を実際に検出した)

## 購入リンク・画像

- 購入リンクは`amazonSearchUrl(title, "Blu-ray")`(`src/ui/common/WorkCover.tsx`)の検索URLのみ。アフィリエイトタグ`izenmi-22`(姉妹サイト共通)。ISBNベースの直リンク機構は書籍でないため撤去した
- **配信リンクも検索URL方式のみ**(movie-dbと同じ思想): `netflixSearchUrl`/`primeVideoSearchUrl`(Amazonの`i=instant-video`検索、アフィリエイトタグ有効)/`danimeSearchUrl`(dアニメストア`sch_pc?searchKey=`)。配信有無はラインアップ変動で誤リンク化するため意図的にデータ化しない
- キービジュアルはAniListのcoverImage(縦長460×650前後)で、既存の表紙枠CSSがそのまま合う。**公式商品画像ではなくキーアートの転載になるため、Aboutページに出典と削除対応の記載を置いている**。楽天ブックス/Kobo/BOOK☆WALKER経路は書籍でないため使っていない(楽天の認証情報も本サイトでは不要)

## デザイン方針

- **メインアクセントは桜ピンク(`--color-sakura`/`-strong`/`-deep`)**。ranobe-db水色・manga-dbオレンジ・game-dbグリーン・mystery-db藤色・tech-dbティールと区別。装飾用パステルの`--color-pink`とは別変数
- **放送クールバッジ(`.season-badge`、冬=blue/春=sakura/夏=mint/秋=peach/劇場=purple)**はgame-dbの機種バッジと同じ発想の専用小パレット
- ページ背景は黒一色固定、装飾最小、見出し`M PLUS Rounded 1c`。favicon(`public/favicon.svg`)は黒背景+「ア」の1文字ロゴ(`#ff86ad`)。**mystery-dbと同じ全面塗り(角丸なし)**でアルファを残さない
- Google Analytics: **未設置**。anime-db専用のGA4測定IDが発行されたら`index.html`のコメント位置にgtagスニペットを追加する(姉妹サイトのIDは流用しない)

## コマンド

```sh
npm install
npm run dev       # http://localhost:5173/anime-db/
npm run build      # 型チェック + データ整合性チェック + ビルド + プリレンダー
npm run preview
npm run fetch-covers
node scripts/generate-ogp.mjs    # 手動実行
node scripts/generate-icons.mjs  # 手動実行
```

`main`へのpushで`.github/workflows/deploy.yml`が自動ビルド・GitHub Pagesデプロイを行う。SEO/SSG(useSeo・prerender.mjs・sitemap生成・SITE_ORIGIN定数の理由)はmystery-dbのCLAUDE.mdの記述がそのまま当てはまる。

## データ規模の推移

26作品(初回シード、2026-08-08)。スタッフ40・スタジオ17・声優84・テーマ32(うちspoiler 2)・アワード5。TV24作品・劇場2作品。キービジュアルは26/26(100%)解決。全作品をAniListで裏取りし、probeで監督が欠けた10作品はAniListスタッフ全ページ走査+Wikipediaで補完した。受賞歴は未登録(下記)。

## 既知の未着手事項

- **受賞歴が0件**。awards.jsonに5賞(東京アニメアワード・アニメグランプリ・ニュータイプアニメアワード・文化庁メディア芸術祭・クランチロール)を用意済みだが、`awardResults`は未投入。取り込みは姉妹サイト共通の受賞パイプライン(Wikipediaの賞ページを正とし、**既存作品への付与→未登録作の追加の2段構え**)で行うこと
- **`link-sister-works.mjs`(manga-db)へのアニメ原作突合の統合**。現在は`relatedNovelUrl`等を手動設定している(シード26作品中20件設定済み)。逆方向(姉妹サイト側から本サイトへのリンク)は未設定
- **GA4測定IDが未発行**(ユーザーのGoogleアカウント操作が必要)
- **Google Search Consoleへのsitemap登録**(ユーザー操作が必要)
