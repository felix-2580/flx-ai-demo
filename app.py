from __future__ import annotations

from datetime import datetime
from urllib.parse import urlencode
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import json
import os
import re
import time
import urllib.error
import urllib.request

from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

# Use stable Gemini models. These can be overridden in Render environment variables.
PRIMARY_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip()
FALLBACK_MODEL = os.environ.get("GEMINI_FALLBACK_MODEL", "").strip()

SYSTEM_PROMPT = """You are FLX.AI, a helpful general-purpose AI assistant with an optional Windows companion.
Return exactly one valid JSON object in one of these forms:
{"type":"action","command":"canonical command"}
{"type":"answer","message":"natural-language reply"}

Use type=action ONLY when the user clearly asks FLX.AI to perform a supported Windows action.
Use type=answer for greetings, questions, explanations, opinions, brainstorming, coding help, writing help, study support, and normal conversation.
When asked what you can do, explain that you can answer questions, explain concepts, help with schoolwork and coding, brainstorm, draft and improve text, and interpret supported Windows actions. Do not claim to control a PC unless you return a supported action for the companion.
Do not treat ordinary questions as Windows commands.

Supported Windows actions (use concise canonical commands):
- Open known apps, websites, and folders: open calculator; open file explorer; open chrome; open downloads; open youtube; open settings; open task manager.
- Search: search <query>.
- Volume: increase volume; decrease volume; increase volume by 10; decrease volume by 10; set volume to 50; mute; unmute.
- Brightness: increase brightness; decrease brightness; increase brightness by 10; decrease brightness by 10; set brightness to 50.
- Wireless radios: turn wifi on; turn wifi off; turn bluetooth on; turn bluetooth off.
- Power/session: lock computer; sleep computer; shut down computer; restart computer; cancel shutdown.
- Media: play pause; next track; previous track.
- Information: show battery; show cpu usage; show memory usage; show disk space; show network status; show system information; show running processes.
- Utilities: take screenshot; copy clipboard; copy text <text>; clear clipboard; what time; today's date; calculate <arithmetic expression>; help.

Interpret natural phrasing into the closest supported canonical command. Examples:
"make it quieter" -> decrease volume
"turn the sound down" -> decrease volume
"switch off wireless" -> turn wifi off
"enable bluetooth" -> turn bluetooth on
"launch my calculator" -> open calculator
"look up <topic>" -> search <topic>

Never output shell commands, PowerShell, Python, scripts, arbitrary code, file-deletion commands, or commands outside the supported actions.
Never claim an action was executed. The local Windows Companion performs the action and reports its result.
If the requested Windows action is unsupported, return type=answer and explain that it is not currently supported.
Return JSON only. Do not use Markdown fences."""

ALLOWED_ACTION_PREFIXES = (
    "open ", "search ",
    "increase volume", "decrease volume", "set volume", "mute", "unmute",
    "increase brightness", "decrease brightness", "set brightness",
    "turn wifi", "turn bluetooth", "lock computer", "lock pc",
    "sleep computer", "sleep pc", "shut down computer", "shutdown computer",
    "restart computer", "cancel shutdown", "play pause", "pause music",
    "resume music", "next track", "previous track", "show ",
    "take screenshot", "copy ", "clear clipboard", "what time", "current time",
    "tell me the time", "time now", "today", "what date", "calculate ",
    "compute ", "help", "commands",
)


def answer(message: str):
    return {"type": "answer", "message": str(message)}


def action(command: str):
    return {"type": "action", "command": str(command).strip()}


def clean_command(value: str) -> str:
    value = (value or "").strip().lower()
    value = value.replace("wi-fi", "wifi").replace("wi fi", "wifi")
    value = re.sub(r"[!?.,]+$", "", value)
    value = re.sub(r"\s+", " ", value)
    return value


def direct_action(user_text: str):
    """Recognize unambiguous local commands without spending a Gemini request."""
    text = clean_command(user_text)

    if text.startswith("search "):
        return action(text)
    if text.startswith("look up "):
        return action("search " + text[8:].strip())
    if text in {"can you open", "could you open", "open something", "launch something"}:
        return answer("Sure — what would you like me to open?")
    if text.startswith("open "):
        return action(text)

    # Volume command normalization. Amounts remain explicit when supplied.
    volume_amount = re.fullmatch(
        r"(?:increase|raise|boost|turn up|turn the volume up|decrease|lower|reduce|turn down|turn the volume down)\s+(?:the\s+)?volume(?:\s+by\s+(\d{1,3})(?:\s*(?:%|percent))?)?",
        text,
    )
    if volume_amount:
        amount = volume_amount.group(1)
        decrease = bool(re.match(r"(?:decrease|lower|reduce|turn down|turn the volume down)", text))
        if text.startswith("turn the volume up"):
            decrease = False
        return action(("decrease volume" if decrease else "increase volume") + (f" by {amount}" if amount else ""))
    if text in {
        "louder", "turn it up", "make it louder", "increase the sound", "volume up",
        "turn the volume up", "turn volume up", "turn up the volume", "turn up volume",
    }:
        return action("increase volume")
    if text in {
        "quieter", "turn it down", "make it quieter", "lower the sound", "volume down",
        "turn sound down", "turn the volume down", "turn volume down", "turn down the volume",
        "turn down volume", "decrease the volume", "reduce the volume",
    }:
        return action("decrease volume")
    match = re.fullmatch(r"(?:set|change) volume to (\d{1,3})(?:\s*(?:%|percent))?", text)
    if match:
        return action(f"set volume to {match.group(1)}")
    if text in {"mute", "mute audio", "mute volume", "unmute", "unmute audio", "unmute volume"}:
        return action("mute" if text.startswith("mute") and not text.startswith("unmute") else "unmute")

    # Brightness.
    match = re.fullmatch(r"(?:set|change) brightness to (\d{1,3})(?:\s*(?:%|percent))?", text)
    if match:
        return action(f"set brightness to {match.group(1)}")
    if text in {"increase brightness", "brightness up", "brighter", "turn brightness up"}:
        return action("increase brightness")
    if text in {"decrease brightness", "brightness down", "dimmer", "turn brightness down"}:
        return action("decrease brightness")

    # Wi-Fi radio aliases. These route to the radio API in companion.py.
    wifi_on = {"turn wifi on", "turn on wifi", "switch wifi on", "switch on wifi", "enable wifi", "wifi on", "turn wireless on", "enable wireless"}
    wifi_off = {"turn wifi off", "turn off wifi", "switch wifi off", "switch off wifi", "disable wifi", "wifi off", "turn wireless off", "disable wireless"}
    if text in wifi_on:
        return action("turn wifi on")
    if text in wifi_off:
        return action("turn wifi off")

    bluetooth_on = {"turn bluetooth on", "turn on bluetooth", "switch bluetooth on", "switch on bluetooth", "enable bluetooth", "bluetooth on"}
    bluetooth_off = {"turn bluetooth off", "turn off bluetooth", "switch bluetooth off", "switch off bluetooth", "disable bluetooth", "bluetooth off"}
    if text in bluetooth_on:
        return action("turn bluetooth on")
    if text in bluetooth_off:
        return action("turn bluetooth off")

    # Directly supported utilities and system commands.
    aliases = {
        "lock pc": "lock computer", "lock my pc": "lock computer", "lock my computer": "lock computer",
        "sleep pc": "sleep computer", "put computer to sleep": "sleep computer",
        "shut down": "shut down computer", "shutdown": "shut down computer",
        "restart": "restart computer", "reboot computer": "restart computer",
        "what time is it": "what time", "time now": "what time", "current time": "what time",
        "what is the time": "what time", "tell me the time": "what time",
        "what is today's date": "today's date", "what is the date": "today's date", "date today": "today's date",
        "battery status": "show battery", "show ram usage": "show memory usage",
        "show cpu": "show cpu usage", "show ram": "show memory usage",
        "show disk": "show disk space", "show network": "show network status",
        "screenshot": "take screenshot", "take a screenshot": "take screenshot",
        "copy clipboard": "copy clipboard", "clear clipboard": "clear clipboard",
        "play pause": "play pause", "pause music": "pause music", "resume music": "resume music",
        "next song": "next track", "previous song": "previous track",
        "help": "help", "show commands": "help",
    }
    if text in aliases:
        return action(aliases[text])

    for prefix in ("calculate ", "compute "):
        if text.startswith(prefix):
            return action(text)
    if text.startswith("copy text "):
        return action(text)
    if text in {
        "show battery", "show cpu usage", "show memory usage", "show disk space",
        "show running processes", "show network status", "show system information",
        "take screenshot", "copy clipboard", "clear clipboard", "today's date",
        "what date", "current date", "cancel shutdown", "play pause", "next track",
        "previous track", "help", "commands",
    }:
        return action(text)
    return None


def fetch_json(url: str, timeout: int = 10):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "FLX.AI/1.0", "Accept": "application/json"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def geocode_city(city: str):
    url = "https://geocoding-api.open-meteo.com/v1/search?" + urlencode({
        "name": city, "count": 1, "language": "en", "format": "json"
    })
    data = fetch_json(url)
    results = data.get("results") or []
    return results[0] if results else None


def weather_description(code: int) -> str:
    descriptions = {
        0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
        45: "Fog", 48: "Depositing rime fog", 51: "Light drizzle", 53: "Moderate drizzle",
        55: "Dense drizzle", 56: "Light freezing drizzle", 57: "Dense freezing drizzle",
        61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain", 66: "Light freezing rain",
        67: "Heavy freezing rain", 71: "Slight snowfall", 73: "Moderate snowfall",
        75: "Heavy snowfall", 77: "Snow grains", 80: "Slight rain showers",
        81: "Moderate rain showers", 82: "Violent rain showers", 85: "Slight snow showers",
        86: "Heavy snow showers", 95: "Thunderstorm", 96: "Thunderstorm with slight hail",
        99: "Thunderstorm with heavy hail",
    }
    return descriptions.get(int(code), "Conditions unavailable")


def live_weather(city: str):
    try:
        place = geocode_city(city)
        if not place:
            return answer(f"I couldn't find a location called {city}. Try adding its state or country.")
        params = (
            f"latitude={place['latitude']}&longitude={place['longitude']}"
            "&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m"
            "&timezone=auto"
        )
        data = fetch_json("https://api.open-meteo.com/v1/forecast?" + params)
        current = data.get("current", {})
        name = place.get("name", city)
        region = place.get("admin1") or place.get("country") or ""
        location = f"{name}, {region}" if region else name
        code = current.get("weather_code")
        description = weather_description(code) if code is not None else "Conditions unavailable"
        message = (
            f"Current weather for {location}: {description}. "
            f"Temperature: {current.get('temperature_2m', 'N/A')}°C; "
            f"feels like {current.get('apparent_temperature', 'N/A')}°C; "
            f"humidity {current.get('relative_humidity_2m', 'N/A')}%; "
            f"wind {current.get('wind_speed_10m', 'N/A')} km/h; "
            f"precipitation {current.get('precipitation', 'N/A')} mm."
        )
        return answer(message)
    except Exception as exc:
        return answer(f"I couldn't retrieve live weather right now ({type(exc).__name__}). Please try again shortly.")


def city_time(city: str):
    try:
        place = geocode_city(city)
        if not place or not place.get("timezone"):
            return answer(f"I couldn't identify the time zone for {city}. Try a larger city or include its country.")
        now = datetime.now(ZoneInfo(place["timezone"]))
        name = place.get("name", city)
        return answer(f"The local time in {name} is {now.strftime('%I:%M:%S %p')} on {now.strftime('%A, %d %B %Y')}.")
    except ZoneInfoNotFoundError:
        return answer("The time-zone database is unavailable on the server. Please try again later.")
    except Exception as exc:
        return answer(f"I couldn't retrieve the local time ({type(exc).__name__}). Please try again.")


def live_information_request(prompt: str):
    text = clean_command(prompt)
    weather = re.search(r"\b(?:weather|forecast)\b.*?\b(?:in|for|at)\s+(.+)$", text)
    if weather:
        return live_weather(weather.group(1).strip())
    if re.search(r"\b(?:weather|forecast)\b", text):
        return answer("Which city should I check the weather for? For example: 'weather in Chennai'.")

    time_match = re.search(r"\b(?:time|clock)\b.*?\b(?:in|for|at)\s+(.+)$", text)
    if time_match:
        return city_time(time_match.group(1).strip())
    return None


def parse_model_json(raw: str):
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.I)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            return json.loads(raw[start:end + 1])
        raise


def gemini_request(model: str, key: str, prompt: str):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "maxOutputTokens": 700,
        },
    }
    request_data = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
        method="POST",
    )
    with urllib.request.urlopen(request_data, timeout=25) as response:
        return json.loads(response.read().decode("utf-8"))


def request_model_with_retry(model: str, key: str, prompt: str):
    last_error = None
    # Do not multiply Gemini usage with automatic retries.
    for attempt in range(1):
        try:
            return gemini_request(model, key, prompt), None
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            try:
                error_json = json.loads(body).get("error", {})
                message = error_json.get("message", body[:500])
                status_name = error_json.get("status", "")
            except Exception:
                message, status_name = body[:500], ""
            last_error = {"code": exc.code, "status": status_name, "message": message}
            retryable = exc.code in {500, 503, 504} or (
                exc.code == 429 and status_name.lower() not in {"quota_exceeded"}
            )
            if not retryable or attempt == 1:
                break
            time.sleep(0.8 * (2 ** attempt))
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = {"code": 0, "status": "NETWORK_ERROR", "message": str(exc)}
            if attempt == 1:
                break
            time.sleep(0.8 * (2 ** attempt))
        except Exception as exc:
            last_error = {"code": 0, "status": "RESPONSE_ERROR", "message": f"{type(exc).__name__}: {exc}"}
            break
    return None, last_error


def validate_model_result(obj):
    if not isinstance(obj, dict):
        return answer("I received an invalid response from the AI service. Please try again.")

    response_type = obj.get("type")
    if response_type == "action":
        command = str(obj.get("command", "")).strip()
        lowered = command.lower()
        if command and lowered.startswith(ALLOWED_ACTION_PREFIXES):
            return action(command)
        return answer("I couldn't map that request to a supported Windows action. Try rephrasing it or ask me to explain what I can do.")

    if response_type == "answer":
        message = str(obj.get("message", "")).strip()
        return answer(message or "I couldn't form a response. Please try again.")

    return answer("I received an unexpected response format. Please try again.")


def ask_gemini(prompt: str):
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        return answer("Gemini is not configured. Add GEMINI_API_KEY in the Render environment variables.")

    # First try the configured primary model, then a cheaper stable fallback.
    models = [PRIMARY_MODEL]
    if FALLBACK_MODEL and FALLBACK_MODEL != PRIMARY_MODEL:
        models.append(FALLBACK_MODEL)

    errors = []
    for index, model in enumerate(models):
        data, error = request_model_with_retry(model, key, prompt)
        if error:
            errors.append((model, error))
            # Only switch model for service/capacity/network failures. Bad key or malformed request won't improve with another model.
            code = error.get("code")
            status = str(error.get("status", "")).lower()
            if index == 0 and FALLBACK_MODEL and code in {500, 503, 504}:
                continue
            break

        try:
            candidates = data.get("candidates") or []
            parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
            raw = "\n".join(part.get("text", "") for part in parts if part.get("text"))
            if not raw:
                finish = candidates[0].get("finishReason", "unknown") if candidates else "no candidates"
                return answer(f"The AI service returned no text (finish reason: {finish}). Please rephrase and try again.")
            return validate_model_result(parse_model_json(raw))
        except Exception as exc:
            return answer(f"I couldn't understand the AI service response ({type(exc).__name__}). Please try again.")

    if errors:
        model, error = errors[-1]
        code = error.get("code")
        message = error.get("message", "No additional details were provided.")
        if code == 503:
            return answer("Gemini is temporarily overloaded or unavailable (503). FLX.AI retried and tried its fallback model, but the service still did not respond. This does not by itself mean your API key is invalid. Please try again in a little while.")
        if code == 429:
            return answer(f"Gemini rate limit or quota issue (429): {message}")
        if code in {401, 403}:
            return answer(f"Gemini authentication/permission error ({code}): {message}. Check the GEMINI_API_KEY and API access in Google AI Studio.")
        if code == 400:
            return answer(f"Gemini rejected the request (400): {message}. Check the model name and request settings.")
        if code == 0:
            return answer(f"FLX.AI couldn't reach Gemini ({error.get('status', 'network error')}): {message}")
        return answer(f"Gemini request failed ({code}) using {model}: {message}")

    return answer("Gemini did not return a usable response. Please try again.")


@app.get("/")
def home():
    return render_template("index.html")


@app.get("/health")
def health():
    return jsonify({
        "status": "ok",
        "service": "FLX.AI",
        "ai_enabled": bool(os.environ.get("GEMINI_API_KEY", "").strip()),
        "primary_model": PRIMARY_MODEL,
        "fallback_model": FALLBACK_MODEL,
    })


@app.post("/api/command")
def api_command():
    payload = request.get_json(silent=True) or {}
    prompt = str(payload.get("command", "")).strip()
    mode = str(payload.get("mode", "unified")).strip().lower()

    if not prompt:
        return jsonify(answer("Enter a message or command.")), 400
    if len(prompt) > 2000:
        return jsonify(answer("Please keep your message under 2,000 characters.")), 400

    live_result = live_information_request(prompt)
    if live_result is not None:
        return jsonify(live_result)

    direct = direct_action(prompt)
    if direct is not None:
        return jsonify(direct)

    if mode == "local":
        interpreted = ask_gemini(prompt)
        if interpreted.get("type") == "action":
            return jsonify(interpreted)
        return jsonify(answer("I couldn't map that to a supported Windows action. " + interpreted.get("message", "Try rephrasing the command.")))

    return jsonify(ask_gemini(prompt))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
