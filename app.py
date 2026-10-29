from flask import Flask, render_template, request, jsonify
from datetime import datetime
from urllib.parse import quote_plus
import ast, operator, re, os, json, urllib.request, urllib.error

app = Flask(__name__)
SAFE_OPERATORS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
    ast.Pow: operator.pow, ast.USub: operator.neg, ast.UAdd: operator.pos}

def response(message, category="general", url=None, command=None, success=None):
    if command is None:
        try:
            payload = request.get_json(silent=True) or {}
            command = str(payload.get("command", ""))
        except Exception:
            command = ""
    if success is None:
        success = category != "error"
    data = {
        "success": bool(success),
        "message": str(message),
        "state": "success" if success else "error",
        "command": command,
        "category": category,
    }
    if url:
        data["url"] = url
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
    mode = str(payload.get("mode", "local")).lower()
    if not raw:
        return response("Type a command first.", "error", command=raw, success=False), 400
    if len(raw) > 500:
        return response("Please keep prompts under 500 characters.", "error", command=raw, success=False), 400
    if mode != "ai":
        return response("Local Mode commands must run through the FLX.AI Windows Companion on this PC.", "error", command=raw, success=False), 400
    answer = ask_gemini(raw)
    if answer:
        failed = answer.startswith("The AI service is temporarily unavailable") or answer.startswith("AI Mode needs")
        return response(answer, "error" if failed else "ai", command=raw, success=not failed), (503 if failed else 200)
    return response("AI Mode needs a Gemini API key. Add GEMINI_API_KEY in your Render environment variables, then redeploy.", "error", command=raw, success=False), 503

if __name__ == "__main__": app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
