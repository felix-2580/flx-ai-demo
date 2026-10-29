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
