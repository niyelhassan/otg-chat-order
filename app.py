import os
import uuid
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from google import genai
from urllib.parse import urlencode

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

app = Flask(__name__, static_folder=str(BASE_DIR), static_url_path="")

_client = None
_menu_data = None


def get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
    return _client


def load_menu():
    global _menu_data
    if _menu_data is None:
        menu_path = BASE_DIR / "menu.json"
        with open(menu_path, "r", encoding="utf-8") as f:
            _menu_data = json.load(f)
    return _menu_data


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
    cart = payload.get("cart", [])

    if not message:
        return jsonify({"error": "Message is required."}), 400

    assistant_message, updated_cart, show_payment, show_cart = generate_reply(message, history, cart)

    messages: List[Dict[str, Any]] = history + [
        {"role": "user", "content": message},
        {"role": "model", "content": assistant_message},
    ]

    # Add cart as a message if it should be shown
    if show_cart and updated_cart:
        cart_items = "\n".join([f"• {item['name']}" + 
                               (f" (with {', '.join(item['modifiers'])})" if item.get('modifiers') else "")
                               for item in updated_cart])
        cart_message = f"**Your Cart:**\n{cart_items}"
        messages.append({"role": "cart", "content": cart_message})

    # Add payment as a message if it should be shown
    if show_payment and updated_cart:
        order_number = str(uuid.uuid4()).split("-")[0].upper()
        payment_link = "https://example.com"
        
        messages.append({
            "role": "payment",
            "content": payment_link,
            "orderNumber": order_number
        })

    response_data = {
        "messages": messages,
        "cart": updated_cart,
    }
    
    print(f"=== Chat Request ===")
    print(f"User Message: {message}")
    print(f"Cart Items: {len(updated_cart)}")
    print(f"Show Cart: {show_cart}")
    print(f"Show Payment: {show_payment}")
    print(f"====================")

    return jsonify(response_data), 200


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


def generate_reply(message: str, history: List[Dict[str, str]], cart: List[Dict[str, Any]]) -> Tuple[str, List[Dict[str, Any]], bool, bool]:
    client = get_client()
    if client is None:
        return "I'm offline right now, but I'm ready to take your order as soon as I'm back online.", cart, False, False

    menu = load_menu()
    
    # Create simplified menu for AI - just names and IDs
    menu_items = []
    for item in menu:
        menu_items.append({
            "name": item["name"],
            "id": item["id"]
        })
    
    cart_summary = "\n".join([f"- {item['name']}" + 
                              (f" with {', '.join(item['modifiers'])}" if item.get('modifiers') else "")
                              for item in cart])
    
    system_prompt = f"""You are a restaurant order assistant for El Premio Tex Mex Bar and Grill.

MENU: {json.dumps(menu_items, indent=2)}

EXACT STEPS TO FOLLOW:
1. Greet and ask what they want to order
2. When customer names an item: Ask "Would you like any modifications to [item name]?"
3. After getting mods response: use [ADD_TO_CART: item_id, item_name, mod1, mod2]
4. Then ask "Would you like to add anything else before checking out?"
5. When customer says no/nope/that's it/nothing else:
   - MUST use [SHOW_CART] 
   - Then ask "Ready to confirm?"
6. When customer confirms (yes/confirmed/looks good):
   - Say "Great!" 
   - MUST use [CHECKOUT]

COMMANDS YOU MUST USE:
[ADD_TO_CART: item_id, item_name, mod1, mod2] - when adding items after mods
[SHOW_CART] - REQUIRED before asking to confirm
[CHECKOUT] - REQUIRED after customer confirms
[REQUEST_MODIFIERS: item_id] - only if customer asks about mods

CRITICAL RULES:
- You MUST use [SHOW_CART] when customer says they're done ordering
- You MUST use [CHECKOUT] when customer confirms the order
- Keep responses under 15 words
- Never skip [SHOW_CART] before confirmation"""

    # Build conversation with cart context
    conversation_parts = []
    for turn in history:
        role = "model" if turn.get("role") in ["assistant", "model"] else "user"
        conversation_parts.append({
            "role": role,
            "parts": [{"text": turn.get("content", "")}]
        })
    
    # Add current message with cart context
    user_message = f"{message}"
    if cart:
        user_message += f"\n\n[SYSTEM: Current cart: {cart_summary}]"
    
    conversation_parts.append({
        "role": "user",
        "parts": [{"text": user_message}]
    })
    
    # Print conversation history once at the start
    print(f"=== Conversation History ===")
    for i, part in enumerate(conversation_parts):
        role_display = "Assistant" if part["role"] == "model" else "User"
        content = part["parts"][0]["text"]
        print(f"  {i+1}. [{role_display}]: {content}")
    print(f"=============================")
    
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash-preview-09-2025",
            contents=conversation_parts,
            config=genai.types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.1
            ),
        )
        reply = response.text.strip()
        
        print(f"=== AI Processing ===")
        print(f"Raw Response: {reply}")
        
        # If AI requests modifiers, directly provide them without regeneration
        if "[REQUEST_MODIFIERS:" in reply:
            start = reply.find("[REQUEST_MODIFIERS:") + 19
            end = reply.find("]", start)
            if end != -1:
                item_id = int(reply[start:end].strip())
                modifiers = get_modifiers_for_item(item_id, menu)
                reply = f"We can modify: {', '.join(modifiers)}."
                print(f"  Direct Modifiers Response: {reply}")
        
        if not reply:
            raise ValueError("Empty response")
        
        # CHECK FOR COMMANDS BEFORE REMOVING THEM
        show_payment = "[CHECKOUT]" in reply
        show_cart = "[SHOW_CART]" in reply
        
        print(f"  Commands Detected: Checkout={show_payment}, ShowCart={show_cart}")
        
        # Parse cart commands
        updated_cart = parse_cart_commands(reply, cart, menu)
        
        # Remove cart command syntax from user-facing message
        clean_reply = remove_cart_commands(reply)
        
        print(f"  Clean Response: {clean_reply}")
        print(f"  Updated Cart: {len(updated_cart)} items")
        print(f"======================")
        
        return clean_reply, updated_cart, show_payment, show_cart
    except Exception as e:
        app.logger.error(f"Error generating reply: {e}")
        import traceback
        traceback.print_exc()
        return "I'm having trouble right now. Please try again.", cart, False, False


def get_modifiers_for_item(item_id: int, menu: List[Dict[str, Any]]) -> List[str]:
    """Get available modifiers for a specific menu item"""
    for item in menu:
        if item["id"] == item_id:
            modifiers = []
            for mod_group in item.get("modifier_groups", []):
                for mod in mod_group.get("modifiers", []):
                    modifiers.append(mod["name"])
            return modifiers
    return []


def parse_cart_commands(reply: str, cart: List[Dict[str, Any]], menu: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Parse cart management commands from AI response"""
    updated_cart = list(cart)
    
    # Check for ADD_TO_CART command
    if "[ADD_TO_CART:" in reply:
        start = reply.find("[ADD_TO_CART:") + 13
        end = reply.find("]", start)
        if end != -1:
            parts = [p.strip() for p in reply[start:end].split(",")]
            if len(parts) >= 2:
                item_id = int(parts[0])
                item_name = parts[1]
                modifiers = parts[2:] if len(parts) > 2 else []
                
                updated_cart.append({
                    "id": item_id,
                    "name": item_name,
                    "modifiers": modifiers
                })
    
    # Check for CLEAR_CART command
    if "[CLEAR_CART]" in reply:
        updated_cart = []
    
    return updated_cart


def remove_cart_commands(reply: str) -> str:
    """Remove cart command syntax from user-facing message"""
    import re
    reply = re.sub(r'\[ADD_TO_CART:[^\]]+\]', '', reply)
    reply = re.sub(r'\[VIEW_CART\]', '', reply)
    reply = re.sub(r'\[CLEAR_CART\]', '', reply)
    reply = re.sub(r'\[SHOW_CART\]', '', reply)
    reply = re.sub(r'\[CHECKOUT\]', '', reply)
    reply = re.sub(r'\[REQUEST_MODIFIERS:[^\]]+\]', '', reply)
    return reply.strip()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
