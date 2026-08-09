# anime-db

TVアニメ・劇場アニメを制作スタジオ・監督・シリーズ構成・声優・放送クール・受賞歴・テーマから検索できるファンデータベース。姉妹サイト6番目(2026-08-08作成)。**年表(/timeline)機能はユーザー指示で2026-08-09に削除済み(再提案しない)**。scaffoldのコピー元は**mystery-db**(人物系エンティティが最多で改造距離が最短だったため)。アーキテクチャ・デザインシステム・運用ノウハウはranobe-db系列をそのまま踏襲している。

- 公開URL: https://izenmi.github.io/anime-db/
- リポジトリ: `izenmi/anime-db`(public。GitHub Pagesは無料枠だとpublicでないと使えない)
- スタック: React 18 + TypeScript + Vite 5 + `react-router-dom`(`BrowserRouter`)

## データモデル上の判断(このサイト固有・最重要)

- **シリーズ単位で1エントリ**。『鬼滅の刃』は1件で、分割クール・続編・派生劇場版は`broadcastNote`(自由記述)に書く
- **シリーズは24件・99作品に付与済み**(2026-08-09)。プリキュア17・ガンダム10・Fate7など。機械的な接頭辞一致では『異世界〜』『魔法少女〜』が大量に誤検出されるので、**実在フランチャイズを列挙して突合する方式**にした
- **〈物語〉シリーズのような「作品をまたぐシリーズ」は`series.json`のエンティティ**(作品から`seriesId`で任意参照。2026-08-09にエンティティ化、それ以前の`seriesName`表示用テキストを置換)。`/series`に一覧・詳細ページ(**一覧は収録作品数の多い順、詳細内の作品は新しい順**で固定)、ナビタブと作品一覧の絞り込みもある。劇場作品は**単独作品のみ**`format: "movie"`で登録する(TVシリーズの劇場版は登録しない)
- **`season` はシリーズ第1期の放送開始クール** `{ year, quarter: winter|spring|summer|fall }`。埋め込みフィールドで、エンティティ化していない(game-dbの`platforms`と同じ考え方)
- **`seasonCount`(期数)と`latestSeason`(最新シーズンのクール)は`scripts/backfill_seasons.py`が入れる派生データ**。手書き禁止(broadcastNoteの「第N期」とずれる)。1期だけ/第1期と同じクールなら省略する。**作品一覧のカードは`season`ではなく`latestSeason`を出す**(下記「一覧の日付は最新シーズン」)
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
### 1000作品規模の一括追加パイプライン(2026-08-09に追加)

`suggest_candidates.py` + `probe_anilist.py` は1件1リクエストのため1000件規模だと40分以上かかる。
大量投入用に以下を新設した(**既存の2本もそのまま残してある**。少量の追加にはそちらが手軽)。

- **`scripts/harvest_anilist.py`** … 人気順カタログを**1リクエスト50作品**で収穫し、候補プール
  (`scripts/.cache/pool.json`)に貯める。60ページ=3000作品で約20分。何度実行しても追記マージ
- **`scripts/fill_directors.py`** … 監督が取れなかった候補を `media(id_in:)` で25件ずつまとめて
  staffの次ページを追う。上位2125件のうち335件が監督欠けだったが、8ページまで追って56件まで減った
- **`scripts/jp_romaji.py`** … ヘボン式ローマ字→ひらがな。AniListの `name.full` / `title.romaji` は
  **実際の読み**なので、そこから `nameKana` / `titleKana` を機械生成できる(漢字からの読み推定と違い
  「梶裕貴→かじひろたか」のような誤読が起きない)。変換できなければ None を返して手動送りにする。
  `slug()`(そのまま)と `person_slug()`(長音を縮めて既存の `araki-tetsuro` 形に合わせる)は**別物**で、
  人名以外に `person_slug` を使うと `Tokyo Ghoul → tokyo-ghol` と英単語が壊れる
- **`scripts/batch_tool.py stage N` / `finalize N` / `drop N <id...>`** … プールからN件取り出して
  あらすじ以外を埋めた `batchNNN.json` と、人が埋める項目だけの `batchNNN.ask.txt` を書く。
  `batchNNN.meta.json`(`{"<作品id>": {"s": あらすじ, "k": かな}, "STUDIO"/"PERSON"/"PERSON_NAME"/"SERIES": {...}}`)
  を合流させて apply する。**あらすじの長さ・キリル文字や英単語の混入・かな欠けを検査し、1件でも
  引っかかればバッチ全体をapplyしない**(実際に「три年間」「distance を越えた」等の混入を多数検出した)
- **`scripts/studio_alias.json` / `person_alias.json` / `studio_kana.json`** … AniListの表記と既存
  データの表記のずれを吸収する。AniListはラテン表記(`MADHOUSE`)、既存は日本語表記(`マッドハウス`)の
  ことがあるため、**スラッグが既存idと一致したら同じスタジオとみなす**のが基本ルール。綴りがずれる
  社名(`Tatsunoko Production`→`tatsunoko`、`CoMix Wave`→`comix-wave-films`)だけaliasで対応。
  人物側も同様(`박성후`→`park-sung-hoo`)。**スタジオ名は英単語なのでromaji変換を使ってはいけない**
  (`bones`→`ぼねす`になる)。かなは `studio_kana.json` に貯めて再利用する

#### 続編・劇場版を弾く判定(ここが一番手を焼いた)

シリーズ単位1エントリを守るための除外判定。**relations は使えない**(第1期の側にも SIDE_STORY・
SUMMARY・PREQUEL がぶら下がるため、『DEATH NOTE』『ONE PIECE』『呪術廻戦』の第1期まで落ちた)。
最終的に4つを併用している:

1. **タイトルの前方一致**(`same_franchise`)。native と romaji の両方で成立することを要求して
   「トリコ」と「トリコロール」のような偶然の一致を弾く。閾値は2文字(『銀魂』と『銀魂゜』のため)
2. **語幹どうしの比較**。両方に副題が付く『かぐや様は告らせたい～天才たちの…』と
   『かぐや様は告らせたい-ウルトラロマンティック-』は前方一致では引っかからない
3. **ローマ字の本編名の一致**。『Magi: The Labyrinth of Magic』と『Magi: The Kingdom of Magic』のように
   邦題が2文字で閾値に届かないケースを拾う。投入済み作品のローマ字語幹は `.cache/applied_keys.json` に貯める
4. **続編マーカーの明示除外**(`第2期` `セカンドシーズン` `Season 2` 等)と**劇場版マーカー**
   (`劇場版` `映画` `総集編`)。第1期が未登録でも、第2期をシリーズ代表として登録するのは避ける

**AniListの役職名は `Director (eps 1-278)` のように担当話数が付くことがある**。役職を完全一致で見ていたため、
『ONE PIECE』『名探偵コナン』『銀魂』『クレヨンしんちゃん』のような長期シリーズが「監督なし」と判定され、
stage が skip.json に落として**140作品を丸ごと取りこぼしていた**(2026-08-09に `role_key()` を入れて修正)。
`fill_directors.py` も既定で1ページ目からやり直すようにしてある。

それでも `stage` の一覧を目視すると数件は残る(『傷物語』の分割公開、『K RETURN OF KINGS』のように
本編名が1文字の続編、『NOMAD メガロボクス2』等)。**`batch_tool.py drop` で間引く前提**で運用する。

### broadcastNote の一括生成(`scripts/backfill_broadcast_note.py`)

シリーズ単位1エントリという方針上、第2期以降は本文ではなく `broadcastNote` に書く。この作業は
**AniListの `relations` から `SEQUEL` の連鎖を辿って自動生成できる**。

- `media(id_in:)` を25件ずつ、SEQUEL先も再帰的に取得。関係データは `.cache/relations.json` にキャッシュするので再実行は無料
- 末尾が `が制作されている。` のものを自動生成と見なして毎回作り直す。手書きの note は上書きしない
- **分割クールを別の期として数えない**のが肝。共通接頭辞が長く(5文字以上かつ短い方の6割以上)、
  かつ残りが期数表記(`2` `Ⅱ` `2nd` 等)でないものは同じ期の続きとして扱い、期数を振らずに作品名だけ並べる。
  この判定を入れる前は『BLEACH 千年血戦篇-訣別譚-』を第3期、『炎炎ノ消防隊 参ノ章 第2クール』を第4期と誤って数えていた
- 続編がすでに独立した作品として works.json にある場合は、そこで連鎖を打ち切る(二重掲載になるため)

### 一覧の日付は最新シーズン(`scripts/backfill_seasons.py`、2026-08-09)

シリーズ単位1エントリなので、`season`(第1期)をそのまま一覧に出すと『銀魂』が「2006年春」、
『僕のヒーローアカデミア』が「2016年春」になり、**まだ続いている作品ほど古く見える**。そこで
一覧のカードには**最新シーズンのクールと「全N期」**を出す。

- 期数の数え方は broadcastNote と**完全に同じロジックを共有**する(`scripts/season_chain.py`の
  `numbered_chain`)。分割クールを別の期に数えない判定もここ1か所にある。カードの「全4期」と
  noteの「第4期『…』」が食い違うのが一番まずいので、2本目の実装を書かないこと
- 続編のクールは AniList の `season`/`seasonYear`(無ければ `startDate.month`)。`.cache/seasons.json`
  にキャッシュするので再実行は無料。`backfill_broadcast_note.py` を流した後に続けて実行する
- **未放送でも放送予定クールが判明していれば `latestSeason` に入る**(2026-08-09時点で8作品)。
  「放送時期が新しい順」では『葬送のフリーレン』(2027年秋)のような放送予定作が先頭に来る
- フロント側は `displaySeason(w) = w.latestSeason ?? w.season`(`src/ui/common/labels.ts`)を通す。
  **カードの日付・並べ替え(`seasonSortKey`)・クール絞り込みの3つを同じ値に揃えてある**
  (「春アニメ」で絞ったのに「2022年冬」のカードが並ぶのを避けるため)。作品詳細のバッジだけは
  放送開始クールのままで、「全8期(最新 2018年夏)」を併記して一覧と突き合わせられるようにしている。
  声優の出演歴やシリーズ内の並び(generate-manifest.mjs の `bySeason`)は「始まった順」に見たいので
  `season` のまま

- あらすじは150〜250字で**必ず独自要約**(AniListのdescriptionも転記禁止)。書き出し後に`[Ѐ-ӿ가-힯]`と`[A-Za-z]{4,}`で機械点検する(シード投入時にこの点検が「剣technique」「VRMMORPG」の混入を実際に検出した)

## 購入リンク・画像

- 購入リンクは`amazonSearchUrl(title, "Blu-ray")`(`src/ui/common/WorkCover.tsx`)の検索URLのみ。アフィリエイトタグ`izenmi-22`(姉妹サイト共通)。ISBNベースの直リンク機構は書籍でないため撤去した
- **配信リンクも検索URL方式のみ**(movie-dbと同じ思想): `netflixSearchUrl`/`primeVideoSearchUrl`(Amazonの`i=instant-video`検索、アフィリエイトタグ有効)/`danimeSearchUrl`(dアニメストア`sch_pc?searchKey=`)。配信有無はラインアップ変動で誤リンク化するため意図的にデータ化しない
- キービジュアルはAniListのcoverImage(縦長460×650前後)で、既存の表紙枠CSSがそのまま合う。**公式商品画像ではなくキーアートの転載になるため、Aboutページに出典と削除対応の記載を置いている**。楽天ブックス/Kobo/BOOK☆WALKER経路は書籍でないため使っていない(楽天の認証情報も本サイトでは不要)

## デザイン方針

- **メインアクセントは桜ピンク(`--color-sakura`/`-strong`/`-deep`)**。ranobe-db水色・manga-dbオレンジ・game-dbグリーン・mystery-db藤色・tech-dbティールと区別。装飾用パステルの`--color-pink`とは別変数
- **放送クールバッジ(`.season-badge`、冬=blue/春=sakura/夏=mint/秋=peach/劇場=purple)**はgame-dbの機種バッジと同じ発想の専用小パレット。ただし**作品カードでは`.season-badge--quiet`を併用して枠線だけのラベルにする**(一覧では作品名とスタッフを先に読ませたいため。塗るのは作品詳細だけ)
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

- 26作品(初回シード、2026-08-08)。スタッフ40・スタジオ17・声優84
- **1028作品(2026-08-09に1002作品を一括追加)**。スタッフ672・スタジオ193・声優889・テーマ32・アワード5。TV952作品・劇場76作品、放送年は1979〜2026年。原作種別は漫画482・ライトノベル283・オリジナル153・その他62・ゲーム47
- **2883作品(同じく2026-08-09に、AniList人気順1〜5000位を収穫しきって1855作品を追加)**。スタッフ1308・スタジオ391・声優1946。TV2587作品・劇場296作品、放送年は1958〜2026年。原作種別は漫画1242・オリジナル634・ライトノベル445・その他302・ゲーム259。`broadcastNote`は565作品に自動付与
  - **AniListの人気順クエリは5000件で打ち切られる**ため、この帯はこれで枯れた。さらに増やすには年別・ジャンル別・スコア順にクエリを切り直す必要があるが、その先は個人制作ONA・幼児向け短編・成人向けが中心になり収録基準が落ちる

一括追加は下記の**収穫→バッチ**パイプラインで行った。**あらすじだけを人が書き、他は全部機械で埋める**のが設計の要。

## 既知の未着手事項

- **受賞歴は197件/128作品を投入済み**(2026-08-09)。`scripts/harvest_awards.py`(5賞ぶんのWikipedia抽出) → `scripts/apply_awards.py`(既存作品への付与)で入れた。
  - 賞ページは**5賞とも書式が違う**(箇条書き・wikitable・`{{Award category}}`テンプレート)ので、賞ごとに専用の抽出関数を書いてある
  - **続編・劇場版の受賞は本編エントリに寄せる**(独立エントリを作らない方針のため)。どの期・どの劇場版が受賞したかは`result`に括弧書きで残す
  - **未反映が87件残っている**。内訳は文化庁メディア芸術祭の個人制作短編(収録基準外)、海外作品、OVA・ONA作品(『戦闘妖精雪風』『DEVILMAN crybaby』等)、未登録のTVシリーズ(『聖闘士星矢』『負けヒロインが多すぎる!』『アオのハコ』等)
- **`link-sister-works.mjs`(manga-db)へのアニメ原作突合の統合**。現在は`relatedNovelUrl`等を手動設定している(シード26作品中20件設定済み)。逆方向(姉妹サイト側から本サイトへのリンク)は未設定
- **GA4測定IDが未発行**(ユーザーのGoogleアカウント操作が必要)
- **Google Search Consoleへのsitemap登録**(ユーザー操作が必要)
