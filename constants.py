# 季節代碼
SEASONS = ["atom01", "binary01", "cream01", "divine01", "ever01", "atom02"]
SEASONS_PREFIX = ["a", "b", "c", "d", "e", "aa"]

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

# 依長度排序，確保較長的在前避免例如 'aa' 被當成 'a' + 'a'
prefix_pattern = '|'.join(sorted(SEASONS_PREFIX, key=len, reverse=True))
# 卡號格式
CARD_NUMBER_REGEX = rf'^({prefix_pattern})\d{{3}}[az]?'