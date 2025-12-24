class StrType:
    @staticmethod
    def type(group_name: str, name: str, bir_type: int) -> str:
        try:
            dic = {
                1: f"{group_name}🎉@{name}生日快乐🎉",
                2: f"{group_name}(@{name}生日快乐!)",
                3: f"{group_name}(@{name}生日快乐🎂)"
            }
            return dic[bir_type]
        except:
            return group_name