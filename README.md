# FLX.AI — Cross-Device Demo

A responsive Flask web app based on the FLX.AI interface. It is designed to be hosted and opened from a browser on laptops, desktops, tablets, and phones.

## Important: Demo Mode

This hosted version **does not control the visitor's actual computer**. Commands for volume, brightness, applications, files, Wi-Fi, Bluetooth, screenshots, and power controls return a clearly labelled simulation. This is intentional: a cloud-hosted website cannot directly run Windows commands on each visitor's device.

## Features

- Responsive dark futuristic interface
- Command chat UI and quick-command buttons
- Optional browser speech recognition (browser support varies)
- Basic arithmetic calculator with safe parsing (no `eval`)
- Browser-local time/date responses
- Google and YouTube searches returned as clickable links
- Simulated responses for local computer controls
- `/health` endpoint for deployment checks
- No third-party browser-side libraries

## Run locally (optional test)

Python 3.10+ is recommended.

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

Then open `http://127.0.0.1:5000`.

## Deploy online with Render

You will need a GitHub account and a Render account. You do **not** need to install Python or project libraries on the demonstration computer.

1. Extract this ZIP into a folder named `FLX_AI_Cross_Device`.
2. Create a new GitHub repository (for example, `flx-ai-demo`).
3. Upload the contents of this folder to the repository. Make sure `app.py`, `requirements.txt`, and `render.yaml` are in the repository's root, and `index.html` is inside `templates/`.
4. Open the Render dashboard: https://dashboard.render.com/
5. Choose **New → Web Service** and connect the repository.
6. Render should detect the `render.yaml` settings. If it asks you to configure them, use:
   - **Runtime:** Python
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `gunicorn app:app`
7. Create/deploy the service and wait for the build to finish.
8. Open the public `https://...onrender.com` URL Render gives you.
9. Test `help`, `What is 125 * 8?`, `Search Google for artificial intelligence`, and `Increase volume`.
10. Share that URL with your teacher or open it on the demonstration computer.

Render's free web services can sleep after a period of inactivity, so the first visit after a quiet period may take a little time to load. Check the current plan limits on Render before the demonstration.

## Suggested demo sequence

1. Open the hosted URL on the school computer.
2. Show that the same page fits the screen without copying project files onto that computer.
3. Type `What is 125 * 8?` to demonstrate a working utility.
4. Type `Search Google for artificial intelligence` and click **Open link**.
5. Type `Set brightness to 70%` and explain that the system recognizes the command but simulates it in hosted Demo Mode.
6. Use the same URL on a phone to demonstrate responsive layout.

## Project structure

```text
FLX_AI_Cross_Device/
├── app.py
├── requirements.txt
├── render.yaml
├── README.md
├── .gitignore
└── templates/
    └── index.html
```

## Troubleshooting

- **Build fails:** open the Render service's Events/Logs and check the first error. Confirm that `requirements.txt` is in the repository root.
- **Page opens but commands fail:** visit `/health` on the same domain. It should return JSON containing `"status": "ok"`.
- **Voice button does nothing:** speech recognition support varies by browser and permissions. Typing commands always works.
- **Slow first load:** a free hosted service may have gone to sleep. Open the URL a few minutes before your presentation.

## Safety / privacy

This demo does not need access to your files, camera, microphone (unless you choose the browser voice feature), or operating-system controls. Voice input is optional and handled by the browser's speech-recognition support.
