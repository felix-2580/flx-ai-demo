from flask import Flask, jsonify, render_template, request
from urllib.parse import quote_plus
import json
import os
import urllib.request
import urllib.error

app = Flask(__name__)

SYSTEM_PROMPT = """You are FLX.AI. Return exactly one JSON object:
{"type":"action","command":"canonical command"} OR {"type":"answer","message":"reply"}.
For actions, choose only simple commands supported by the FLX.AI Windows Companion:
open apps/websites/folders (e.g. open calculator, open file explorer, open downloads, open youtube);
search <query>;
increase/decrease volume, mute, unmute, set volume to 50;
increase/decrease brightness, set brightness to 50;
turn wifi on/off; turn bluetooth on/off;
lock computer; sleep computer; shut down computer; restart computer; cancel shutdown;
play pause; next track; previous track;
show battery/cpu/memory/disk/network information; take screenshot;
what time; today's date; calculate <math expression>; help.
Never output shell, PowerShell, Python, scripts, arbitrary code, or commands outside this companion's supported actions.
Questions, explanations and normal conversation must be type=answer.
Never claim an action was executed; the local companion executes it.
Return valid JSON only, no Markdown fences."""

def ask_gemini(prompt):
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        return {"type": "answer", "message": "Gemini is not configured. Add GEMINI_API_KEY in the Render environment variables."}
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent?key=" + quote_plus(key)
    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 350, "responseMimeType": "application/json"}
    }
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            result = json.loads(response.read().decode())
        parts = result.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        raw = "\n".join(p.get("text", "") for p in parts if p.get("text")).strip()
        obj = json.loads(raw)
        if obj.get("type") == "action":
            action = str(obj.get("command", "")).strip()
            allowed_starts = (
                "open ", "search ", "increase volume", "decrease volume", "set volume",
                "mute", "unmute", "increase brightness", "decrease brightness", "set brightness",
                "turn wifi", "turn bluetooth", "lock computer", "sleep computer",
                "shut down computer", "shutdown computer", "restart computer", "cancel shutdown",
                "play pause", "pause music", "resume music", "next track", "previous track",
                "show ", "take screenshot", "copy ", "clear clipboard", "what time",
                "current time", "tell me the time", "today", "what date", "calculate ",
                "compute ", "help", "commands"
            )
            if action.lower().startswith(allowed_starts):
                return {"type": "action", "command": action}
            return {"type": "answer", "message": "I couldn't map that to a supported Windows action. Try rephrasing it."}
        return {"type": "answer", "message": str(obj.get("message", "")).strip() or "I couldn't form a response. Try again."}
    except urllib.error.HTTPError as exc:
        return {"type": "answer", "message": f"Gemini request failed ({exc.code}). Check the Render API configuration."}
    except Exception:
        return {"type": "answer", "message": "I couldn't reach the AI service or understand its response. Please try again."}

@app.get("/")
def home():
    return render_template("index.html")

@app.get("/health")
def health():
    return jsonify({"status": "ok", "service": "FLX.AI", "ai_enabled": bool(os.environ.get("GEMINI_API_KEY", "").strip())})

@app.post("/api/command")
def api_command():
    payload = request.get_json(silent=True) or {}
    command = str(payload.get("command", "")).strip()
    if not command:
        return jsonify({"type": "answer", "message": "Enter a message or command."}), 400
    return jsonify(ask_gemini(command))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
