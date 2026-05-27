import csv
from collections import defaultdict

CSV_FILE = "Goods - 角色名单 (生日表) 2026-05-27_11-53.csv"
SQL_FILE = "bir.sql"


def parse_multi_field(field: str) -> list[str]:
    if not field or not field.strip():
        return []
    field = field.strip().strip('"')
    return [item.strip() for item in field.split(",") if item.strip()]


def main():
    # 按日期分组: date -> set of names
    date_groups = defaultdict(set)

    with open(CSV_FILE, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            char_name = row["角色名称"].strip()
            char_birthday = row["生日"].strip()

            # 角色
            if char_name and char_birthday:
                date_groups[char_birthday].add(char_name)

            # 中之人
            va_names = parse_multi_field(row["中之人"])
            va_birthdays = parse_multi_field(row["中之人生日"])
            for i, va_name in enumerate(va_names):
                if i < len(va_birthdays) and va_birthdays[i]:
                    date_groups[va_birthdays[i]].add(va_name)

    # 按日期排序
    sorted_dates = sorted(date_groups.keys())

    # 生成 SQL
    lines = ["INSERT INTO main.member (date, name, extra) VALUES"]
    month_comments = {
        "01": "1月", "02": "2月", "03": "3月", "04": "4月",
        "05": "5月", "06": "6月", "07": "7月", "08": "8月",
        "09": "9月", "10": "10月", "11": "11月", "12": "12月"
    }

    current_month = None
    entries = []

    for date in sorted_dates:
        month = date[:2]
        if month != current_month:
            if current_month is not None:
                # 在月份注释前不加逗号，注释后继续
                pass
            current_month = month

        names = sorted(date_groups[date])
        name_str = "&".join(names)
        entries.append((month, date, name_str))

    # 按月分组输出
    current_month = None
    for i, (month, date, name_str) in enumerate(entries):
        if month != current_month:
            if current_month is not None:
                # 去掉上一行末尾的逗号，加分号或继续
                lines[-1] = lines[-1].rstrip(",") + ","
            lines.append(f"/* {month_comments[month]} */")
            current_month = month

        is_last = (i == len(entries) - 1)
        comma = "" if is_last else ","
        lines.append(f"('{date}', '{name_str}', ''){comma}")

    lines.append("")  # 末尾空行

    with open(SQL_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"✅ 已生成 {SQL_FILE}，共 {len(entries)} 条记录")


if __name__ == "__main__":
    main()
