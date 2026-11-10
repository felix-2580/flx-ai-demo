from __future__ import annotations

from datetime import datetime
from urllib.parse import urlencode
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import json
import os
import re
import time
import threading
import urllib.error
import urllib.request

from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

# Groq model selection. GROQ_MODEL is optional; when omitted, FLX.AI
# discovers active models available to this API key and selects dynamically.
GROQ_MODEL_OVERRIDE = os.environ.get("GROQ_MODEL", "").strip()
GROQ_MODELS_CACHE_SECONDS = 600
_GROQ_MODELS_CACHE = {"expires": 0.0, "models": []}
_GROQ_MODELS_LOCK = threading.Lock()

SYSTEM_PROMPT = """You are FLX.AI, a helpful general-purpose AI assistant with an optional Windows companion.
Return exactly one JSON object with all three keys: "type", "command", and "message".
For an action, use {"type":"action","command":"canonical command","message":null}.
For an answer, use {"type":"answer","command":null,"message":"natural-language reply"}.
Never omit a key. Use null for the field that does not apply.

Use type=action ONLY when the user clearly asks FLX.AI to perform a supported Windows action.
Use type=answer for greetings, questions, explanations, opinions, brainstorming, coding help, writing help, study support, and normal conversation.
IDENTITY AND PRODUCT KNOWLEDGE:

You are FLX.AI, an AI-powered Windows assistant designed to combine
natural-language AI interaction with practical Windows desktop control.

You are not a generic chatbot. You are the intelligence layer of the
FLX.AI application. Your purpose is to help users interact with their
computer naturally, obtain information, solve problems and execute
supported Windows operations through the FLX.AI interface.

Always identify yourself as FLX.AI when users ask who you are,
what you do, or what application they are interacting with.

FLX.AI combines two primary operating modes:

1. AI MODE
2. LOCAL MODE

----------------------------------------
1. AI MODE – INTELLIGENT CONVERSATION
----------------------------------------

AI Mode uses the Groq API as the language-model backend.

Its purpose is to understand natural-language requests, answer questions,
interpret instructions and determine whether a request requires a supported
Windows action or a conversational response.

AI Mode supports:

A. General Knowledge and Conversation
- Answer general knowledge questions.
- Explain scientific, mathematical, technological and academic concepts.
- Discuss everyday topics and provide useful explanations.
- Answer follow-up questions using the conversation context.
- Brainstorm ideas and help users explore different approaches.
- Provide structured, contextually relevant responses.

B. Education and Learning
- Explain school and college-level concepts.
- Help solve mathematical and scientific problems.
- Explain programming concepts and algorithms.
- Assist with homework, revision and exam preparation.
- Break complicated topics into understandable steps.
- Provide examples when they improve understanding.

C. Programming and Technical Assistance
- Explain programming languages and technical concepts.
- Generate and debug code.
- Help identify errors and understand their causes.
- Suggest improvements to existing programs.
- Explain computer hardware, software and operating systems.

D. Writing and Productivity
- Draft and improve written content.
- Help with reports, documentation and presentations.
- Summarize information.
- Organize ideas into structured formats.
- Assist with planning and brainstorming.

E. Natural-Language Command Interpretation
- Understand commands expressed in ordinary language.
- Identify when a user intends to control Windows.
- Convert supported requests into canonical companion commands.
- Distinguish questions about an operation from requests to perform it.

IMPORTANT:
AI Mode does not independently control Windows. It interprets requests
and communicates supported actions to the Windows Companion.

----------------------------------------
2. LOCAL MODE – WINDOWS CONTROL
----------------------------------------

Local Mode is intended for direct interaction with supported Windows
functions through the FLX.AI Windows Companion.

The companion runs on the user's Windows computer and performs local
operations requested through FLX.AI.

Supported capabilities include:

A. Application Management
- Launch supported desktop applications.
- Open Calculator, Notepad, File Explorer, Settings,
  Task Manager and other configured applications.
- Open supported websites in a browser.
- Launch supported browser modes such as Guest and Incognito.
- Open common folders such as Downloads and Desktop.

B. System Audio Controls
- Increase system volume.
- Decrease system volume.
- Set volume to a requested percentage.
- Mute and unmute system audio.

C. Display Controls
- Increase screen brightness.
- Decrease screen brightness.
- Set brightness to a requested percentage,
  where supported by the hardware.

D. Wireless Connectivity
- Enable Wi-Fi.
- Disable Wi-Fi.
- Enable Bluetooth.
- Disable Bluetooth.
- Report success or failure based on the companion's result.

E. Window Management
- Minimize the active window.
- Maximize the active window.
- Restore a window.
- Close the active window.

F. Power and Session Management
- Lock the computer.
- Put the computer to sleep.
- Shut down the computer.
- Restart the computer.
- Cancel a pending shutdown when supported.

G. Media Controls
- Play or pause media.
- Skip to the next track.
- Return to the previous track.

H. System Monitoring
- Retrieve battery information.
- Check CPU usage.
- Check memory usage.
- Check available disk space.
- Check network status.
- View supported system information.
- Retrieve running-process information.

I. Desktop Utilities
- Capture a screenshot.
- Access supported clipboard operations.
- Perform calculations.
- Retrieve local date and time.

IMPORTANT:
The Windows Companion must actually support an operation before you
describe it as an available feature. Do not invent additional capabilities.

----------------------------------------
3. VOICE INTERACTION
----------------------------------------

FLX.AI provides a voice-input interface through its website.

Users can interact with the application using spoken commands instead
of typing every request.

Voice input is intended to support:
- Natural-language questions.
- Conversational interaction.
- Supported Windows commands.
- Hands-free command submission.

Voice input is an alternative method of providing instructions.
It does not provide additional Windows capabilities beyond those
supported by FLX.AI and its companion.

----------------------------------------
4. HOW FLX.AI PROCESSES REQUESTS
----------------------------------------

FLX.AI uses a request-processing workflow:

1. The user enters a message or provides a voice command.
2. The website backend receives the request.
3. AI Mode interprets the request when AI processing is required.
4. The backend determines whether the result is a conversational
   answer or a supported Windows action.
5. Conversational answers are returned to the interface.
6. Supported Windows actions are passed through the companion
   integration.
7. The Windows Companion executes the requested operation.
8. The execution result is returned to FLX.AI.
9. The interface displays the result and command status.

Never claim that a Windows operation has succeeded before receiving
confirmation from the companion.

----------------------------------------
5. HOW TO RESPOND ABOUT FLX.AI
----------------------------------------

When users ask "What can you do?", provide an organized overview
of the major FLX.AI capabilities.

When users ask "What commands do you support?", focus on actual
Windows operations rather than general AI conversation.

When users ask "What is AI Mode?", explain the Groq-powered
conversation and natural-language interpretation functionality.

When users ask "What is Local Mode?", explain the Windows Companion
and direct desktop-control functionality.

When users ask "Can you control my computer?", explain that FLX.AI
can execute supported Windows operations through its companion
running on the user's computer.

When users ask "How do you work?", explain the request-processing
workflow without exposing API keys, credentials or internal secrets.

When users ask about an unsupported feature, clearly state that
it is not currently supported.

----------------------------------------
6. ACCURACY AND CAPABILITY RESTRICTIONS
----------------------------------------

- Never claim unrestricted access to Windows.
- Never claim that every desktop application can be controlled.
- Never invent commands or companion functionality.
- Never claim to have executed an action without companion confirmation.
- Never confuse an AI-generated explanation with an executed operation.
- Never expose API keys, environment variables or private credentials.
- Clearly distinguish between AI Mode and Local Mode.
- Do not imply that voice input adds capabilities unavailable
  through the normal command interface.
- Keep explanations proportional to the user's question.

Your identity must consistently remain FLX.AI.
Your responses should reflect the actual capabilities of the
FLX.AI application rather than generic capabilities of an AI model.

Do not treat ordinary questions as Windows commands.

Supported Windows actions (use concise canonical commands):
- Open known apps, websites, and folders: open calculator; open file explorer; open chrome; open downloads; open youtube; open settings; open task manager; open guest mode in chrome; open incognito in chrome.
- Window management: minimize window; maximize window; restore window; close window.
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
    "compute ", "minimize window", "minimise window", "maximize window",
    "maximise window", "restore window", "close window", "help", "commands",
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
    """Recognize unambiguous local commands without spending a Groq request."""
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
        "minimize this window": "minimize window", "minimise this window": "minimize window",
        "minimize current window": "minimize window", "minimise current window": "minimize window",
        "maximize this window": "maximize window", "maximise this window": "maximize window",
        "restore this window": "restore window", "close this window": "close window",
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
        "minimize window", "minimise window", "maximize window", "maximise window",
        "restore window", "close window",
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
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:220]
        return answer(f"The weather provider returned HTTP {exc.code}. {detail or 'Please try again shortly.'}")
    except (urllib.error.URLError, TimeoutError) as exc:
        return answer(f"The weather service could not be reached ({type(exc).__name__}). Please try again shortly.")
    except Exception as exc:
        return answer(f"I couldn't retrieve live weather right now ({type(exc).__name__}: {exc}). Please try again shortly.")


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
    raw = (raw or "").strip().lstrip("\\ufeff")
    if not raw:
        raise ValueError("Groq returned an empty text part.")

    # Remove optional Markdown fences without assuming they are present.
    raw = re.sub(r"^\`\`\`(?:json)?\\s*", "", raw, flags=re.I)
    raw = re.sub(r"\\s*\`\`\`$", "", raw)

    # First try the complete response.
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
        raise ValueError("Groq JSON response was not an object.")
    except json.JSONDecodeError:
        pass

    # Some model responses contain a short preamble or trailing text.
    # Extract the first complete JSON object while respecting quoted braces.
    start = raw.find("{")
    if start < 0:
        raise ValueError("Groq response did not contain a JSON object.")

    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(raw)):
        char = raw[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                candidate = raw[start:index + 1]
                try:
                    parsed = json.loads(candidate)
                    if isinstance(parsed, dict):
                        return parsed
                    raise ValueError("Groq JSON response was not an object.")
                except json.JSONDecodeError:
                    # Allow harmless trailing commas before } or ].
                    repaired = re.sub(r",\\s*([}\\]])", r"\\1", candidate)
                    parsed = json.loads(repaired)
                    if isinstance(parsed, dict):
                        return parsed
                    raise ValueError("Groq JSON response was not an object.")

    raise ValueError("Groq response contained an incomplete JSON object.")


def discover_groq_models(key: str, force_refresh: bool = False):
    """Return active model IDs visible to this API key, cached for ten minutes."""
    now = time.monotonic()
    with _GROQ_MODELS_LOCK:
        if (
            not force_refresh
            and _GROQ_MODELS_CACHE["models"]
            and now < _GROQ_MODELS_CACHE["expires"]
        ):
            return list(_GROQ_MODELS_CACHE["models"])

        url = "https://api.groq.com/openai/v1/models"
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {key}",
                "User-Agent": "FLX.AI/1.0 (+https://github.com/felix-2580/flx-ai-demo)",
            },
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))

        entries = payload.get("data") or []
        model_ids = []
        excluded_terms = (
            "whisper", "transcribe", "speech", "audio", "embedding",
            "rerank", "guard", "safeguard", "moderation",
        )
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            model_id = str(entry.get("id", "")).strip()
            if not model_id or entry.get("active") is False:
                continue
            if any(term in model_id.lower() for term in excluded_terms):
                continue
            model_ids.append(model_id)

        # Prefer economical general-purpose chat models where available.
        # The API's model-list response does not expose prices or free-tier
        # eligibility; account access and rate limits are enforced by Groq.
        # Strict Structured Outputs are preferred because Groq constrains
        # generation to this application's schema for these exact model IDs.
        priority = {
            "openai/gpt-oss-20b": 0,
            "openai/gpt-oss-120b": 1,
            "qwen/qwen3.8-27b": 2,
        }
        model_ids = sorted(set(model_ids), key=lambda item: (priority.get(item, 100), item.lower()))

        _GROQ_MODELS_CACHE["models"] = model_ids
        _GROQ_MODELS_CACHE["expires"] = time.monotonic() + GROQ_MODELS_CACHE_SECONDS
        print(
            f"[FLX.AI][Groq] model_discovery_success active_chat_candidates={len(model_ids)}",
            flush=True,
        )
        return list(model_ids)


STRICT_JSON_MODELS = {
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
    "qwen/qwen3.8-27b",
}

FLX_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "type": {"type": "string", "enum": ["action", "answer"]},
        "command": {"type": ["string", "null"]},
        "message": {"type": ["string", "null"]},
    },
    "required": ["type", "command", "message"],
    "additionalProperties": False,
}


def groq_request(model: str, key: str, prompt: str):
    url = "https://api.groq.com/openai/v1/chat/completions"
    response_format = (
        {
            "type": "json_schema",
            "json_schema": {
                "name": "flx_ai_response",
                "strict": True,
                "schema": FLX_RESPONSE_SCHEMA,
            },
        }
        if model in STRICT_JSON_MODELS
        else {"type": "json_object"}
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "response_format": response_format,
        "temperature": 0.2,
        "max_completion_tokens": 2048,
        "stream": False,
    }
    request_data = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {key}",
            "User-Agent": "FLX.AI/1.0 (+https://github.com/felix-2580/flx-ai-demo)",
        },
        method="POST",
    )
    with urllib.request.urlopen(request_data, timeout=45) as response:
        return json.loads(response.read().decode("utf-8"))


def request_groq_with_retry(model: str, key: str, prompt: str):
    last_error = None
    max_attempts = 3

    for attempt in range(max_attempts):
        attempt_number = attempt + 1
        started_at = time.monotonic()
        print(
            f"[FLX.AI][Groq] request_start model={model} "
            f"attempt={attempt_number}/{max_attempts}",
            flush=True,
        )
        try:
            data = groq_request(model, key, prompt)
            elapsed = time.monotonic() - started_at
            print(
                f"[FLX.AI][Groq] request_success model={model} "
                f"attempt={attempt_number} duration_seconds={elapsed:.2f}",
                flush=True,
            )
            return data, None
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            try:
                error_json = json.loads(body).get("error", {})
                if isinstance(error_json, dict):
                    message = error_json.get("message", body[:1000])
                    status_name = error_json.get("code", error_json.get("type", ""))
                else:
                    message, status_name = str(error_json), ""
            except Exception:
                message, status_name = body[:1000], ""

            elapsed = time.monotonic() - started_at
            last_error = {"code": exc.code, "status": str(status_name), "message": message}
            retryable = exc.code in {408, 429, 500, 502, 503, 504}
            print(
                f"[FLX.AI][Groq] request_error model={model} "
                f"attempt={attempt_number}/{max_attempts} http_status={exc.code} "
                f"api_status={status_name or 'not_provided'} "
                f"duration_seconds={elapsed:.2f} message={message}",
                flush=True,
            )
            if not retryable or attempt_number >= max_attempts:
                break

            delay = 1.0 * (2 ** attempt)
            print(
                f"[FLX.AI][Groq] retrying model={model} "
                f"after_seconds={delay:.1f}",
                flush=True,
            )
            time.sleep(delay)
        except (urllib.error.URLError, TimeoutError) as exc:
            elapsed = time.monotonic() - started_at
            last_error = {"code": 0, "status": "NETWORK_ERROR", "message": str(exc)}
            print(
                f"[FLX.AI][Groq] network_error model={model} "
                f"attempt={attempt_number}/{max_attempts} "
                f"duration_seconds={elapsed:.2f} message={exc}",
                flush=True,
            )
            if attempt_number >= max_attempts:
                break
            time.sleep(1.0 * (2 ** attempt))
        except Exception as exc:
            elapsed = time.monotonic() - started_at
            last_error = {"code": 0, "status": "RESPONSE_ERROR", "message": f"{type(exc).__name__}: {exc}"}
            print(
                f"[FLX.AI][Groq] response_error model={model} "
                f"attempt={attempt_number} duration_seconds={elapsed:.2f} "
                f"message={type(exc).__name__}: {exc}",
                flush=True,
            )
            break

    return None, last_error


def model_error_allows_fallback(error):
    """Only switch models for model-specific or JSON-mode incompatibility."""
    if not error:
        return False
    code = error.get("code")
    status = str(error.get("status", "")).lower()
    message = str(error.get("message", "")).lower()

    # Cloudflare blocks and account-wide throttling are not fixed by changing models.
    if "1010" in message or "cloudflare" in message:
        return False
    if code == 404 or "model_not_found" in status:
        return True
    if code == 403:
        return "model" in message and any(word in message for word in ("access", "available", "permission", "not found"))
    if code == 400:
        return any(term in message for term in (
            "response_format", "json mode", "json_object", "structured output",
            "does not support", "not supported for this model",
            "failed to validate json", "failed_generation",
            "generated json", "invalid json",
        ))
    return False


def request_groq_with_fallback(key: str, prompt: str):
    """Try an optional configured model first, then discovered compatible candidates."""
    try:
        discovered = discover_groq_models(key)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        return None, {
            "code": exc.code,
            "status": "MODEL_DISCOVERY_ERROR",
            "message": detail or str(exc),
        }
    except Exception as exc:
        return None, {
            "code": 0,
            "status": "MODEL_DISCOVERY_ERROR",
            "message": f"{type(exc).__name__}: {exc}",
        }

    candidates = []
    if GROQ_MODEL_OVERRIDE:
        candidates.append(GROQ_MODEL_OVERRIDE)
    candidates.extend(model for model in discovered if model not in candidates)

    if not candidates:
        return None, {
            "code": 0,
            "status": "NO_CHAT_MODELS",
            "message": "Groq returned no active chat-model candidates for this API key.",
        }

    attempted = set()
    last_error = None
    refreshed_after_missing_model = False

    index = 0
    while index < len(candidates):
        model = candidates[index]
        index += 1
        if model in attempted:
            continue
        attempted.add(model)

        data, error = request_groq_with_retry(model, key, prompt)
        if not error:
            return data, None

        last_error = error
        if not model_error_allows_fallback(error):
            return None, error

        print(
            f"[FLX.AI][Groq] model_fallback_from={model} "
            f"reason={error.get('status') or error.get('code')}",
            flush=True,
        )

        if error.get("code") == 404 and not refreshed_after_missing_model:
            refreshed_after_missing_model = True
            try:
                refreshed = discover_groq_models(key, force_refresh=True)
                candidates.extend(item for item in refreshed if item not in attempted and item not in candidates)
            except Exception as exc:
                print(
                    f"[FLX.AI][Groq] model_refresh_failed "
                    f"error={type(exc).__name__}: {exc}",
                    flush=True,
                )

    return None, last_error

def validate_model_result(obj):
    if not isinstance(obj, dict):
        return answer("I received an invalid response from the AI service. Please try again.")

    response_type = obj.get("type")
    if response_type == "action":
        command = str(obj.get("command") or "").strip()
        lowered = command.lower()
        if command and lowered.startswith(ALLOWED_ACTION_PREFIXES):
            return action(command)
        return answer("I couldn't map that request to a supported Windows action. Try rephrasing it or ask me to explain what I can do.")

    if response_type == "answer":
        message = str(obj.get("message") or "").strip()
        return answer(message or "I couldn't form a response. Please try again.")

    return answer("I received an unexpected response format. Please try again.")


def ask_groq(prompt: str):
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        return answer("Groq is not configured. Add GROQ_API_KEY in the Render environment variables.")

    data, error = request_groq_with_fallback(key, prompt)

    if error:
        code = error.get("code")
        status = error.get("status", "")
        message = error.get("message", "No additional details were provided.")
        if code == 401:
            return answer("Groq authentication failed (401). Check the GROQ_API_KEY in Render.")
        if code == 403:
            if "1010" in str(message) or "cloudflare" in str(message).lower():
                return answer(f"Groq's security layer blocked FLX.AI (403): {message}.")
            return answer(f"Groq denied access to the available models (403): {message}.")
        if code == 404:
            return answer(f"None of the discovered models could be used (404): {message}")
        if code == 429:
            return answer(f"Groq rate limit or quota reached (429): {message}")
        if code == 400:
            return answer(f"Groq rejected the request (400): {message}. No compatible JSON-mode model was found.")
        if status == "NO_CHAT_MODELS":
            return answer("Groq did not return any active chat models for this API key.")
        if status == "MODEL_DISCOVERY_ERROR":
            return answer(f"FLX.AI couldn't retrieve your available Groq models: {message}")
        if code == 0:
            return answer(f"FLX.AI couldn't reach Groq ({status or 'network error'}): {message}")
        return answer(f"Groq request failed ({code}): {message}")

    choices = data.get("choices") or []
    if not choices:
        print(
            "[FLX.AI][Groq] response_parse_error error=no_choices finish_reason=unknown",
            flush=True,
        )
        return answer("Groq returned no response choices. Please try again.")

    choice = choices[0]
    message_obj = choice.get("message") or {}
    raw = message_obj.get("content") or ""
    finish_reason = choice.get("finish_reason", "unknown")

    if not raw.strip():
        print(
            f"[FLX.AI][Groq] response_parse_error "
            f"error=empty_content finish_reason={finish_reason}",
            flush=True,
        )
        return answer(f"Groq returned an empty response (finish reason: {finish_reason}). Please try again.")

    try:
        return validate_model_result(parse_model_json(raw))
    except Exception as exc:
        print(
            f"[FLX.AI][Groq] response_parse_error "
            f"error={type(exc).__name__}: {exc} finish_reason={finish_reason}",
            flush=True,
        )
        if finish_reason == "length":
            return answer("Groq reached its response-length limit. Please try asking for a shorter answer.")
        return answer(f"I couldn't understand the Groq response ({type(exc).__name__}). Please try again.")


@app.get("/")
def home():
    return render_template("index.html")


@app.get("/health")
def health():
    return jsonify({
        "status": "ok",
        "service": "FLX.AI",
        "ai_enabled": bool(os.environ.get("GROQ_API_KEY", "").strip()),
        "provider": "groq",
        "model": GROQ_MODEL_OVERRIDE or "automatic",
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
        interpreted = ask_groq(prompt)
        if interpreted.get("type") == "action":
            return jsonify(interpreted)
        return jsonify(answer("I couldn't map that to a supported Windows action. " + interpreted.get("message", "Try rephrasing the command.")))

    return jsonify(ask_groq(prompt))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
