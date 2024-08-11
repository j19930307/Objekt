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
    regex = "^[a-d]\\d{3}[az]?$"
    if not re.match(regex, card_numbers):
        message = await ctx.respond("卡號輸入錯誤")
        await message.delete(delay=5)
    else:
        if len(card_numbers) == 4:  # 如果為 4 碼，加上電子版本碼 Z
            card_numbers += "z"
        season_prefix = card_numbers[0]
        season = next((season for season in seasons if season.startswith(season_prefix)), None)
        objekt = get_objekt_info(season, member.lower(), card_numbers[1:])
        await send_objekt_message(ctx, objekt)


async def send_objekt_message(ctx, objekt: Objekt):
    await ctx.defer()
    if objekt:
        collection = EmbedField(name="編號", value=objekt.collection)
        copies = EmbedField(name="發行數量", value=str(objekt.copies))
        description = EmbedField(name="說明", value=objekt.description)
        # Embed url 相同，會將兩張圖片合併顯示在第一個 Embed
        embed1 = Embed(url="https://www.google.com", image=objekt.front_image, fields=[collection, copies, description])
        embed2 = Embed(url="https://www.google.com", image=objekt.back_image)
        await ctx.followup.send(embeds=[embed1, embed2])
    else:
        message = await ctx.followup.send("查無資訊")
        await message.delete(delay=5)


bot.run(BOT_TOKEN)
