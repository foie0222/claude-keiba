"""投票内容のカード画像を生成する。"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# フォント設定
_FONT_PATH_REGULAR = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
_FONT_PATH_BOLD = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"

# カラー
_BG_COLOR = (30, 30, 35)
_TEXT_COLOR = (240, 240, 240)
_ACCENT_COLOR = (100, 180, 255)
_MUTED_COLOR = (160, 160, 170)
_PASS_COLOR = (180, 180, 60)

# レイアウト
_CARD_WIDTH = 600
_PADDING = 32

TYPE_LABEL = {"win": "単勝", "place": "複勝", "quinella": "馬連", "wide": "ワイド"}

VENUE_JP = {
    "sapporo": "札幌", "hakodate": "函館", "fukushima": "福島", "niigata": "新潟",
    "tokyo": "東京", "nakayama": "中山", "chukyo": "中京", "kyoto": "京都",
    "hanshin": "阪神", "kokura": "小倉",
}


def _load_font(bold: bool = False, size: int = 24) -> ImageFont.FreeTypeFont:
    path = _FONT_PATH_BOLD if bold else _FONT_PATH_REGULAR
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


def _horse_name_map(horses: list[dict]) -> dict[int, str]:
    """馬番 → 馬名のマッピングを構築。"""
    return {h["number"]: h["name"] for h in horses}


def _get_condition(race: dict) -> str:
    """馬場状態を取得。芝→turf_condition、ダート→dirt_condition。"""
    surface = race.get("surface", "")
    if "ダート" in surface:
        return race.get("dirt_condition", "")
    return race.get("turf_condition", "")


def generate_card_image(
    race_info: dict,
    bet_decision: dict,
    *,
    output_dir: Path | None = None,
) -> Path:
    """カード画像を生成してPNGファイルパスを返す。"""
    race = race_info.get("race", {})
    horses = race_info.get("horses", [])
    name_map = _horse_name_map(horses)

    venue_jp = VENUE_JP.get(race.get("venue", ""), race.get("venue", ""))
    race_no = race.get("race_number", 0)
    race_name = race.get("name", "")
    distance = race.get("distance", 0)
    surface = race.get("surface", "")
    condition = _get_condition(race)

    bets = bet_decision.get("bets", [])
    is_pass = bet_decision.get("pass_races", False) or not bets
    total_amount = bet_decision.get("total_amount", 0)

    # フォント
    font_title = _load_font(bold=True, size=28)
    font_sub = _load_font(bold=False, size=22)
    font_body = _load_font(bold=False, size=20)
    font_amount = _load_font(bold=True, size=20)
    font_total = _load_font(bold=True, size=24)

    # 行を構築: (text, font, color)
    lines = []

    # ヘッダー
    lines.append((f"{venue_jp}{race_no}R", font_title, _TEXT_COLOR))
    if race_name:
        lines.append((race_name, font_sub, _ACCENT_COLOR))
    detail = f"{surface}{distance}m"
    if condition:
        detail += f" {condition}"
    lines.append((detail, font_sub, _MUTED_COLOR))
    lines.append(("", font_body, _TEXT_COLOR))  # 空行

    if is_pass:
        lines.append(("見送り", font_title, _PASS_COLOR))
    else:
        for bet in bets:
            bet_type = TYPE_LABEL.get(bet["type"], bet["type"])
            horse_nums = bet["horses"]

            if len(horse_nums) == 1:
                h = horse_nums[0]
                name = name_map.get(h, "")
                label = f"{bet_type} {h}番 {name}"
            else:
                nums_str = "-".join(str(h) for h in horse_nums)
                label = f"{bet_type} {nums_str}"

            lines.append((label, font_body, _TEXT_COLOR))

            odds = bet.get("odds", 0)
            ev = bet.get("expected_value", 0)
            amount = bet.get("amount", 0)
            est_payout = int(amount * odds) if odds else 0
            detail_line = f"  {amount:,}円 @{odds} → {est_payout:,}円"
            lines.append((detail_line, font_amount, _MUTED_COLOR))

        lines.append(("", font_body, _TEXT_COLOR))  # 空行
        lines.append((f"計 {total_amount:,}円", font_total, _TEXT_COLOR))

    # 画像サイズ計算
    y = _PADDING
    line_positions = []
    for text, font, color in lines:
        line_positions.append((text, font, color, y))
        if text == "":
            y += 12
        else:
            bbox = font.getbbox(text)
            y += bbox[3] - bbox[1] + 10
    y += _PADDING

    img = Image.new("RGB", (_CARD_WIDTH, y), _BG_COLOR)
    draw = ImageDraw.Draw(img)

    for text, font, color, ly in line_positions:
        if text:
            draw.text((_PADDING, ly), text, font=font, fill=color)

    # 保存
    race_id = race.get("race_id", "unknown")
    output_dir = output_dir or Path("/tmp")
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{race_id}.png"
    img.save(path)

    return path
