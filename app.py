from flask import Flask, render_template, request, jsonify
from datetime import datetime
from urllib.parse import quote_plus
import ast, operator, re, os, json, urllib.request, urllib.error

app = Flask(__name__)
SAFE_OPERATORS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
    ast.Pow: operator.pow, ast.USub: operator.neg, ast.UAdd: operator.pos}

def response(message, category="general", url=None):
    data = {"message": message, "category": category}
    if url: data["url"] = url
    return jsonify(data)

def safe_calculate(expression):
    expression = expression.strip().replace("^", "**")
    if not expression or len(expression) > 100: raise ValueError("Enter a short arithmetic expression.")
    tree = ast.parse(expression, mode="eval")
    def visit(node):
        if isinstance(node, ast.Expression): return visit(node.body)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float): return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in SAFE_OPERATORS:
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 8: raise ValueError("That exponent is too large.")
            result = SAFE_OPERATORS[type(node.op)](left, right)
            if abs(result) > 1e100: raise ValueError("That result is too large.")
            return result
        if isinstance(node, ast.UnaryOp) and type(node.op) in SAFE_OPERATORS: return SAFE_OPERATORS[type(node.op)](visit(node.operand))
        raise ValueError("Use numbers and basic operators only (+, -, *, /, //, %, **).")
    return visit(tree)

def ask_gemini(prompt):
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key: return None
    endpoint = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key=" + quote_plus(api_key)
    payload = {"system_instruction": {"parts": [{"text": "You are FLX.AI, a concise and helpful assistant. Never claim you changed a computer or opened local files. Explain that actual Windows actions require the local FLX.AI Companion. Do not ask for passwords, API keys, or sensitive information."}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.6, "maxOutputTokens": 600}}
    req = urllib.request.Request(endpoint, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as result: data = json.loads(result.read().decode())
        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            return "\n".join(p.get("text", "") for p in parts if p.get("text")).strip() or "I couldn't form a response. Try again."
        return "I couldn't form a response. Try asking another way."
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError):
        return "The AI service is temporarily unavailable or has reached its limit. Try again later."

@app.get("/")
def home(): return render_template("index.html")

@app.get("/health")
def health(): return jsonify({"status": "ok", "service": "FLX.AI", "ai_enabled": bool(os.environ.get("GEMINI_API_KEY"))})

@app.post("/api/command")
def command():
    payload = request.get_json(silent=True) or {}
    raw = str(payload.get("command", "")).strip()
    browser_time = str(payload.get("browser_time", "")).strip()
    mode = str(payload.get("mode", "local")).lower()
    if not raw: return response("Type a command first.", "error"), 400
    if len(raw) > 500: return response("Please keep commands under 500 characters.", "error"), 400
    text = raw.lower().strip()
    if mode == "ai":
        answer = ask_gemini(raw)
        if answer: return response(answer, "ai")
        return response("AI Mode needs a Gemini API key. Add GEMINI_API_KEY in your Render environment variables, then redeploy.", "error"), 503
    if any(p in text for p in ("what time", "current time", "tell me the time", "time now")):
        try: return response("Your device's local time is " + datetime.fromisoformat(browser_time.replace("Z", "+00:00")).strftime("%I:%M %p") + ".", "utility")
        except ValueError: return response("I couldn't read your device time. Check your device clock.", "utility")
    if any(p in text for p in ("today's date", "todays date", "what date", "current date", "date today")):
        try: return response("Your device's local date is " + datetime.fromisoformat(browser_time.replace("Z", "+00:00")).strftime("%A, %d %B %Y") + ".", "utility")
        except ValueError: return response("I couldn't read your device date.", "utility")
    if text in ("help", "commands", "what can you do", "show commands"):
        return response("Local Mode: open apps and folders, control volume/brightness, manage windows, media keys, Wi-Fi adapter and screenshots through the local companion. Web: search Google/YouTube. Utilities: date, time and arithmetic. AI Mode needs GEMINI_API_KEY.", "help")
    math_candidate = None
    for prefix in ("calculate ", "compute ", "what is ", "what's "):
        if text.startswith(prefix): math_candidate = raw[len(prefix):].strip().rstrip("?"); break
    if math_candidate is None and re.fullmatch(r"[\d\s.+\-*/()%^]+", raw): math_candidate = raw
    if math_candidate is not None:
        try:
            result = safe_calculate(math_candidate)
            if isinstance(result, float) and result.is_integer(): result = int(result)
            return response(f"{math_candidate} = {result}", "utility")
        except (ValueError, SyntaxError, ZeroDivisionError, OverflowError) as exc: return response(f"I couldn't calculate that: {exc}", "utility")
    match = re.match(r"^(?:search(?: google)? for|google search for)\s+(.+)$", raw, re.I)
    if match:
        q = match.group(1).strip(); return response("Ready to search Google for: " + q, "search", "https://www.google.com/search?q=" + quote_plus(q))
    match = re.match(r"^(?:search youtube for|youtube search for)\s+(.+)$", raw, re.I)
    if match:
        q = match.group(1).strip(); return response("Ready to search YouTube for: " + q, "search", "https://www.youtube.com/results?search_query=" + quote_plus(q))
    links = {"open google": "https://www.google.com", "google": "https://www.google.com", "open youtube": "https://www.youtube.com", "youtube": "https://www.youtube.com", "open chatgpt": "https://chatgpt.com", "chatgpt": "https://chatgpt.com", "open github": "https://github.com", "github": "https://github.com"}
    if text in links: return response("Opening " + text.replace("open ", "") + " in a new tab.", "search", links[text])
    answer = ask_gemini(raw)
    if answer: return response(answer, "ai")
    return response("I don't recognise that as a web or utility command. For Windows actions, use Local Mode with FLX.AI Companion running on this same PC. For open-ended questions, configure GEMINI_API_KEY on Render.", "general")

if __name__ == "__main__": app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
