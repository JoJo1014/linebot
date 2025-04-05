from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return "你好，我是你的記帳機器人！"

if __name__ == "__main__":
    app.run(port=5000, debug=True)