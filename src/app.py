from flask import Flask
from routes.upload import upload_blueprint

app = Flask(__name__)
app.register_blueprint(upload_blueprint)

@app.route("/", methods=["GET"])
def health():
    return "Slack Bot is alive", 200
