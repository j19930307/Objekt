# 季節代碼
SEASONS = ["atom01", "binary01", "cream01", "divine01", "ever01"]
SEASONS_PREFIX = [season[0] for season in SEASONS]

# 成員名稱
MEMBERS = [
    "YooYeon", "Mayu", "Xinyu", "NaKyoung", "SoHyun",
    "DaHyun", "Nien", "SeoYeon", "JiYeon", "Kotone",
    "ChaeYeon", "YuBin", "JiWoo", "Kaede", "ShiOn",
    "Lynn", "Sullin", "HyeRin", "ChaeWon", "HaYeon",
    "SooMin", "YeonJi", "JooBin", "SeoAh", "JinSoul",
    "HaSeul", "KimLip", "HeeJin", "Choerry"
]
MEMBERS_LOWER = [member.lower() for member in MEMBERS]

# 卡號格式
CARD_NUMBER_REGEX = rf"[{''.join(SEASONS_PREFIX)}]\d{{3}}[az]?"
