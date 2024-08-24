import json
import os
import re
import discord
import requests
from discord import Option, Embed, EmbedField
from dotenv import load_dotenv
from objekt import Objekt

load_dotenv()
BOT_TOKEN = os.environ["BOT_TOKEN"]

bot = discord.Bot()


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name} ({bot.user.id})')
    print('Bot is ready to receive commands')


seasons = ["atom01", "binary01", "cream01", "divine01"]
members = [
    "YooYeon", "Mayu", "Xinyu", "NaKyoung", "SoHyun",
    "DaHyun", "Nien", "SeoYeon", "JiYeon", "Kotone",
    "ChaeYeon", "YuBin", "JiWoo", "Kaede", "ShiOn",
    "Lynn", "Sullin", "HyeRin", "ChaeWon", "HaYeon",
    "SooMin", "YeonJi", "JooBin", "SeoAh"
]
members_lower = [member.lower() for member in members]
card_numbers_regex = "[a-z]\\d{3}[az]?"


def get_objekt_info(season: str, member: str, collection: str):
    metadata_response = requests.get(f"https://apollo.cafe/api/objekts/metadata/{season}-{member}-{collection}")
    by_slug_response = requests.get(f"https://apollo.cafe/api/objekts/by-slug/{season}-{member}-{collection}")

    if metadata_response.status_code != 200 or by_slug_response.status_code != 200:
        return

    metadata = json.loads(metadata_response.text)
    by_slug = json.loads(by_slug_response.text)

    return Objekt(collection=by_slug["collectionNo"], front_image=by_slug["frontImage"],
                  back_image=by_slug["backImage"],
                  copies=metadata["copies"], description=metadata["metadata"]["description"])


@bot.slash_command(description="查詢 Objekt 資訊")
async def objekt(ctx: discord.ApplicationContext,
                 member: Option(str, description="請選擇成員", choices=members),
                 card_numbers: Option(str,
                                      description="請輸入卡號，季節1碼 + 編號3碼 + 電子或實體版1碼 (此碼可不填，預設帶入電子版)",
                                      required=True)):
    card_numbers = card_numbers.lower()
    if not re.match("^[a-d]\\d{3}[az]?$", card_numbers):
        message = await ctx.respond("卡號輸入錯誤")
        await message.delete(delay=5)
    else:
        season, collection = card_numbers_to_season_collection(card_numbers)
        await ctx.defer()
        objekt = get_objekt_info(season, member.lower(), collection)
        if objekt is None:
            message = await ctx.respond("查無資訊")
            await message.delete(delay=5)
        else:
            await ctx.followup.send(embeds=create_embed(objekt))


def create_embed(objekt: Objekt):
    collection = EmbedField(name="編號", value=objekt.collection)
    copies = EmbedField(name="發行數量", value=str(objekt.copies))
    description = EmbedField(name="說明", value=objekt.description)
    # Embed url 相同，會將兩張圖片合併顯示在第一個 Embed
    embed1 = Embed(url="https://www.google.com", image=objekt.front_image, fields=[collection, copies, description])
    embed2 = Embed(url="https://www.google.com", image=objekt.back_image)
    return [embed1, embed2]


@bot.listen('on_message')
async def on_message(message):
    await read_message(message)


# 多筆查詢
async def read_message(message):
    # 排除機器人本身的訊息，避免無限循環
    if message.author == bot.user:
        return
    # 確認訊息中是否有 @bot
    if not bot.user.mentioned_in(message):
        return

    channel = message.channel
    error_message = []

    loading_message = await channel.send(content="處理中，請稍後...")
    search_dict, error = await parse_message(content=message.content)
    error_message.extend(error)

    for name, codes in search_dict.items():
        for code in codes:
            season, collection = card_numbers_to_season_collection(code)
            if season is None or collection is None:
                error_message.append(f"{name} {code} 卡號輸入錯誤")
            else:
                objekt = get_objekt_info(season=season, member=name, collection=collection)
                if objekt is None:
                    error_message.append(f"{name}  {season[0]}{collection} 查無資訊")
                else:
                    await channel.send(embeds=create_embed(objekt))
    # 刪除使用者訊息
    await message.delete()
    # 刪除載入中訊息
    await loading_message.delete()
    if error_message:
        # 發送錯誤訊息
        await channel.send("\n".join(error_message))


# 將訊息轉換成 dict (key 為名字，value 為卡號陣列)
async def parse_message(content: str):
    name_card_numbers_dict = {}
    error_message = []

    for line in content.lower().strip().split("\n"):
        # 名字
        match = re.search(r"[a-z]+", line)
        if match:
            name = match.group()
            if name not in members_lower:
                error_message.append(f"{line} 名字輸入錯誤")
                break
            # 卡號
            codes = re.findall(card_numbers_regex, line)
            name_card_numbers_dict[name] = codes

    return name_card_numbers_dict, error_message


def card_numbers_to_season_collection(card_numbers):
    season_prefix = card_numbers[0]
    season = next((season for season in seasons if season.startswith(season_prefix)), None)
    collection = card_numbers[1:]
    if len(collection) == 3:  # 如果為 3 碼，加上電子版本碼 Z
        collection += "z"
    return season, collection


bot.run(BOT_TOKEN)