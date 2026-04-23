import os
from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()
app=Flask(__name__)

CORS(app)

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "service": "Documind",
        "day": 1
    })

if __name__=="__main__":
    app.run(debug=True,port=5001,threaded=True)