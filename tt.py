import pytz
from datetime import datetime

tz = pytz.timezone('Asia/Taipei')
now = datetime.now(tz)
print(now.strftime('%Y-%m-%d %H:%M:%S'))