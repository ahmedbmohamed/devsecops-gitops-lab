from flask import Flask, jsonify
import os

app = Flask(__name__)


@app.route("/")
def index():
    return jsonify(
        message="Hello from my GitOps pipeline - v2",
        version=os.getenv("APP_VERSION", "dev"),
    )


@app.route("/healthz")
def healthz():
    return jsonify(status="ok"), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
