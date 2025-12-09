from datetime import datetime

now = datetime.now()
formatted_datetime = now.strftime("%m-%d")
print(f"{formatted_datetime}")
print(type(formatted_datetime))
