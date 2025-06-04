import json
import os
import re
import discord
import requests
from discord import Option, Embed, EmbedField, InputTextStyle
from dotenv import load_dotenv

from constants import MEMBERS, MEMBERS_LOWER, SEASONS, CARD_NUMBER_REGEX, SEASONS_PREFIX
from objekt import Objekt

load_dotenv()
BOT_TOKEN = os.environ["BOT_TOKEN"]

bot = discord.Bot()


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

    # 移除逗號並分割成單字
    cards_number = cards.lower().replace(',', ' ').strip().split()
    all_valid = all(re.fullmatch(CARD_NUMBER_REGEX, card) for card in cards_number)
    if not all_valid:
        await ctx.respond("卡號輸入錯誤")
    else:
        await ctx.defer()
        error_message = []
        for number in cards_number:
            season, collection = parse_card_number(card_number_trailing_z(number))
            try:
                objekt = get_objekt_info(season, member.lower(), collection)
                if objekt is None:
                    error_message.append(f"{member} {season[0]}{collection} 查無資訊")
                else:
                    await ctx.respond(embeds=create_embed(objekt))
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

    metadata_details = metadata.get("metadata", {})
    description = metadata_details.get("description", "")

    return Objekt(collection=by_slug["collectionNo"], front_image=by_slug["frontImage"],
                  back_image=by_slug["backImage"], copies=metadata["total"], description=description,
                  transferable=metadata["transferable"], percentage=metadata["percentage"])


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
    # 確認訊息中是否有 @bot
    if not bot.user.mentioned_in(message):
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
        for name, cards_number in member_cards.items():
            for number in cards_number:
                season, collection = parse_card_number(number)
                if season is None or collection is None:
                    error_message.append(f"{name} {number} 卡號輸入錯誤")
                else:
                    try:
                        objekt = get_objekt_info(season=season, member=name, collection=collection)
                        if objekt is None:
                            error_message.append(f"{name} {season[0]}{collection} 查無資訊")
                        else:
                            await message.reply(embeds=create_embed(objekt), mention_author=False)
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
        tuple[dict[str, list[str]], list[str]]:
            - member_cards: 字典，key 為成員名稱 (小寫)，value 為該成員的卡號列表。
            - error_message: 錯誤訊息列表，包含無法解析的行或錯誤的名稱資訊。
    """

    member_cards = {}  # 存儲解析出的成員名稱及其對應的卡號
    error_message = []  # 存儲錯誤訊息

    for line in content.lower().strip().split("\n"):  # 逐行處理輸入內容
        # 移除逗號並分割成單字
        clean_line = line.replace(',', ' ')
        parts = clean_line.strip().split()
        name = parts[0]
        cards = parts[1:]

        if name not in MEMBERS_LOWER:  # 驗證名稱是否在已知成員列表中
            error_message.append(f"{line} 名字輸入錯誤")
            continue

        cards_number = []
        for card in cards:
            # 驗證卡號是否符合格式
            if re.fullmatch(CARD_NUMBER_REGEX, card):
                cards_number.append(card_number_trailing_z(card))
            # 如果沒有找到卡號
            else:
                error_message.append(f"{line} 卡號輸入錯誤")

        member_cards.setdefault(name, []).extend(cards_number)  # 將卡號存入對應成員的列表中

    return member_cards, error_message  # 回傳解析結果與錯誤訊息


def parse_card_number(card_number):
    """解析卡號為季節名稱和 collection 編號"""
    match = re.fullmatch(CARD_NUMBER_REGEX, card_number)
    if not match:
        return None, None

    # 找出季節
    prefix = match.group(1)
    index = SEASONS_PREFIX.index(prefix)
    season = SEASONS[index]

    # 剩下的部分（如 '301', '301a'）
    collection = card_number[len(prefix):]

    return season, collection


def card_number_trailing_z(card_number):
    """如果卡號結尾不是 a 或 z，補上電子版本代碼 z"""
    if not card_number.endswith(('a', 'z')):
        return card_number + 'z'
    return card_number


def remove_mentions(message):
    """訊息內容移除 @bot 的部分"""
    content = message.content
    for mention in message.mentions:
        if mention == bot.user:
            content = content.replace(mention.mention, "").strip()  # 移除 @bot 並去除前後空白
    return content


bot.run(BOT_TOKEN)
