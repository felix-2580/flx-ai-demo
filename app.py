from flask import Flask, render_template, request, jsonify
from datetime import datetime
from urllib.parse import quote_plus
import ast
import operator
import re
import os
import json
import urllib.request
import urllib.error

app = Flask(__name__)

# FLX.AI: responsive hosted demo. Local PC controls are deliberately simulated.
# Optional AI uses Google's Gemini API only when GEMINI_API_KEY is configured.
# Keep API keys in the hosting provider's environment variables, never in GitHub.

SAFE_OPERATORS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod, ast.Pow: operator.pow,
    ast.USub: operator.neg, ast.UAdd: operator.pos,
}


def safe_calculate(expression):
    expression = expression.strip().replace("^", "**")
    if not expression or len(expression) > 100:
        raise ValueError("Enter a short arithmetic expression.")
    tree = ast.parse(expression, mode="eval")

    def visit(node):
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in SAFE_OPERATORS:
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 8:
                raise ValueError("That exponent is too large for this demo.")
            result = SAFE_OPERATORS[type(node.op)](left, right)
            if abs(result) > 1e100:
                raise ValueError("That result is too large.")
            return result
        if isinstance(node, ast.UnaryOp) and type(node.op) in SAFE_OPERATORS:
            return SAFE_OPERATORS[type(node.op)](visit(node.operand))
        raise ValueError("Use numbers and basic operators only (+, -, *, /, //, %, **).")

    return visit(tree)


def response(message, category="general", url=None):
    data = {"message": message, "category": category, "demo": True}
    if url:
        data["url"] = url
    return jsonify(data)


def ask_gemini(prompt):
    """Call Gemini's free-tier model if an API key is configured; otherwise return None."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None

    endpoint = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-2.5-flash-lite:generateContent?key=" + quote_plus(api_key)
    )
    payload = {
        "system_instruction": {
            "parts": [{"text": (
                "You are FLX.AI, a concise, friendly general assistant in a school project demo. "
                "Answer clearly and helpfully. Never claim to have changed the visitor's computer, "
                "opened local apps, accessed files, or performed actions you did not perform. "
                "If asked to control volume, brightness, apps, files, Wi-Fi, Bluetooth, or power, "
                "explain that this hosted website can only simulate those local controls. "
                "Do not request passwords, API keys, or sensitive personal information."
            )}]
        },
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.6, "maxOutputTokens": 500}
    }
    request_obj = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request_obj, timeout=20) as result:
            data = json.loads(result.read().decode("utf-8"))
        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            answer = "\n".join(p.get("text", "") for p in parts if p.get("text"))
            return answer.strip() or "I couldn't form a response just now. Try again."
        return "I couldn't form a response just now. Try asking in a different way."
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError):
        return "The free AI service is temporarily unavailable or has reached its limit. Try again later, or use a sample command."


@app.get("/")
def home():
    return render_template("index.html")


@app.get("/health")
def health():
    return jsonify({"status": "ok", "mode": "demo", "ai_enabled": bool(os.environ.get("GEMINI_API_KEY"))})


@app.post("/api/command")
def command():
    payload = request.get_json(silent=True) or {}
    raw = str(payload.get("command", "")).strip()
    browser_time = str(payload.get("browser_time", "")).strip()

    if not raw:
        return response("Type a command first.", "error"), 400
    if len(raw) > 500:
        return response("Please keep commands under 500 characters.", "error"), 400

    text = raw.lower().strip()
    clean = raw.strip()

    if any(phrase in text for phrase in ("what time", "current time", "tell me the time", "time now")):
        if browser_time:
            try:
                local_dt = datetime.fromisoformat(browser_time.replace("Z", "+00:00"))
                return response("Your device's local time is " + local_dt.strftime("%I:%M %p") + ".", "utility")
            except ValueError:
                pass
        return response("I couldn't read your device time. Check the clock on this device.", "utility")

    if any(phrase in text for phrase in ("today's date", "todays date", "what date", "current date", "date today")):
        if browser_time:
            try:
                local_dt = datetime.fromisoformat(browser_time.replace("Z", "+00:00"))
                return response("Your device's local date is " + local_dt.strftime("%A, %d %B %Y") + ".", "utility")
            except ValueError:
                pass
        return response("I couldn't read your device date. Check the date on this device.", "utility")

    if text in ("help", "commands", "what can you do", "show commands"):
        return response(
            "Try: What time is it? · What is 125 * 8? · Search Google for artificial intelligence · "
            "Search YouTube for Python tutorials · Open YouTube · Increase volume · Set brightness to 70%.\n\n"
            "Calculations, date/time, and search links work. PC controls are simulated in hosted Demo Mode.",
            "help"
        )

    math_candidate = None
    for prefix in ("calculate ", "compute ", "what is ", "what's "):
        if text.startswith(prefix):
            math_candidate = clean[len(prefix):].strip().rstrip("?")
            break
    if math_candidate is None and re.fullmatch(r"[\d\s.+\-*/()%^]+", clean):
        math_candidate = clean
    if math_candidate is not None:
        try:
            result = safe_calculate(math_candidate)
            if isinstance(result, float) and result.is_integer():
                result = int(result)
            return response(f"{math_candidate} = {result}", "utility")
        except (ValueError, SyntaxError, ZeroDivisionError, OverflowError) as exc:
            return response(f"I couldn't calculate that: {exc}", "utility")

    google_match = re.match(r"^(?:search google for|google search for|search for)\s+(.+)$", clean, re.I)
    if google_match:
        query = google_match.group(1).strip()
        return response(f"Ready to search Google for: {query}", "search",
                        "https://www.google.com/search?q=" + quote_plus(query))

    youtube_match = re.match(r"^(?:search youtube for|youtube search for)\s+(.+)$", clean, re.I)
    if youtube_match:
        query = youtube_match.group(1).strip()
        return response(f"Ready to search YouTube for: {query}", "search",
                        "https://www.youtube.com/results?search_query=" + quote_plus(query))

    simple_links = {
        "open google": ("Google is ready to open in a new tab.", "https://www.google.com"),
        "google": ("Google is ready to open in a new tab.", "https://www.google.com"),
        "open youtube": ("YouTube is ready to open in a new tab.", "https://www.youtube.com"),
        "youtube": ("YouTube is ready to open in a new tab.", "https://www.youtube.com"),
        "open chatgpt": ("ChatGPT is ready to open in a new tab.", "https://chatgpt.com"),
        "chatgpt": ("ChatGPT is ready to open in a new tab.", "https://chatgpt.com"),
        "open github": ("GitHub is ready to open in a new tab.", "https://github.com"),
        "github": ("GitHub is ready to open in a new tab.", "https://github.com"),
    }
    if text in simple_links:
        message, link = simple_links[text]
        return response(message, "search", link)

    if any(word in text for word in ("volume", "brightness", "notepad", "calculator app", "file explorer",
                                     "open calculator", "open files", "open settings", "screenshot", "wifi",
                                     "wi-fi", "bluetooth", "shutdown", "restart", "lock pc", "open pycharm",
                                     "open chrome", "open edge")):
        return response(
            "Demo Mode: I understood your system command — “" + clean + "”.\n\n"
            "This hosted website cannot change settings or open apps on the visitor's device. "
            "Those actions would require a separate local companion app.", "demo"
        )

    ai_reply = ask_gemini(clean)
    if ai_reply:
        return response(ai_reply, "ai")

    if any(greeting in text for greeting in ("hello", "hi flx", "hey flx", "good morning", "good afternoon")):
        return response("Hello! I'm FLX.AI. Try a calculation, a web search, or ask me a question. For more examples, type help.", "general")
    if "who are you" in text or "what is flx.ai" in text:
        return response("I'm FLX.AI, a free-first assistant demo. Calculations, date/time, and search links work without an AI API; optional AI replies are enabled when a Gemini API key is configured.", "general")

    return response(
        "I can handle calculations, date/time, and search commands without an API. For open-ended questions, add a free Gemini API key in Render's environment variables. Type help to see examples.",
        "general"
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
