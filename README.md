# FLX.AI — Minimal, Free-First Web Assistant

A responsive Flask web app with a single sound-reactive reactor orb, a bottom command bar, sample commands, optional browser voice input, and an optional Gemini AI response backend.

## What works without an AI API

- Safe arithmetic such as `What is 125 * 8?`
- Device-local date and time
- Google and YouTube search links
- Basic help and greetings
- Simulated desktop commands such as volume, brightness, opening apps, files, Wi-Fi, and power actions
- Microphone-driven orb animation while voice mode is active

The hosted site cannot directly control the visitor's computer. Those actions remain clearly labelled as Demo Mode unless a separate local companion app is built later. The microphone is requested only when the visitor clicks the microphone button; sound levels are processed locally in the browser and audio is not uploaded by the sound visualizer. If voice recognition is available, the browser's speech-recognition service may process speech according to that browser/provider's rules.

## Optional free AI answers (Gemini API)

The app uses Google's `gemini-2.5-flash-lite` through the API only if `GEMINI_API_KEY` is configured. Without a key, it still supports the non-AI commands above and responds with a note about the optional AI feature.

1. Open Google AI Studio: https://aistudio.google.com/app/apikey
2. Create an API key for the Gemini API. Check the current free-tier models, limits, and terms before use: https://ai.google.dev/gemini-api/docs/pricing
3. In Render, open your FLX.AI Web Service → **Environment** → **Add Environment Variable**.
4. Set **Key** to `GEMINI_API_KEY` and **Value** to your key. Save changes and redeploy if prompted.
5. Never put the key in `app.py`, `index.html`, GitHub, screenshots, or public messages. Keep the API on its free tier; do not enable billing. Free-tier limits may change, and Google says free-tier content may be used to improve its products, so don't send private or sensitive information.

If the key is absent or the free-tier limit is reached, the app falls back to the built-in commands or gives a temporary-unavailable message. No paid API is required to run the base app.

## Run locally (optional)

Python 3.10+ recommended.

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000`.

## Deploy / update on Render

1. Upload these project files to the root of the existing GitHub repository, keeping `index.html` inside `templates/`.
2. Render settings: Build command `pip install -r requirements.txt`; Start command `gunicorn app:app`.
3. Commit changes to GitHub. If auto-deploy is enabled, Render deploys the new commit; otherwise choose **Manual Deploy → Deploy latest commit**.
4. Keep using the same Render URL.

## Project structure

```text
FLX_AI_Free_Minimal/
├── app.py
├── requirements.txt
├── render.yaml
├── README.md
├── .gitignore
└── templates/
    └── index.html
```
