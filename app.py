from flask import Flask, render_template, request, jsonify
from datetime import datetime
from urllib.parse import quote_plus
import ast
import operator
import re
import os

app = Flask(__name__)

# FLX.AI CROSS-DEVICE DEMO
# This hosted version intentionally does not execute commands on a visitor's PC.

SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def safe_calculate(expression):
    """Evaluate basic arithmetic without eval() or arbitrary code execution."""
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


@app.get("/")
def home():
    return render_template("index.html")


@app.get("/health")
def health():
    return jsonify({"status": "ok", "mode": "demo"})


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

    # Browser-local time is supplied by the user's device, not the hosting server.
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
            "Try these commands:\n"
            "• What time is it?\n"
            "• What is 125 * 8?\n"
            "• Search Google for artificial intelligence\n"
            "• Search YouTube for Python tutorials\n"
            "• Open YouTube\n"
            "• Increase volume / Decrease volume\n"
            "• Set brightness to 70%\n"
            "• Open Notepad\n\n"
            "The last three are simulated in Demo Mode; they do not change this device.",
            "help"
        )

    # Basic arithmetic: recognize "calculate ...", "what is ...", or a plain expression.
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

    # Search commands return links so the user chooses when to open an external site.
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

    if text in ("open google", "google"):
        return response("Google is ready to open in a new tab.", "search", "https://www.google.com")
    if text in ("open youtube", "youtube"):
        return response("YouTube is ready to open in a new tab.", "search", "https://www.youtube.com")
    if text in ("open chatgpt", "chatgpt"):
        return response("ChatGPT is ready to open in a new tab.", "search", "https://chatgpt.com")
    if text in ("open github", "github"):
        return response("GitHub is ready to open in a new tab.", "search", "https://github.com")

    # Explicitly simulated desktop/system actions.
    if any(word in text for word in ("volume", "brightness", "notepad", "calculator app",
                                     "file explorer", "open calculator", "open files",
                                     "open settings", "screenshot", "wifi", "wi-fi",
                                     "bluetooth", "shutdown", "restart", "lock pc",
                                     "open pycharm", "open chrome", "open edge")):
        return response(
            "DEMO MODE: I understood your system command — “" + clean + "”.\n\n"
            "On a computer with a local FLX.AI companion, this type of action could be connected "
            "to the operating system. In this hosted demo, no settings, apps, files, or power controls "
            "are changed.",
            "demo"
        )

    if any(greeting in text for greeting in ("hello", "hi flx", "hey flx", "good morning", "good afternoon")):
        return response("Hello! FLX.AI is online in cross-device Demo Mode. Ask me to calculate something, search the web, or try a simulated PC command.", "general")

    if "who are you" in text or "what is flx.ai" in text:
        return response("I'm FLX.AI, a browser-based assistant interface designed to demonstrate useful commands across devices. This build uses safe demo responses for local PC controls.", "general")

    return response(
        "I received your command: “" + clean + "”.\n\n"
        "I'm running in Demo Mode, so I can demonstrate supported commands but won't execute actions on the host computer. Type “help” to see examples.",
        "general"
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
