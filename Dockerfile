# 使用官方 Python 映像
FROM python:3.11-slim

# 設定工作目錄
WORKDIR /app

# 複製檔案到容器內
COPY . .

# 安裝必要套件
RUN pip install --no-cache-dir -r requirements.txt

# 開放 port
EXPOSE 5000

# 啟動 Flask
CMD ["python", "jo.py"]