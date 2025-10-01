import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Tuple
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from google import genai

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

app = Flask(__name__, static_folder=str(BASE_DIR), static_url_path="")

_client = None


def get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
    return _client


@app.route("/")
def root():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/health", methods=["GET"])
def health() -> Tuple[str, int]:
    return jsonify({"status": "ok"}), 200


@app.route("/api/chat", methods=["POST"])
def chat() -> Tuple[str, int]:
    payload = request.get_json(force=True)
    message = payload.get("message", "").strip()
    history = payload.get("history", [])

    if not message:
        return jsonify({"error": "Message is required."}), 400

    assistant_message = generate_reply(message, history)

    messages: List[Dict[str, Any]] = history + [
        {"role": "user", "content": message},
        {"role": "model", "content": assistant_message},
    ]

    return jsonify({"messages": messages, "cart": None}), 200


@app.route("/api/confirm", methods=["POST"])
def confirm() -> Tuple[str, int]:
    payload = request.get_json(force=True)
    cart = payload.get("cart")

    if not cart:
        return jsonify({"error": "Cart is required."}), 400

    order_number = str(uuid.uuid4()).split("-")[0].upper()
    payment_link = f"https://pay.example.com/{order_number}"

    return jsonify({"payment_link": payment_link, "order_number": order_number}), 200


@app.route("/api/payment/webhook", methods=["POST"])
def payment_webhook() -> Tuple[str, int]:
    payload = request.get_json(force=True, silent=True) or {}
    order_id = payload.get("order_id")
    payment_status = payload.get("status")

    app.logger.info(f"Payment webhook: {order_id} - {payment_status}")

    return jsonify({"received": True}), 200


@app.errorhandler(404)
def handle_404(_: Any) -> Tuple[str, int]:
    return send_from_directory(app.static_folder, "index.html"), 200


def generate_reply(message: str, history: List[Dict[str, str]]) -> str:
    client = get_client()
    if client is None:
        return "I'm offline right now, but I'm ready to take your order as soon as I'm back online."

    system_prompt = "You are a friendly quick-service restaurant assistant. Keep responses short and conversational. Acknowledge requests and ask concise follow-ups if needed."

    try:
        normalized_history = [
            {"role": "model" if turn.get("role") == "assistant" else "user", "parts": [{"text": turn.get("content", "")}]}
            for turn in history
        ]

        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=[*normalized_history, {"role": "user", "parts": [{"text": message}]}],
            config=genai.types.GenerateContentConfig(system_instruction=system_prompt),
        )
        reply = response.text.strip()
        if not reply:
            raise ValueError("Empty response")
        return reply
    except Exception:
        return "I'm having trouble right now. Please try again."


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
     
