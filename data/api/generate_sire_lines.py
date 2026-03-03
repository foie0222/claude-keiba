"""KBDBのHORSEテーブルから種牡馬リストを取得し、確定ペディグリーデータで父系ラインを生成する。

BRDテーブルにFBRDNOが格納されていないため、curated SIRE_FATHER辞書で
父系チェーンを構築し、ROOT_ANCESTORSとの照合で系統を決定する。

Usage: python3 data/api/generate_sire_lines.py

出力: data/sire_lines.json
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kbdb_client import KBDBClient

OUTPUT_PATH = Path(__file__).resolve().parents[1] / "sire_lines.json"

MAX_CHAIN_DEPTH = 10

# ルート祖先テーブル: chain上で最初にヒットした馬名の系統を採用
# 辞書の順序が優先度を決める（先にヒットした方を採用）
ROOT_ANCESTORS = {
    # サンデーサイレンス系統
    "サンデーサイレンス": "サンデーサイレンス系",
    # Roberto系統
    "Roberto": "Roberto系",
    # Hail to Reason (上位)
    "Hail to Reason": "Hail to Reason系",
    # Northern Dancer 系統（子孫→祖先の順）
    "Storm Cat": "Storm Cat系",
    "Danzig": "Danzig系",
    "Nureyev": "Nureyev系",
    "Sadler's Wells": "Sadler's Wells系",
    "Danehill": "Danehill系",
    "Northern Dancer": "Northern Dancer系",
    # Mr. Prospector 系統
    "Kingmambo": "Kingmambo系",
    "Fappiano": "Fappiano系",
    "Mr. Prospector": "Mr. Prospector系",
    # Seattle Slew / A.P. Indy
    "A.P. Indy": "A.P. Indy系",
    "Seattle Slew": "Seattle Slew系",
    # その他
    "ナスルーラ": "ナスルーラ系",
    "Nasrullah": "ナスルーラ系",
    "トニービン": "トニービン系",
    "Hyperion": "Hyperion系",
    "Grey Sovereign": "Grey Sovereign系",
    # 古い欧州系統（終端ノード用）
    "Nearco": "Nearco系",
    "Pharos": "Pharos系",
    "Donatello": "Donatello系",
    "In Reality": "In Reality系",
}

# 種牡馬名 → 父馬名の確定マッピング
# チェーンは SIRE_FATHER を辿って ROOT_ANCESTORS に到達するまで構築される
SIRE_FATHER: dict[str, str] = {
    # ======================================================================
    # サンデーサイレンス系
    # ======================================================================
    # サンデーサイレンス直仔
    "ディープインパクト": "サンデーサイレンス",
    "ステイゴールド": "サンデーサイレンス",
    "ハーツクライ": "サンデーサイレンス",
    "ダイワメジャー": "サンデーサイレンス",
    "ゼンノロブロイ": "サンデーサイレンス",
    "ゴールドアリュール": "サンデーサイレンス",
    "マンハッタンカフェ": "サンデーサイレンス",
    "ネオユニヴァース": "サンデーサイレンス",
    "アドマイヤマックス": "サンデーサイレンス",
    "ブラックタイド": "サンデーサイレンス",
    "Hat Trick": "サンデーサイレンス",
    "ゴールドヘイロー": "サンデーサイレンス",
    "フジキセキ": "サンデーサイレンス",
    "アグネスタキオン": "サンデーサイレンス",
    "マーベラスサンデー": "サンデーサイレンス",
    "ダンスインザダーク": "サンデーサイレンス",
    "サンデーサイレンス": "Halo",
    "Halo": "Hail to Reason",
    # Deep Impact sons (ディープインパクト産駒)
    "キズナ": "ディープインパクト",
    "コントレイル": "ディープインパクト",
    "ディープブリランテ": "ディープインパクト",
    "リアルインパクト": "ディープインパクト",
    "サトノダイヤモンド": "ディープインパクト",
    "ミッキーアイル": "ディープインパクト",
    "エイシンヒカリ": "ディープインパクト",
    "フィエールマン": "ディープインパクト",
    "ディーマジェスティ": "ディープインパクト",
    "サトノアラジン": "ディープインパクト",
    "リアルスティール": "ディープインパクト",
    "サトノインプレッサ": "ディープインパクト",
    "アルアイン": "ディープインパクト",
    "ダノンプレミアム": "ディープインパクト",
    "ワールドエース": "ディープインパクト",
    "ワールドプレミア": "ディープインパクト",
    "ミュゼスルタン": "ディープインパクト",
    "レーヴミストラル": "ディープインパクト",
    "ヴァンキッシュラン": "ディープインパクト",
    "グレーターロンドン": "ディープインパクト",
    "ヴァンセンヌ": "ディープインパクト",
    "サングレーザー": "ディープインパクト",
    "トーセンラー": "ディープインパクト",
    "スピルバーグ": "ディープインパクト",
    "シルバーステート": "ディープインパクト",
    "ロードバリオス": "ディープインパクト",
    "アドミラブル": "ディープインパクト",
    "ディープエクシード": "ディープインパクト",
    "ヴィットリオドーロ": "ディープインパクト",
    "キタノコマンドール": "ディープインパクト",
    "ダノンシャーク": "ディープインパクト",
    "サトノアレス": "ディープインパクト",
    "ダノンバラード": "ディープインパクト",
    "トーセンファントム": "ディープインパクト",
    "ロジャーバローズ": "ディープインパクト",
    "Saxon Warrior": "ディープインパクト",
    "Study of Man": "ディープインパクト",
    "Deep Impact": "サンデーサイレンス",
    # Stay Gold sons (ステイゴールド産駒)
    "オルフェーヴル": "ステイゴールド",
    "ゴールドシップ": "ステイゴールド",
    "ドリームジャーニー": "ステイゴールド",
    "ナカヤマフェスタ": "ステイゴールド",
    "フェノーメノ": "ステイゴールド",
    "レインボーライン": "ステイゴールド",
    "オーシャンブルー": "ステイゴールド",
    "インディチャンプ": "ステイゴールド",
    "ウインブライト": "ステイゴールド",
    "エタリオウ": "ステイゴールド",
    # Heart's Cry sons (ハーツクライ産駒)
    "ジャスタウェイ": "ハーツクライ",
    "シュヴァルグラン": "ハーツクライ",
    "ワンアンドオンリー": "ハーツクライ",
    "スワーヴリチャード": "ハーツクライ",
    "ウインバリアシオン": "ハーツクライ",
    "ラブリーデイ": "ハーツクライ",
    "ヤマカツエース": "ハーツクライ",
    "Yoshida": "ハーツクライ",
    # Daiwa Major sons (ダイワメジャー産駒)
    "アドマイヤマーズ": "ダイワメジャー",
    "カレンブラックヒル": "ダイワメジャー",
    "コパノリチャード": "ダイワメジャー",
    "アレスバローズ": "ダイワメジャー",
    "グランプリボス": "ダイワメジャー",
    "レッドファルクス": "ダイワメジャー",
    "ダノンスマッシュ": "ダイワメジャー",
    # Zenno Rob Roy sons (ゼンノロブロイ産駒)
    "トーセンジョーダン": "ゼンノロブロイ",
    "サンライズソア": "ゼンノロブロイ",
    # Gold Allure sons (ゴールドアリュール産駒)
    "エスポワールシチー": "ゴールドアリュール",
    "スマートファルコン": "ゴールドアリュール",
    "ゴールドドリーム": "ゴールドアリュール",
    "クリソベリル": "ゴールドアリュール",
    "コパノリッキー": "ゴールドアリュール",
    "ナムラタイタン": "ゴールドアリュール",
    "エピカリス": "ゴールドアリュール",
    # Manhattan Cafe sons (マンハッタンカフェ産駒)
    "ジョーカプチーノ": "マンハッタンカフェ",
    "レッドスパーダ": "マンハッタンカフェ",
    # Neo Universe sons (ネオユニヴァース産駒)
    "アンライバルド": "ネオユニヴァース",
    "ロジユニヴァース": "ネオユニヴァース",
    # Black Tide sons
    "キタサンブラック": "ブラックタイド",
    # Agnes Tachyon sons (フジキセキ/アグネスタキオン産駒)
    "ディープスカイ": "アグネスタキオン",
    "キャプテントゥーレ": "アグネスタキオン",
    # Fuji Kiseki sons (フジキセキ産駒)
    "イスラボニータ": "フジキセキ",
    "カネヒキリ": "フジキセキ",
    "キンシャサノキセキ": "フジキセキ",
    "ダノンシャンティ": "フジキセキ",
    # Dance in the Dark sons
    "ザサンデーフサイチ": "ダンスインザダーク",
    # Marvellous Sunday sons
    "サムライハート": "マーベラスサンデー",
    # Matsurida Gogh
    "マツリダゴッホ": "サンデーサイレンス",
    # Orfevre sons
    "エポカドーロ": "オルフェーヴル",
    # Admire Max sons
    "アドマイヤコジーン": "Cozzene",
    "Cozzene": "Caro",
    "Caro": "Donatello",
    # ======================================================================
    # キングカメハメハ系 (Kingmambo → Mr. Prospector)
    # ======================================================================
    "キングカメハメハ": "Kingmambo",
    "ロードカナロア": "キングカメハメハ",
    "ルーラーシップ": "キングカメハメハ",
    "レイデオロ": "キングカメハメハ",
    "ドゥラメンテ": "キングカメハメハ",
    "ローズキングダム": "キングカメハメハ",
    "Lord Kanaloa": "キングカメハメハ",
    "Rey de Oro": "キングカメハメハ",
    "ホッコータルマエ": "キングカメハメハ",
    "ラニ": "Tapit",
    "リオンディーズ": "キングカメハメハ",
    "キセキ": "ルーラーシップ",
    # Kingmambo → Mr. Prospector
    "Kingmambo": "Mr. Prospector",
    "Lemon Drop Kid": "Kingmambo",
    # King's Best → Danehill
    "キングズベスト": "Danehill",
    "エイシンフラッシュ": "キングズベスト",
    # ======================================================================
    # シンボリクリスエス系 (Roberto系)
    # ======================================================================
    "シンボリクリスエス": "Kris S.",
    "Kris S.": "Roberto",
    "エピファネイア": "シンボリクリスエス",
    "サクラプレジデント": "シンボリクリスエス",
    "ストロングリターン": "シンボリクリスエス",
    # Roberto sons/grandsons
    "タニノギムレット": "ブライアンズタイム",
    "ブライアンズタイム": "Roberto",
    "ナリタブライアン": "ブライアンズタイム",
    "マヤノトップガン": "ブライアンズタイム",
    # ======================================================================
    # スクリーンヒーロー系 (Roberto → Hail to Reason)
    # ======================================================================
    "スクリーンヒーロー": "グラスワンダー",
    "モーリス": "スクリーンヒーロー",
    "ゴールドアクター": "スクリーンヒーロー",
    "Maurice": "スクリーンヒーロー",
    # Grass Wonder → Silver Hawk → Roberto
    "グラスワンダー": "Silver Hawk",
    "Silver Hawk": "Roberto",
    # ======================================================================
    # Northern Dancer 系統
    # ======================================================================
    # Storm Cat line
    "Storm Cat": "Storm Bird",
    "Storm Bird": "Northern Dancer",
    "Stormy Atlantic": "Storm Cat",
    "ヨハネスブルグ": "Storm Cat",
    "ヘニーヒューズ": "Hennessy",
    "Hennessy": "Storm Cat",
    "ヘニーハウンド": "ヘニーヒューズ",
    # Giant's Causeway line (Storm Cat → Northern Dancer)
    "Giant's Causeway": "Storm Cat",
    "Shamardal": "Giant's Causeway",
    "Not This Time": "Giant's Causeway",
    "エスケンデレヤ": "Giant's Causeway",
    "Blue Point": "Shamardal",
    "Earthlight": "Shamardal",
    "Lope de Vega": "Shamardal",
    "Pinatubo": "Shamardal",
    "Victor Ludorum": "Shamardal",
    "Lucky Vega": "Lope de Vega",
    # Scat Daddy line (Storm Cat)
    "Scat Daddy": "Johannesburg",
    "Johannesburg": "Hennessy",
    "Caravaggio": "Scat Daddy",
    "Justify": "Scat Daddy",
    "Mendelssohn": "Scat Daddy",
    "No Nay Never": "Scat Daddy",
    "Sioux Nation": "Scat Daddy",
    "Will Take Charge": "Scat Daddy",
    # Harlan's Holiday line (Storm Cat)
    "Harlan's Holiday": "Storm Cat",
    "Into Mischief": "Harlan's Holiday",
    "Audible": "Into Mischief",
    "Authentic": "Into Mischief",
    "Goldencents": "Into Mischief",
    "Practical Joke": "Into Mischief",
    "シャンハイボビー": "Harlan's Holiday",
    # Danzig line
    "Hard Spun": "Danzig",
    "War Front": "Danzig",
    "Air Force Blue": "War Front",
    "Declaration of War": "War Front",
    "Omaha Beach": "War Front",
    "U S Navy Flag": "War Front",
    "War of Will": "War Front",
    "アメリカンペイトリオット": "War Front",
    "Silver State": "Hard Spun",
    # Danehill line (Danzig → Northern Dancer)
    "Danehill": "Danzig",
    "Dansili": "Danehill",
    "Bated Breath": "Dansili",
    "Fastnet Rock": "Danehill",
    "Leinster": "Danehill",
    "Danehill Dancer": "Danehill",
    "Mastercraftsman": "Danehill Dancer",
    # Redoute's Choice / Snitzel line (Danehill)
    "Redoute's Choice": "Danehill",
    "Snitzel": "Redoute's Choice",
    "Not A Single Doubt": "Redoute's Choice",
    "Trapeze Artist": "Snitzel",
    "Farnan": "Not A Single Doubt",
    "The Autumn Sun": "Redoute's Choice",
    # Sadler's Wells / Galileo line
    "Sadler's Wells": "Northern Dancer",
    "Galileo": "Sadler's Wells",
    "Frankel": "Galileo",
    "Australia": "Galileo",
    "Camelot": "Montjeu",
    "Montjeu": "Sadler's Wells",
    "Churchill": "Galileo",
    "Gleneagles": "Galileo",
    "Highland Reel": "Galileo",
    "Intello": "Galileo",
    "Nathaniel": "Galileo",
    "New Approach": "Galileo",
    "Teofilo": "Galileo",
    "Ulysses": "Galileo",
    "ケープブランコ": "Galileo",
    "Dawn Approach": "New Approach",
    "Masar": "New Approach",
    "Havana Gold": "Teofilo",
    "Havana Grey": "Havana Gold",
    "Massaat": "Teofilo",
    "Cracksman": "Frankel",
    "Magna Grecia": "Invincible Spirit",
    "タニノフランケル": "Frankel",
    # Dubawi line (Sadler's Wells系 via Dubai Millennium)
    "Dubai Millennium": "Seeking the Gold",
    "Seeking the Gold": "Mr. Prospector",
    "Dubawi": "Dubai Millennium",
    "Ghaiyyath": "Dubawi",
    "New Bay": "Dubawi",
    "Night of Thunder": "Dubawi",
    "Postponed": "Dubawi",
    "Too Darn Hot": "Dubawi",
    "Zarak": "Dubawi",
    "ホークビル": "Kitten's Joy",
    # Invincible Spirit / Green Desert line
    "Green Desert": "Danzig",
    "Invincible Spirit": "Green Desert",
    "Kingman": "Invincible Spirit",
    "Shalaa": "Invincible Spirit",
    "I Am Invincible": "Invincible Spirit",
    "Palace Pier": "Kingman",
    # Sea The Stars / Cape Cross line
    "Cape Cross": "Green Desert",
    "Sea The Stars": "Cape Cross",
    "Golden Horn": "Cape Cross",
    "Sea The Moon": "Sea The Stars",
    # High Chaparral / Toronado line (Sadler's Wells)
    "High Chaparral": "Sadler's Wells",
    "Dundeel": "High Chaparral",
    "Toronado": "High Chaparral",
    # Nureyev line
    "Nureyev": "Northern Dancer",
    "Pivotal": "Polar Falcon",
    "Polar Falcon": "Nureyev",
    "Siyouni": "Pivotal",
    "Farhh": "Pivotal",
    "Sottsass": "Siyouni",
    "St Mark's Basilica": "Siyouni",
    # Northern Meteor / Zoustar / Deep Field
    "Northern Meteor": "Encosta de Lago",
    "Encosta de Lago": "Fairy King",
    "Fairy King": "Northern Dancer",
    "Zoustar": "Northern Meteor",
    "Deep Field": "Northern Meteor",
    # Other Northern Dancer descendants
    "ローエングリン": "Singspiel",
    "Singspiel": "In The Wings",
    "In The Wings": "Sadler's Wells",
    "Adlerflug": "In The Wings",
    # Written Tycoon / Capitalist (Australian line)
    "Written Tycoon": "Iglesia",
    "Iglesia": "Last Tycoon",
    "Last Tycoon": "Try My Best",
    "Try My Best": "Northern Dancer",
    "Capitalist": "Written Tycoon",
    # Exceed And Excel line
    "Exceed And Excel": "Danehill",
    "Exceedance": "Exceed And Excel",
    # Oasis Dream / Showcasing
    "Oasis Dream": "Green Desert",
    "Showcasing": "Oasis Dream",
    "Soldier's Call": "Showcasing",
    # Lonhro / Octagonal
    "Octagonal": "Zabeel",
    "Zabeel": "Sir Tristram",
    "Sir Tristram": "Sir Ivor",
    "Sir Ivor": "Sir Gaylord",
    "Sir Gaylord": "Turn-to",
    "Turn-to": "Royal Charger",
    "Lonhro": "Octagonal",
    "Ocean Park": "Thorn Park",
    "Thorn Park": "Crown Jester",
    # ======================================================================
    # Mr. Prospector 系統
    # ======================================================================
    # Forty Niner → Mr. Prospector
    "Forty Niner": "Mr. Prospector",
    "Distorted Humor": "Forty Niner",
    "Khozan": "Distorted Humor",
    "Maclean's Music": "Distorted Humor",
    "Cloud Computing": "Maclean's Music",
    "Complexity": "Maclean's Music",
    "Flower Alley": "Distorted Humor",
    "アイルハヴアナザー": "Flower Alley",
    # Gone West → Mr. Prospector
    "Gone West": "Mr. Prospector",
    "Speightstown": "Gone West",
    "Central Banker": "Speightstown",
    "Charlatan": "Speightstown",
    "Munnings": "Speightstown",
    "ケイムホーム": "Gone West",
    # Fappiano → Mr. Prospector
    "Fappiano": "Mr. Prospector",
    "Unbridled": "Fappiano",
    "Unbridled's Song": "Unbridled",
    "Arrogate": "Unbridled's Song",
    "Liam's Map": "Unbridled's Song",
    "エンパイアメーカー": "Unbridled",
    "アポロケンタッキー": "エンパイアメーカー",
    "Pioneerof the Nile": "エンパイアメーカー",
    "American Pharoah": "Pioneerof the Nile",
    "Cairo Prince": "Pioneerof the Nile",
    "Classic Empire": "Pioneerof the Nile",
    "Thousand Words": "Pioneerof the Nile",
    # Curlin line (Smart Strike → Mr. Prospector)
    "Smart Strike": "Mr. Prospector",
    "Curlin": "Smart Strike",
    "English Channel": "Smart Strike",
    "Tom's d'Etat": "Smart Strike",
    "Connect": "Curlin",
    "Global Campaign": "Curlin",
    "Good Magic": "Curlin",
    "Known Agenda": "Curlin",
    "Palace Malice": "Curlin",
    "Vino Rosso": "Curlin",
    # Elusive Quality → Gone West → Mr. Prospector
    "Elusive Quality": "Gone West",
    "Quality Road": "Elusive Quality",
    "Raven's Pass": "Elusive Quality",
    "City of Light": "Quality Road",
    "Klimt": "Quality Road",
    # El Prado line (Sadler's Wells, but Medaglia d'Oro often classified under Mr. Prospector in Japan)
    "El Prado": "Sadler's Wells",
    "Medaglia d'Oro": "El Prado",
    "Kitten's Joy": "El Prado",
    "Bolt d'Oro": "Medaglia d'Oro",
    "Bobby's Kitten": "Kitten's Joy",
    "Kameko": "Kitten's Joy",
    "Oscar Performance": "Kitten's Joy",
    # Malibu Moon → A.P. Indy → Seattle Slew
    "Malibu Moon": "A.P. Indy",
    # Candy Ride line
    "Candy Ride": "Ride the Rails",
    "Ride the Rails": "Cryptoclearance",
    "Cryptoclearance": "Fappiano",
    "Game Winner": "Candy Ride",
    "Gun Runner": "Candy Ride",
    "Mastery": "Candy Ride",
    "Twirling Candy": "Candy Ride",
    "Unified": "Candy Ride",
    "Vekoma": "Candy Ride",
    # Uncle Mo line (Indian Charlie → In Excess)
    "Indian Charlie": "In Excess",
    "In Excess": "Siberian Express",
    "Uncle Mo": "Indian Charlie",
    "Adios Charlie": "Indian Charlie",
    "Mo Town": "Uncle Mo",
    "Modernist": "Uncle Mo",
    "Nyquist": "Uncle Mo",
    "Yaupon": "Uncle Mo",
    # Tapit → Pulpit → A.P. Indy → Seattle Slew
    "A.P. Indy": "Seattle Slew",
    "Pulpit": "A.P. Indy",
    "Tapit": "Pulpit",
    "Bernardini": "A.P. Indy",
    "Take Charge Indy": "A.P. Indy",
    "Constitution": "Tapit",
    "Essential Quality": "Tapit",
    "Frosted": "Tapit",
    "Mohaymen": "Tapit",
    "Race Day": "Tapit",
    "Tiz the Law": "Constitution",
    # Mineshaft → A.P. Indy
    "Mineshaft": "A.P. Indy",
    "Dialed In": "Mineshaft",
    "カジノドライヴ": "Mineshaft",
    # Street Sense / Street Cry line
    "Street Cry": "Machiavellian",
    "Machiavellian": "Mr. Prospector",
    "Street Sense": "Street Cry",
    "Street Boss": "Street Cry",
    "Maxfield": "Street Sense",
    "McKinzie": "Street Sense",
    # Carson City → Mr. Prospector
    "Carson City": "Mr. Prospector",
    "City Zip": "Carson City",
    "Collected": "City Zip",
    "Improbable": "City Zip",
    # Flatter → A.P. Indy
    "Flatter": "A.P. Indy",
    "Upstart": "Flatter",
    # Dixie Union → Dixieland Band
    "Dixie Union": "Dixieland Band",
    "Dixieland Band": "Northern Dancer",
    "Union Rags": "Dixie Union",
    "Catalina Cruiser": "Union Rags",
    "Free Drop Billy": "Union Rags",
    # Paynter → Awesome Again
    "Awesome Again": "Deputy Minister",
    "Deputy Minister": "Vice Regent",
    "Vice Regent": "Northern Dancer",
    "Ghostzapper": "Awesome Again",
    "Daaher": "Awesome Again",
    "Paynter": "Awesome Again",
    "Knicks Go": "Paynter",
    # Honor Code line
    "Honor Code": "A.P. Indy",
    "Honor A. P.": "Honor Code",
    # Super Saver / Runhappy
    "Super Saver": "Maria's Mon",
    "Maria's Mon": "Wavering Monarch",
    "Runhappy": "Super Saver",
    # Violence / Volatile
    "Violence": "Medaglia d'Oro",
    "Volatile": "Violence",
    # First Samurai / Lea
    "First Samurai": "Giant's Causeway",
    "Lea": "First Samurai",
    # Southern Halo → Halo
    "Southern Halo": "Halo",
    "More Than Ready": "Southern Halo",
    "Catholic Boy": "More Than Ready",
    "Daredevil": "More Than Ready",
    # Makfi / Make Believe
    "Makfi": "Dubawi",
    "マクフィ": "Dubawi",
    "Make Believe": "Makfi",
    # Acclamation / Dark Angel / Harry Angel
    "Acclamation": "Royal Applause",
    "Royal Applause": "Waajib",
    "Dark Angel": "Acclamation",
    "Harry Angel": "Dark Angel",
    # ======================================================================
    # A.P. Indy / Seattle Slew 系統
    # ======================================================================
    "Seattle Slew": "Bold Reasoning",
    # ======================================================================
    # トニービン系 (Grey Sovereign → Nasrullah)
    # ======================================================================
    "トニービン": "Kampala",
    "Kampala": "Kalamoun",
    "ジャングルポケット": "トニービン",
    "オウケンブルースリ": "ジャングルポケット",
    # ======================================================================
    # ブライアンズタイム / Roberto 系
    # ======================================================================
    "Roberto": "Hail to Reason",
    # ======================================================================
    # サウスヴィグラス系 (エンドスウィープ → Forty Niner → Mr. Prospector)
    # ======================================================================
    "エンドスウィープ": "Forty Niner",
    "サウスヴィグラス": "エンドスウィープ",
    "アドマイヤムーン": "エンドスウィープ",
    "アグニシャイン": "サウスヴィグラス",
    "ラブリーデイ_END_SWEEP": "エンドスウィープ",  # ラブリーデイはハーツクライ
    # スウェプトオーヴァーボード → エンドスウィープ
    "スウェプトオーヴァーボード": "エンドスウィープ",
    # ======================================================================
    # クロフネ系 (French Deputy → Deputy Minister → Vice Regent → Northern Dancer)
    # ======================================================================
    "French Deputy": "Deputy Minister",
    "クロフネ": "French Deputy",
    # ======================================================================
    # ハービンジャー系 (Danehill)
    # ======================================================================
    "ハービンジャー": "Danehill",
    # ======================================================================
    # ワークフォース系 (King's Best → Danehill)
    # ======================================================================
    "ワークフォース": "King's Best",
    "King's Best": "Danehill",
    # ======================================================================
    # バゴ系 (Nashwan → Blushing Groom)
    # ======================================================================
    "バゴ": "Nashwan",
    "Nashwan": "Blushing Groom",
    "Blushing Groom": "Red God",
    "Red God": "ナスルーラ",
    # ======================================================================
    # Monsun / Protectionist line
    # ======================================================================
    "Monsun": "Konigsstuhl",
    "Protectionist": "Monsun",
    "Noverre": "Rahy",
    "Rahy": "Blushing Groom",
    "Le Havre": "Noverre",
    # Zafonic / Iffraaj / Wootton Bassett
    "Zafonic": "Gone West",
    "Iffraaj": "Zafonic",
    "Wootton Bassett": "Iffraaj",
    "Almanzor": "Wootton Bassett",
    # ======================================================================
    # Additional foreign sires
    # ======================================================================
    "Accelerate": "Lookin At Lucky",
    "Lookin At Lucky": "Smart Strike",
    "Cajun Breeze": "French Fifteen",
    "French Fifteen": "Colonel John",
    "Bayern": "Offlee Wild",
    "Offlee Wild": "Wild Again",
    "Beau Liam": "Lemon Drop Kid",
    "Blame": "Arch",
    "Arch": "Kris S.",
    "Preservationist": "Arch",
    "Dabirsim": "Hat Trick",
    "Dandy Man": "Mozart",
    "Mozart": "Danehill",
    "Dutch Art": "Medicean",
    "Medicean": "Machiavellian",
    "Fort Larned": "E Dubai",
    "E Dubai": "Mr. Prospector",
    "Army Mule": "Friesan Fire",
    "Friesan Fire": "A.P. Indy",
    "Disco Partner": "Disco Rico",
    "Disco Rico": "Disco Flag",
    "Dragon Pulse": "Kyllachy",
    "Kyllachy": "Pivotal",
    "Twilight Son": "Kyllachy",
    "Shackleford": "Forestry",
    "Forestry": "Storm Cat",
    "Lion Heart": "Tale of the Cat",
    "Tale of the Cat": "Storm Cat",
    "Kantharos": "Lion Heart",
    "Bernstein": "Storm Cat",
    "Karakontie": "Bernstein",
    "Sharp Azteca": "Midnight Lute",
    "Midnight Lute": "Real Quiet",
    "Mitole": "エスケンデレヤ",
    "Mor Spirit": "エスケンデレヤ",
    "Shancelot": "シャンハイボビー",
    "Maximum Security": "ニューイヤーズデイ",
    "Al Wukair": "Dream Ahead",
    "Dream Ahead": "Diktat",
    "Diktat": "Warning",
    # New Year's Day / ニューイヤーズデイ → Street Sense
    "ニューイヤーズデイ": "Street Sense",
    "New Year's Day": "Street Sense",
    "Optimizer": "English Channel",
    "St Patrick's Day": "ディープインパクト",
    "Sweynesse": "Lope de Vega",
    "Frankel産駒": "Galileo",  # just in case
    # ======================================================================
    # 日本の種牡馬（ア行～ワ行）
    # ======================================================================
    "アイファーソング": "ゴスホークケン",
    "アジアエクスプレス": "ヘニーヒューズ",
    "アスカクリチャン": "グランプリボス",
    "アスクピーターパン": "ディープインパクト",
    "アニマルキングダム": "Leroidesanimaux",
    "Leroidesanimaux": "Candy Stripes",
    "アポロキングダム": "ビッグアーサー",
    "アポロソニック": "ビッグアーサー",
    "アルデバラン２": "Aldebaran",
    "Aldebaran": "Mr. Prospector",
    "アルバート": "アドマイヤドン",
    "アドマイヤドン": "ティンバーカントリー",
    "ティンバーカントリー": "Woodman",
    "Woodman": "Mr. Prospector",
    "アロマカフェ": "エイシンサンディ",
    "エイシンサンディ": "サンデーサイレンス",
    "アーネストリー": "グラスワンダー",
    "インカンテーション": "シニスターミニスター",
    "ウォータービルド": "ケンタッキアン",
    "エーシントップ": "サウスヴィグラス",
    "エンパイアペガサス": "エンパイアメーカー",
    "オウケンワールド": "オウケンブルースリ",
    "オンファイア": "ダイワメジャー",
    "オーヴァルエース": "マツリダゴッホ",
    "カフェラピード": "マンハッタンカフェ",
    "カフジテイク": "リオンディーズ",
    "カリズマティック": "Summer Squall",
    "Summer Squall": "Storm Bird",
    "カリフォルニアクローム": "Lucky Pulpit",
    "Lucky Pulpit": "Pulpit",
    "カルストンライトオ": "サクラバクシンオー",
    "サクラバクシンオー": "サクラユタカオー",
    "サクラユタカオー": "テスコボーイ",
    "テスコボーイ": "Princely Gift",
    "Princely Gift": "ナスルーラ",
    "ガルボ": "マンハッタンカフェ",
    "キャプテンキング": "ロードカナロア",
    "キングヘイロー": "ダンシングブレーヴ",
    "ダンシングブレーヴ": "Lyphard",
    "Lyphard": "Northern Dancer",
    "キングリオ": "キングヘイロー",
    "ギンザグリングラス": "ステイゴールド",
    "クラウンレガーロ": "サウスヴィグラス",
    "クリエイター２": "Tapit",
    "クリーンエコロジー": "クロフネ",
    "クレスコグランド": "マンハッタンカフェ",
    "クワイトファイン": "マンハッタンカフェ",
    "グァンチャーレ": "ディープインパクト",
    "グランデッツァ": "ディープインパクト",
    "ケープブランコ": "Galileo",
    "コパノチャーリー": "ゴールドアリュール",
    "ゴスホークケン": "Bernstein",
    "ゴルトマイスター": "ゴールドアリュール",
    "ゴールスキー": "ゴールドアリュール",
    "ゴールデンバローズ": "ディープインパクト",
    "ゴールデンマンデラ": "マンハッタンカフェ",
    "サイモンラムセス": "サウスヴィグラス",
    "サクラオリオン": "サクラバクシンオー",
    "サトノクラウン": "Marju",
    "Marju": "Last Tycoon",
    "サトノジェネシス": "ディープインパクト",
    "サングラス": "ジャスタウェイ",
    "サンダースノー": "Helmet",
    "Helmet": "Exceed And Excel",
    "サートゥルナーリア": "ロードカナロア",
    "ザファクター": "War Front",
    "シゲルカガ": "ディープインパクト",
    "シスキン": "First Defence",
    "First Defence": "Unbridled's Song",
    "シニスターミニスター": "Old Trieste",
    "Old Trieste": "A.P. Indy",
    "シビルウォー": "マジェスティックウォリアー",
    "シュウジ": "キンシャサノキセキ",
    "ショウナンカンプ": "サクラバクシンオー",
    "ショウナンバッハ": "ステイゴールド",
    "シルポート": "シンボリクリスエス",
    "スクワートルスクワート": "Marquetry",
    "Marquetry": "Mr. Prospector",
    "スズカコーズウェイ": "フジキセキ",
    "スズカフェニックス": "サンデーサイレンス",
    "ストーミングホーム": "Machiavellian",
    "ストーミーシー": "Storm Cat",
    "スノードラゴン": "アドマイヤコジーン",
    "スピリッツミノル": "ディープインパクト",
    "スマートオーディン": "ダノンバラード",
    "セイウンコウセイ": "アドマイヤコジーン",
    "セイクリムズン": "エイシンサンディ",
    "セレスハント": "ダイワメジャー",
    "タイセイレジェンド": "キングカメハメハ",
    "タイムパラドックス": "ブライアンズタイム",
    "タツゴウゲキ": "キングカメハメハ",
    "タリスマニック": "Medaglia d'Oro",
    "タワーオブロンドン": "Raven's Pass",
    "タートルボウル": "Dyhim Diamond",
    "Dyhim Diamond": "Indian Ridge",
    "Indian Ridge": "Ahonoora",
    "ダイシンサンダー": "サンダーガルチ",
    "サンダーガルチ": "Gulch",
    "Gulch": "Mr. Prospector",
    "ダイシンバルカン": "サウスヴィグラス",
    "ダノンキングリー": "ディープインパクト",
    "ダノンレジェンド": "Macho Uno",
    "Macho Uno": "Holy Bull",
    "ダンカーク": "Unbridled's Song",
    "ダンスディレクター": "アルデバラン",
    "アルデバラン": "Mr. Prospector",
    "チェリークラウン": "タイキシャトル",
    "タイキシャトル": "Devil's Bag",
    "Devil's Bag": "Halo",
    "テーオーヘリオス": "サウスヴィグラス",
    "ディスクリートキャット": "Forestry",
    "トゥザグローリー": "キングカメハメハ",
    "トゥザワールド": "キングカメハメハ",
    "トウケイヘイロー": "ゴールドヘイロー",
    "トビーズコーナー": "Bustin Stones",
    "Bustin Stones": "City Zip",
    "トランセンド": "ワイルドラッシュ",
    "ワイルドラッシュ": "Wild Again",
    "Wild Again": "Icecapade",
    "トーセンブライト": "サンデーサイレンス",
    "トーセンホマレボシ": "ディープインパクト",
    "トーセンレーヴ": "ディープインパクト",
    "トーホウジャッカル": "スペシャルウィーク",
    "スペシャルウィーク": "サンデーサイレンス",
    "ドリームバレンチノ": "ロージズインメイ",
    "ドレフォン": "Gio Ponti",
    "Gio Ponti": "Tale of the Cat",
    "ナダル": "Blame",
    "ニシケンモノノフ": "アイルハヴアナザー",
    "ニホンピロアワーズ": "ブライアンズタイム",
    "ネロ": "ヘニーヒューズ",
    "ノボジャック": "ティンバーカントリー",
    "ノヴェリスト": "Monsun",
    "ノーブルミッション": "Galileo",
    "ハギノハイブリッド": "サクラバクシンオー",
    "ハクサンムーン": "アドマイヤムーン",
    "ハッピースプリント": "サウスヴィグラス",
    "バトルプラン": "クロフネ",
    "バンドワゴン": "ゼンノロブロイ",
    "バンブーエール": "マンハッタンカフェ",
    "バーディバーディ": "ジョーカプチーノ",
    "パイロ": "Pulpit",
    "パドトロワ": "アドマイヤコジーン",
    "ビッグアーサー": "サクラバクシンオー",
    "ビーチパトロール": "Lemon Drop Kid",
    "ファインニードル": "アドマイヤムーン",
    "フィレンツェファイア": "Poseidon's Warrior",
    "Poseidon's Warrior": "Speightstown",
    "フォーウィールドライブ": "ゴールドアリュール",
    "フサイチセブン": "クロフネ",
    "フリオーソ": "ブライアンズタイム",
    "ブリックスアンドモルタル": "Giant's Causeway",
    "ブルドッグボス": "ダイワメジャー",
    "プリサイスエンド": "エンドスウィープ",
    "ヘンリーバローズ": "ディープインパクト",
    "ベストウォーリア": "マジェスティックウォリアー",
    "ベルシャザール": "キングカメハメハ",
    "ベンバトル": "Dubawi",
    "ベーカバド": "Cape Cross",
    "ポアゾンブラック": "マイネルラヴ",
    "マイネルラヴ": "Seeking the Gold",
    "ポエティックフレア": "Dawn Approach",
    "マインドユアビスケッツ": "Posse",
    "Posse": "Silver Deputy",
    "Silver Deputy": "Deputy Minister",
    "マクマホン": "Ramonti",
    "Ramonti": "Martino Alonso",
    "マジェスティックウォリアー": "A.P. Indy",
    "マスクゾロ": "Roman Ruler",
    "Roman Ruler": "Fusaichi Pegasus",
    "Fusaichi Pegasus": "Mr. Prospector",
    "マテラスカイ": "Speightstown",
    "マルターズアポジー": "ゴスホークケン",
    "ミスターメロディ": "Scat Daddy",
    "ミスチヴィアスアレックス": "Into Mischief",
    "ミッキーグローリー": "ディープインパクト",
    "ミッキースワロー": "トーセンホマレボシ",
    "ミッキーロケット": "キングカメハメハ",
    "ミラアイトーン": "スズカフェニックス",
    "メイショウサムソン": "オペラハウス",
    "オペラハウス": "Sadler's Wells",
    "メイショウボーラー": "タイキシャトル",
    "メジロダイボサツ": "メジロマックイーン",
    "メジロマックイーン": "メジロティターン",
    "メジロティターン": "メジロアサマ",
    "モズアスコット": "Frankel",
    "モンテロッソ": "Dubawi",
    "モーニン": "ヘニーヒューズ",
    "ヤマニンセラフィム": "ステイゴールド",
    "ヤングマンパワー": "スニッツェル",
    "スニッツェル": "Redoute's Choice",
    "ユアーズトゥルーリ": "Storm Cat",
    "リオンリオン": "ルーラーシップ",
    "リヤンドファミユ": "ルーラーシップ",
    "リーチザクラウン": "スペシャルウィーク",
    "ルヴァンスレーヴ": "シンボリクリスエス",
    "レオアクティブ": "キングカメハメハ",
    "レガーロ": "ディープインパクト",
    "レッドベルジュール": "ディープインパクト",
    "ロゴタイプ": "ローエングリン",
    "ロンギングダンサー": "ディープインパクト",
    "ロンドンタウン": "カネヒキリ",
    "ロージズインメイ": "Devil His Due",
    "Devil His Due": "Devil's Bag",
    "ローレルゲレイロ": "キングヘイロー",
    "ワンダーアキュート": "カリズマティック",
    "ヴァンゴッホ": "Galileo",
    "ヴィクトワールピサ": "ネオユニヴァース",
    "Danon Ballade": "ディープインパクト",
    # ======================================================================
    # 未解決だった種牡馬の追加
    # ======================================================================
    "デクラレーションオブウォー": "War Front",
    "キタサンミカヅキ": "キタサンブラック",
    # ======================================================================
    # ルート祖先まで到達しなかった中間系統の補完
    # ======================================================================
    # Siberian Express系 → Northern Dancer系として解決
    "Siberian Express": "Caro",
    # In Excess → Siberian Express → Caro → ...
    # Caro → Donatello は遠すぎるので、独立系統として Grey Sovereign に接続
    # 実際: Caro(=Donatello系) は Donatello → Donatello II → Caro
    # Donatello系は独立系統として扱う
    # Icecapade系
    "Icecapade": "Nearctic",
    "Nearctic": "Nearco",
    "Nearco": "Pharos",
    # Waajib系 (Acclamation → Royal Applause → Waajib)
    "Waajib": "Try My Best",
    # Konigsstuhl系 (Monsun → Konigsstuhl)
    "Konigsstuhl": "Dschingis Khan",
    # Warning系 (Al Wukair → Dream Ahead → Diktat → Warning)
    "Warning": "Known Fact",
    "Known Fact": "In Reality",
    # Colonel John系 (Cajun Breeze → French Fifteen → Colonel John)
    "Colonel John": "Tiznow",
    "Tiznow": "Cee's Tizzy",
    # Disco Flag系
    "Disco Flag": "Pleasant Colony",
    # Royal Charger系 → already chained through Turn-to
    "Royal Charger": "Nearco",
    # Crown Jester系 (Ocean Park → Thorn Park → Crown Jester)
    "Crown Jester": "Scenic",
    # Wavering Monarch系 (Runhappy → Super Saver → Maria's Mon → Wavering Monarch)
    "Wavering Monarch": "Majestic Light",
    # Real Quiet系 (Sharp Azteca → Midnight Lute → Real Quiet)
    "Real Quiet": "Quiet American",
    "Quiet American": "Fappiano",
    # Candy Stripes系 (Animal Kingdom → Leroidesanimaux → Candy Stripes)
    "Candy Stripes": "Blushing Groom",
    # ケンタッキアン系
    "ケンタッキアン": "キングヘイロー",
    # Ahonoora系 (タートルボウル → Dyhim Diamond → Indian Ridge → Ahonoora)
    "Ahonoora": "Lorenzaccio",
    # Holy Bull系 (ダノンレジェンド → Macho Uno → Holy Bull)
    "Holy Bull": "Great Above",
    # メジロアサマ系 → パーソロン系として扱う
    "メジロアサマ": "パーソロン",
    "パーソロン": "Donatello",
    # マスクトヒーロー → パイロ → Pulpit
    # already covered
}


def fetch_all_sires(client: KBDBClient) -> dict[str, str]:
    """HORSEテーブルから全ユニーク種牡馬(FBRDNO, FHSNM)を取得。"""
    rows = client.query(
        "SELECT DISTINCT FBRDNO, FHSNM FROM HORSE WHERE FBRDNO <> '0000000000';"
    )
    sires = {}
    for r in rows:
        brdno = r["FBRDNO"].strip()
        name = r["FHSNM"].strip()
        if brdno and name:
            sires[brdno] = name
    return sires


def build_chain(sire_name: str) -> list[str]:
    """SIRE_FAT​​HER辞書を辿って [自身, 父, 祖父, ...] の名前リストを返す。

    ルート祖先を見つけた後、via表示のためにもう1世代先まで辿る。
    """
    chain = [sire_name]
    current = sire_name
    visited = {sire_name}
    found_root = False

    for _ in range(MAX_CHAIN_DEPTH):
        father = SIRE_FATHER.get(current)
        if not father or father in visited:
            break
        chain.append(father)
        if found_root:
            # ルート祖先の1世代先まで取得して終了
            break
        if father in ROOT_ANCESTORS:
            found_root = True
        visited.add(father)
        current = father

    return chain


def classify_line(chain: list[str]) -> tuple[str, str]:
    """チェーンからline(系統名)とvia(経路)を決定。

    Returns:
        (line, via) タプル
    """
    # chain内でROOT_ANCESTORSを探す
    root_idx = None
    for i, name in enumerate(chain):
        if name in ROOT_ANCESTORS:
            root_idx = i
            break

    if root_idx is not None:
        line = ROOT_ANCESTORS[chain[root_idx]]
        # via: chain[1]（父）からroot ancestorまで（含む）
        # rootが直接の父(idx=1)の場合、1世代先も含めてコンテキストを提供
        if root_idx == 0:
            # 自身がroot ancestor
            via_parts = []
        elif root_idx == 1 and len(chain) > 2:
            # 直接の父がroot → rootの父も表示
            via_parts = chain[1 : root_idx + 2]
        else:
            via_parts = chain[1 : root_idx + 1]
    else:
        # ルート祖先が見つからない場合、終端の馬名に「系」を付ける
        terminal = chain[-1] if chain else "不明"
        line = f"{terminal}系"
        via_parts = chain[1:]

    via = " → ".join(via_parts) if via_parts else ""
    return line, via


def main():
    client = KBDBClient()

    print("1. HORSEテーブルから全種牡馬を取得...")
    sires = fetch_all_sires(client)
    print(f"   {len(sires)}頭の種牡馬を取得")

    print("2. 各種牡馬の系統を判定...")
    result = {}
    unresolved = []
    for _brdno, name in sorted(sires.items(), key=lambda x: x[1]):
        chain = build_chain(name)
        line, via = classify_line(chain)
        result[name] = {"line": line, "via": via}
        # 自身がそのまま系統名になっている = SIRE_FAT​​HERに未登録
        if line == f"{name}系":
            unresolved.append(name)

    print(f"   {len(result)}頭を分類完了")

    if unresolved:
        print(f"\n   未解決（SIRE_FAT​​HERに未登録）: {len(unresolved)}頭")
        for name in unresolved:
            print(f"     - {name}")

    print(f"\n3. {OUTPUT_PATH} に出力...")
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print("完了!")

    # サマリー表示
    line_counts: dict[str, int] = {}
    for entry in result.values():
        line_counts[entry["line"]] = line_counts.get(entry["line"], 0) + 1
    print("\n系統別分布:")
    for line_name, count in sorted(line_counts.items(), key=lambda x: -x[1]):
        print(f"  {line_name}: {count}頭")


if __name__ == "__main__":
    main()
