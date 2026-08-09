#!/usr/bin/env python3
"""ヘボン式ローマ字 → ひらがな の決定的変換。

AniListが持つ `name.full`(人名のローマ字)や `title.romaji` は**実際の読み**なので、
そこから `nameKana` / `titleKana` を機械生成できる(漢字から読みを推定するのと違い、
「梶裕貴 → かじひろたか」のような誤読が起きない)。1000作品規模の投入で人手を使わない
ためのキモなので、変換できない文字が1つでもあれば None を返して**呼び出し側に手動入力を
促す**(黙って壊れたかなを作らない)。

  romaji_to_hiragana("Yuuki Kaji")      -> "ゆうきかじ"
  romaji_to_hiragana("Shingeki no Kyojin") -> "しんげきのきょじん"
  romaji_to_hiragana("Steins;Gate")     -> None
"""
import re
import unicodedata

_MACRON = str.maketrans({"ā": "aa", "ī": "ii", "ū": "uu", "ē": "ee", "ō": "ou",
                         "â": "aa", "î": "ii", "û": "uu", "ê": "ee", "ô": "ou"})

# 3文字→2文字→1文字の順に最長一致で食わせる
TABLE = {
    "kya": "きゃ", "kyu": "きゅ", "kyo": "きょ", "kye": "きぇ",
    "gya": "ぎゃ", "gyu": "ぎゅ", "gyo": "ぎょ",
    "sha": "しゃ", "shu": "しゅ", "sho": "しょ", "she": "しぇ", "shi": "し",
    "sya": "しゃ", "syu": "しゅ", "syo": "しょ",
    "ja": "じゃ", "ju": "じゅ", "jo": "じょ", "je": "じぇ", "ji": "じ",
    "jya": "じゃ", "jyu": "じゅ", "jyo": "じょ",
    "cha": "ちゃ", "chu": "ちゅ", "cho": "ちょ", "che": "ちぇ", "chi": "ち",
    "tya": "ちゃ", "tyu": "ちゅ", "tyo": "ちょ",
    "tsu": "つ", "tsa": "つぁ", "tso": "つぉ",
    "nya": "にゃ", "nyu": "にゅ", "nyo": "にょ",
    "hya": "ひゃ", "hyu": "ひゅ", "hyo": "ひょ",
    "bya": "びゃ", "byu": "びゅ", "byo": "びょ",
    "pya": "ぴゃ", "pyu": "ぴゅ", "pyo": "ぴょ",
    "mya": "みゃ", "myu": "みゅ", "myo": "みょ",
    "rya": "りゃ", "ryu": "りゅ", "ryo": "りょ",
    "fyu": "ふゅ", "vyu": "ゔゅ",
    "dya": "ぢゃ", "dyu": "ぢゅ", "dyo": "ぢょ",
    "ka": "か", "ki": "き", "ku": "く", "ke": "け", "ko": "こ",
    "ga": "が", "gi": "ぎ", "gu": "ぐ", "ge": "げ", "go": "ご",
    "sa": "さ", "su": "す", "se": "せ", "so": "そ",
    "za": "ざ", "zi": "じ", "zu": "ず", "ze": "ぜ", "zo": "ぞ",
    "ta": "た", "te": "て", "to": "と", "ti": "てぃ", "tu": "とぅ",
    "da": "だ", "de": "で", "do": "ど", "di": "でぃ", "du": "どぅ",
    "na": "な", "ni": "に", "nu": "ぬ", "ne": "ね", "no": "の",
    "ha": "は", "hi": "ひ", "fu": "ふ", "he": "へ", "ho": "ほ", "hu": "ふ",
    "ba": "ば", "bi": "び", "bu": "ぶ", "be": "べ", "bo": "ぼ",
    "pa": "ぱ", "pi": "ぴ", "pu": "ぷ", "pe": "ぺ", "po": "ぽ",
    "fa": "ふぁ", "fi": "ふぃ", "fe": "ふぇ", "fo": "ふぉ",
    "va": "ゔぁ", "vi": "ゔぃ", "vu": "ゔ", "ve": "ゔぇ", "vo": "ゔぉ",
    "ma": "ま", "mi": "み", "mu": "む", "me": "め", "mo": "も",
    "ya": "や", "yu": "ゆ", "yo": "よ",
    "ra": "ら", "ri": "り", "ru": "る", "re": "れ", "ro": "ろ",
    "la": "ら", "li": "り", "lu": "る", "le": "れ", "lo": "ろ",
    "wa": "わ", "wo": "を", "wi": "うぃ", "we": "うぇ",
    "a": "あ", "i": "い", "u": "う", "e": "え", "o": "お",
    "n": "ん",
}
_MAXLEN = 3
_VOWELS = set("aiueo")
# 促音になる子音(n は「ん」なので除く)
_SOKUON = set("kstpgdbjzcfhmryw")


def romaji_to_hiragana(s: str):
    """変換できれば ひらがな文字列、1文字でも解釈できなければ None。"""
    if not s:
        return None
    t = unicodedata.normalize("NFKC", s).lower().translate(_MACRON)
    # 記号は読みに影響しないので落とす(「Kaguya-sama wa Kokurasetai: Tensai-tachi...」のような
    # コロン・感嘆符つきタイトルが軒並み変換不能になっていたため)
    t = re.sub(r"[\s'’\-‐−・:;,.!?~=+&/()\[\]{}\"“”『』「」*×]+", " ", t)
    # 助詞の は / へ はヘボン式では wa / e と綴るので、単独語のときだけ読みではなく表記に寄せる
    t = " ".join({"wa": "ha", "e": "he"}.get(w, w) for w in t.split())
    out, i, n = [], 0, len(t)
    while i < n:
        c = t[i]
        if c == " ":
            i += 1
            continue
        # 促音: 同じ子音の連続(ただし n は「ん」扱い)
        if c in _SOKUON and i + 1 < n and t[i + 1] == c:
            out.append("っ")
            i += 1
            continue
        # 撥音: n の次が母音でも y でもなければ「ん」
        if c == "n" and (i + 1 >= n or (t[i + 1] not in _VOWELS and t[i + 1] != "y")):
            out.append("ん")
            i += 1
            continue
        for ln in range(_MAXLEN, 0, -1):
            chunk = t[i:i + ln]
            if chunk in TABLE:
                out.append(TABLE[chunk])
                i += ln
                break
        else:
            return None  # 未知の文字(英単語・記号・数字など)は諦めて手動に回す
    return "".join(out) or None


def slug(s: str):
    """任意の文字列 → id 用スラッグ。英単語を壊さないよう綴りはいじらない。"""
    t = unicodedata.normalize("NFKC", s or "").lower().translate(_MACRON)
    t = re.sub(r"[^a-z0-9]+", "-", t)
    return re.sub(r"-+", "-", t).strip("-")


def person_slug(s: str):
    """日本人名のローマ字 → id 用スラッグ。長音の綴りゆれ(tetsurou/tetsuro)を既存idに寄せる。

    既存の staff.json が `araki-tetsuro` / `kaji-yuki` のように長音を落とした綴りなので、
    `ou`(次が e のときを除く: Inoue を Inoe にしないため)・`uu`・`oo` を縮める。
    **作品名・スタジオ名には使わないこと**(Tokyo Ghoul → tokyo-ghol、MADHOUSE → madhose と
    英単語が壊れる)。
    """
    t = unicodedata.normalize("NFKC", s or "").lower().translate(_MACRON)
    t = re.sub(r"ou(?!e)", "o", t)
    t = t.replace("uu", "u").replace("oo", "o")
    return slug(t)


if __name__ == "__main__":
    for s in ["Yuuki Kaji", "Tetsurou Araki", "Shingeki no Kyojin", "Marina Inoue",
              "Steins;Gate", "Kimetsu no Yaiba", "Yasuko Kobayashi", "Hakkenden"]:
        print(f"{s!r:28} -> {romaji_to_hiragana(s)!r:24} slug={slug(s)!r}")
