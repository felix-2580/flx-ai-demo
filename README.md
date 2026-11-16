# FLX.AI — Web Assistant

FLX.AI is a Flask-based AI assistant with a Groq-powered conversation backend, a Windows Companion integration, browser voice input, and web research with clickable sources.

## Core features

- AI Mode for general questions, explanations, coding help, and conversation.
- Local Mode for interpreting supported Windows Companion commands.
- Conversation context retained in a browser-scoped SQLite history (up to 12 messages, with a 24-hour expiry).
- Web research for current or changing information using Tavily Search.
- Groq summarizes retrieved results; the interface displays an expandable **Sources** section with links to the original pages.
- Weather questions in AI Mode are routed through web search.
- Existing local search commands continue to open a browser search through the Windows Companion.
- Browser voice input and Edge TTS speech output.

## Required Render environment variables

Add these in **Render → FLX.AI Web Service → Environment**:

| Variable | Purpose |
| --- | --- |
| `GROQ_API_KEY` | Required for AI conversation and research summaries |
| `TAVILY_API_KEY` | Required for web search, current information, and weather research |
| `GROQ_MODEL` | Optional model override; leave unset to use automatic model discovery |

Get API keys from the provider dashboards:

- Groq: https://console.groq.com/keys
- Tavily: https://app.tavily.com/

Keep both API keys private. Store them only as Render environment variables; never place them in source code, HTML, screenshots, or public messages.

If `TAVILY_API_KEY` is missing or search fails, FLX.AI displays a clear search-configuration or service error. General AI answers continue to use Groq. If `GROQ_API_KEY` is missing, AI answers and research summaries cannot be generated.

## Web research behaviour

1. Groq determines whether the user's request needs current web information.
2. FLX.AI sends a focused query to Tavily.
3. Up to five HTTPS source records are passed to Groq as research context.
4. Groq writes a concise answer based on those results.
5. The website displays **Sources (N)** below the answer. Clicking it expands the list; each source opens in a new browser tab.

Stable knowledge questions should be answered directly without web search. Follow-up questions use the saved conversation history when Groq builds the search query.

## Run locally

Python 3.10+ is recommended.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Set `GROQ_API_KEY` and `TAVILY_API_KEY` in your local environment, then run:

```powershell
python app.py
```

Open http://127.0.0.1:5000.

## Deploy on Render

- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn app:app`
- Keep the existing Render service and URL.
- After pushing a commit, allow auto-deploy to run or choose **Manual Deploy → Deploy latest commit**.

## Project structure

```text
flx-ai-demo/
├── app.py
├── requirements.txt
├── render.yaml
├── README.md
└── templates/
    └── index.html
```

The Windows Companion remains a separate application and repository. This web repository does not replace or rebuild the companion.
