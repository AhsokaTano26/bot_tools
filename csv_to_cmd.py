import csv
import re

CSV_FILE = "Goods - 角色名单 (生日表) 2026-05-27_11-53.csv"
BATCH_SIZE = 20  # 每条指令最多导入人数，防止消息过长


def parse_multi_field(field: str) -> list[str]:
    """解析可能包含多个值的字段，如 '远藤祐里香, 中岛由贵'"""
    if not field or not field.strip():
        return []
    # 去掉引号，按逗号分隔
    field = field.strip().strip('"')
    return [item.strip() for item in field.split(",") if item.strip()]


def main():
    characters = []  # (name, date)
    voice_actors = []  # (name, date)

    with open(CSV_FILE, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            char_name = row["角色名称"].strip()
            char_birthday = row["生日"].strip()

            # 角色
            if char_name and char_birthday:
                characters.append((char_name, char_birthday))

            # 中之人（可能多人）
            va_names = parse_multi_field(row["中之人"])
            va_birthdays = parse_multi_field(row["中之人生日"])

            for i, va_name in enumerate(va_names):
                if i < len(va_birthdays) and va_birthdays[i]:
                    voice_actors.append((va_name, va_birthdays[i]))

    # 去重（黑泽朋世同时配音奥泽美咲和米歇尔）
    voice_actors = list(dict(voice_actors).items())
    voice_actors = [(name, date) for name, date in voice_actors]

    def generate_commands(data: list[tuple[str, str]], label: str) -> list[str]:
        commands = []
        for i in range(0, len(data), BATCH_SIZE):
            batch = data[i:i + BATCH_SIZE]
            items = ", ".join(f"{name} {date}" for name, date in batch)
            commands.append(f"批量导入 {items}")
        return commands

    print(f"# === 角色 ({len(characters)} 人) ===")
    print("# 复制以下指令发送给 bot：\n")
    for cmd in generate_commands(characters, "角色"):
        print(cmd)
        print()

    print(f"\n# === 中之人 ({len(voice_actors)} 人) ===")
    print("# 复制以下指令发送给 bot：\n")
    for cmd in generate_commands(voice_actors, "中之人"):
        print(cmd)
        print()

    # 生成批量关联指令
    all_names = sorted(set(name for name, _ in characters) | set(name for name, _ in voice_actors))

    print(f"\n# === 批量关联 (共 {len(all_names)} 人) ===")
    print("# 批量导入后，复制以下指令绑定标签：\n")
    for i in range(0, len(all_names), BATCH_SIZE):
        batch = all_names[i:i + BATCH_SIZE]
        names_str = ", ".join(batch)
        print(f"批量关联 BanG_Dream! {names_str}")
        print()


if __name__ == "__main__":
    main()
