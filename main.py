import json
import os
import re
from dataclasses import dataclass

import discord
import requests
from discord import Option, Embed, EmbedField, InputTextStyle
from dotenv import load_dotenv

from constants import MEMBERS, MEMBERS_LOWER, SEASONS, CARD_NUMBER_REGEX, SEASONS_PREFIX
from objekt import Objekt

load_dotenv()
BOT_TOKEN = os.environ["BOT_TOKEN"]

bot = discord.Bot()


@dataclass(frozen=True)
class ParsedCardNumber:
    raw: str
    normalized: str
    season: str
    collection: str


@bot.event
async def on_ready():
    """機器人啟動時執行，顯示登入訊息"""
    print(f'Logged in as {bot.user.name} ({bot.user.id})')
    print('Bot is ready to receive commands')


async def autocomplete_members(ctx: discord.AutocompleteContext):
    """當用戶輸入選項時，提供自動補全建議。"""
    query = ctx.value.lower()  # 取得用戶目前輸入的字串
    return [member for member in MEMBERS if member.lower().startswith(query)]  # 篩選出以目前輸入開頭的選項


@bot.slash_command(description="查詢 Objekt 資訊")
async def objekt(ctx: discord.ApplicationContext,
                 member: Option(str, description="請選擇成員",
                                autocomplete=discord.utils.basic_autocomplete(autocomplete_members)),
                 cards: Option(str, description="請輸入卡號 (可查詢多筆)", required=True)):
    """處理單筆 Objekt 查詢"""

    parsed_cards = parse_card_numbers(cards)
    if not parsed_cards:
        await ctx.respond("卡號輸入錯誤")
    else:
        await ctx.defer()
        error_message = []
        for parsed_card in parsed_cards:
            try:
                objekt = get_objekt_info(parsed_card.season, member.lower(), parsed_card.collection)
                if objekt is None:
                    error_message.append(f"{member} {parsed_card.season[0]}{parsed_card.collection} 查無資訊")
                else:
                    await ctx.respond(embeds=create_embed(objekt))
                    if objekt.frontMedia:
                        await ctx.respond(objekt.frontMedia)
                if error_message:
                    await ctx.respond("\n".join(error_message))
            except Exception as e:
                await ctx.respond(str(e))


@bot.slash_command(description="查詢多筆 Objekt 資訊")
async def objekts(ctx: discord.ApplicationContext):
    """顯示查詢多筆 Objekt 資訊的對話框"""
    await ctx.send_modal(SearchModal())


@bot.listen('on_message')
async def on_message(message):
    """監聽訊息，若提及機器人則處理查詢"""
    await listen_message(message)


class SearchModal(discord.ui.Modal):
    """Discord UI Modal 用於輸入查詢多筆 Objekt 資訊"""

    def __init__(self):
        super().__init__(title="查詢多筆 Objekt 資訊")
        self.add_item(
            discord.ui.InputText(
                style=InputTextStyle.long,
                label="請輸入查詢內容",
                placeholder="輸入範例：\nJiwoo B208 c208 C315\nchaeyeon c315,b207,b208"
            )
        )

    async def callback(self, interaction: discord.Interaction):
        """處理使用者輸入後的回應"""
        await interaction.response.send_message(self.children[0].value)
        sent_message = await interaction.original_response()
        await send_objekt_info_to_discord(message=sent_message, input_text=self.children[0].value)


def get_objekt_info(season: str, member: str, collection: str):
    """從 API 獲取 Objekt 資訊"""
    metadata_response = requests.get(f"https://apollo.cafe/api/objekts/metadata/{season}-{member}-{collection}")
    by_slug_response = requests.get(f"https://apollo.cafe/api/objekts/by-slug/{season}-{member}-{collection}")

    if metadata_response.status_code != 200 or by_slug_response.status_code != 200:
        raise Exception(
            f"API 回應錯誤 (metadata: {metadata_response.status_code}) (by_slug: {by_slug_response.status_code})")

    metadata = json.loads(metadata_response.text)
    by_slug = json.loads(by_slug_response.text)

    data = metadata.get("data", {})
    description = data.get("description", "")

    return Objekt(collection=by_slug["collectionNo"], front_image=by_slug["frontImage"],
                  back_image=by_slug["backImage"], copies=metadata["total"], description=description,
                  transferable=metadata["transferable"], percentage=metadata["percentage"],
                  frontMedia=by_slug["frontMedia"])


def create_embed(objekt: Objekt):
    """建立 Discord Embed 以顯示 Objekt 資訊"""
    collection = EmbedField(name="編號", value=objekt.collection, inline=True)
    copies = EmbedField(name="發行量", value=str(objekt.copies), inline=True)
    # 排版用空白欄位
    space = EmbedField(name="\u200B", value="\u200B", inline=True)
    percentage = EmbedField(name="可傳率", value=f"{objekt.percentage}%", inline=True)
    transferable = EmbedField(name="可傳量", value=objekt.transferable, inline=True)
    description = EmbedField(name="說明", value=objekt.description)
    # 可傳率為 100% 時，則不顯示可傳資訊
    if objekt.copies == objekt.transferable:
        fields = [collection, copies, description]
    else:
        fields = [collection, copies, space, percentage, transferable, space, description]
    # Embed url 相同，會將兩張圖片合併顯示在第一個 Embed
    embed1 = Embed(url="https://www.google.com", image=objekt.front_image, fields=fields)
    embed2 = Embed(url="https://www.google.com", image=objekt.back_image)
    return [embed1, embed2]


async def listen_message(message):
    """處理使用者發送的訊息，並回應 Objekt 資訊"""
    # 排除 @everyone 或 @here
    if message.mention_everyone:
        return
    # 排除機器人本身的訊息，避免無限循環
    if message.author == bot.user:
        return
    # 確認訊息內容中是否主動 @bot
    if bot.user.mention not in message.content:
        return
    processing_message = await message.channel.send("處理中，請稍後...")
    await send_objekt_info_to_discord(message=message, input_text=remove_mentions(message))
    await processing_message.delete()


async def send_objekt_info_to_discord(message, input_text: str):
    """解析輸入內容並發送 Objekt 資訊至 Discord"""
    member_cards, error_message = await parse_message(content=input_text)
    if not member_cards:
        error_message.append("輸入內容無法解析")
    else:
        for name, parsed_cards in member_cards.items():
            for parsed_card in parsed_cards:
                try:
                    objekt = get_objekt_info(
                        season=parsed_card.season,
                        member=name,
                        collection=parsed_card.collection,
                    )
                    if objekt is None:
                        error_message.append(f"{name} {parsed_card.season[0]}{parsed_card.collection} 查無資訊")
                    else:
                        await message.reply(embeds=create_embed(objekt), mention_author=False)
                        if objekt.frontMedia:
                            await message.reply(objekt.frontMedia, mention_author=False)
                except Exception as e:
                    await message.reply(str(e))
    if error_message:  # 如果有錯誤訊息
        await message.reply(content="\n".join(error_message), mention_author=False)


async def parse_message(content: str):
    """
    解析訊息內容，提取成員名稱與對應的卡號。

    參數:
        content (str): 訊息內容，每行可能包含成員名稱與卡號。

    回傳:
        tuple[dict[str, list[ParsedCardNumber]], list[str]]:
            - member_cards: 字典，key 為成員名稱 (小寫)，value 為該成員的已解析卡號列表。
            - error_message: 錯誤訊息列表，包含無法解析的行或錯誤的名稱資訊。
    """

    member_cards = {}  # 存儲解析出的成員名稱及其對應的卡號
    error_message = []  # 存儲錯誤訊息

    for line in content.lower().strip().split("\n"):  # 逐行處理輸入內容
        # 移除逗號並分割成單字
        clean_line = line.replace(',', ' ')
        parts = clean_line.strip().split()

        names = []
        parsed_cards = []
        line_has_error = False

        for part in parts:
            if part in MEMBERS_LOWER:
                names.append(part)
            else:
                expanded_cards = parse_card_token(part)
                if expanded_cards is None:
                    error_message.append(f"{line} 名字或卡號輸入錯誤")
                    line_has_error = True
                    break
                parsed_cards.extend(expanded_cards)

        if line_has_error:
            continue

        for name in names:
            member_cards.setdefault(name, []).extend(parsed_cards)  # 將卡號存入對應成員的列表中

    return member_cards, error_message  # 回傳解析結果與錯誤訊息


def parse_card_number(card_number):
    """解析單一卡號並回傳標準化後的資訊。"""
    card_info = parse_card_reference(card_number)
    if card_info is None:
        return None

    normalized, prefix, _, suffix = card_info
    season = SEASONS[SEASONS_PREFIX.index(prefix)]
    collection = f"{normalized[len(prefix):-1]}{suffix}"

    return ParsedCardNumber(
        raw=card_number,
        normalized=normalized,
        season=season,
        collection=collection,
    )


def parse_card_token(card_token):
    """解析單一卡號或卡號區間。"""
    if "-" not in card_token:
        parsed_card = parse_card_number(card_token)
        if parsed_card is None:
            return None
        return [parsed_card]

    range_parts = card_token.split("-")
    if len(range_parts) != 2:
        return None

    start_info = parse_card_reference(range_parts[0])
    end_info = parse_card_reference(range_parts[1])
    if start_info is None or end_info is None:
        return None

    _, start_prefix, start_number, start_suffix = start_info
    _, end_prefix, end_number, end_suffix = end_info
    if start_prefix != end_prefix or start_suffix != end_suffix or start_number > end_number:
        return None

    return [
        parse_card_number(f"{start_prefix}{number:03d}{start_suffix}")
        for number in range(start_number, end_number + 1)
    ]


def parse_card_reference(card_number):
    """解析卡號基本資訊，供單卡與區間共用。"""
    normalized = normalize_card_number(card_number)
    if normalized is None:
        return None

    match = re.fullmatch(CARD_NUMBER_REGEX, normalized)
    if not match:
        return None

    prefix = match.group(1)
    suffix = normalized[-1]
    number = int(normalized[len(prefix):-1])
    return normalized, prefix, number, suffix


def parse_card_numbers(cards: str):
    """從輸入字串提取並解析多個卡號。"""
    parsed_cards = []
    for part in cards.lower().replace(',', ' ').strip().split():
        expanded_cards = parse_card_token(part)
        if expanded_cards is None:
            return None
        parsed_cards.extend(expanded_cards)
    return parsed_cards


def normalize_card_number(card_number):
    """標準化卡號格式；若格式錯誤則回傳 None。"""
    normalized = card_number.lower().strip()
    if not re.fullmatch(CARD_NUMBER_REGEX, normalized):
        return None
    if normalized.endswith(('a', 'z')):
        return normalized
    return f"{normalized}z"


def remove_mentions(message):
    """訊息內容移除 @bot 的部分"""
    content = message.content
    for mention in message.mentions:
        if mention == bot.user:
            content = content.replace(mention.mention, "").strip()  # 移除 @bot 並去除前後空白
    return content


bot.run(BOT_TOKEN)
