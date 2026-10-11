# CommunityConnect AI

A voice assistant that helps people in India find government support programs for
education, healthcare, financial help, jobs, disability, women and child welfare, and food.
People talk to it naturally in English or Hindi. It asks a few simple questions, searches
a knowledge base of real programs, explains the matches in plain language, and, if the
person wants, saves a request so a human volunteer can call them back. Volunteers are
alerted on Telegram.

The assistant does not replace social workers, officials, doctors or lawyers. It never
promises eligibility: it says a person *may* be eligible and points to the official source.

This is an MVP for demos.

## How it works

```text
Browser (React)  --mic audio / typed text-->  LiveKit room
                                                  |
                                     Silero VAD -> turn detection
                                                  |
                                     faster-whisper STT (local, in the chosen language)
                                                  |
                                     LLM (any OpenAI-compatible API, Groq by default)
                                       |  tool: search_programs  -> RAG over knowledge_base/programs.json
                                       |  tool: request_human_help -> SQLite + Telegram
                                                  |
                                     Piper TTS (local, English or Hindi voice)
                                                  |
Browser  <--audio, live transcript, program cards with sources--  LiveKit room
```

| Layer | Choice |
| --- | --- |
| Voice transport | LiveKit Agents 1.8.1 |
| Speech to text | faster-whisper `small` (int8, CPU) |
| LLM | Groq `openai/gpt-oss-120b` through the OpenAI-compatible API |
| RAG | Multilingual MiniLM embeddings (ONNX), in-memory cosine search with metadata filters |
| Text to speech | Piper `en_US-lessac-medium` and `hi_IN-pratham-medium` |
| Storage | SQLite |
| Notifications | Telegram Bot API |
| Backend | FastAPI (issues LiveKit tokens, serves the built frontend) |
| Frontend | React + Vite |

The user picks English or Hindi on the page before starting. The choice travels to the agent
as a LiveKit participant attribute and fixes the language for speech recognition, the voice,
and the replies. A fixed language is more reliable than detecting it on every turn.

The embedding model maps Hindi and English into one vector space, so a Hindi question
matches English program text without translating it first. With a few dozen programs, a
numpy search in memory is simpler than running a vector database. Swap in Qdrant only if
the knowledge base grows to many thousands of documents.

## Layout

```text
agent.py                    LiveKit voice agent: prompt, tools, session wiring
local_speech.py             Whisper STT and Piper TTS plugins (English + Hindi)
rag.py                      Embeddings and program search
requests_store.py           SQLite storage and validation for help requests
notifications.py            Telegram alerts to volunteers
server.py                   FastAPI: LiveKit token endpoint, serves frontend/dist
knowledge_base/programs.json  The program knowledge base
frontend/                   React app
```

## Setup

You need Python 3.12+ (developed on 3.14), Node.js 18+, a free
[LiveKit Cloud](https://cloud.livekit.io) project and a [Groq](https://console.groq.com)
API key.

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

cd frontend
npm install
npm run build
cd ..
```

Copy `.env.example` to `.env` and fill in the LiveKit URL, key and secret, and
`LLM_API_KEY` (an existing `GROQ_API_KEY` also works). Telegram is optional.

Models download themselves on the first run into `models/`: the Whisper model, both Piper
voices and the embedding model, roughly 1 GB in total.

### Telegram (optional)

1. Message [@BotFather](https://t.me/BotFather), send `/newbot`, and copy the token into
   `TELEGRAM_BOT_TOKEN`.
2. Add the bot to the volunteers' group (or message it directly), send it any message,
   then open `https://api.telegram.org/bot<token>/getUpdates` and copy `chat.id` into
   `TELEGRAM_CHAT_ID`.

Without these the agent still saves requests and logs one warning that notifications are
disabled.

## Running

Two terminals, both from the project root with the virtual environment active:

```powershell
python agent.py dev
```

```powershell
uvicorn server:app --port 8000
```

Open http://localhost:8000, choose English or हिंदी, and press **Start talking**. The worker joins each new room
automatically.

For frontend development, run `npm run dev` in `frontend/` and open http://localhost:5173
instead; it proxies `/api` to port 8000.

You can also talk to the agent in the terminal, without the browser:

```powershell
python agent.py console
```

The console has no language picker; set `AGENT_LANGUAGE=hi` in `.env` for Hindi.

## Demo

1. Choose English and press **Start talking**. The assistant greets you.
2. Say "I need help finding educational support for my younger brother."
3. It asks whether he is in school or college, then for his class or age and your state.
4. It searches the knowledge base and describes two or three programs. Cards with the
   official source link appear under the conversation.
5. Say you would like a volunteer to help you apply. It asks permission, takes your phone
   number, reads it back and saves the request.
6. The page shows the request number, and the volunteer group receives the Telegram alert.

Try the same with हिंदी selected, for example "मुझे अपने छोटे भाई की पढ़ाई के लिए मदद चाहिए।"
You can also type messages instead of speaking.

Saved requests are in `data/communityconnect.db`, table `help_requests`.

## Knowledge base

`knowledge_base/programs.json` holds real central-government schemes. The details were
taken from the official source listed on each program (`source_url`) on the date in
`last_checked`. Amounts, rules and state-level availability change, so check each entry
against its source before relying on it, and update `last_checked` when you do.

To add a program, append an object with the same fields and restart the agent. The index
is rebuilt from the file at startup. Only add information from an official source, and
always include `source_url`.

Education programs can also have `"level": "school"` or `"college"`, which the search uses
as a filter. `audience` (for example `farmer` or `household`) is descriptive only.

Categories: `education`, `healthcare`, `financial_assistance`, `employment`, `disability`,
`women_child_welfare`, `food`, `agriculture`, `housing`, `insurance`, `pension`. A new
category must also be added to `Category` in `agent.py` so the agent can search it.

Search applies the `category`, `location`, age and level filters first, then ranks by
similarity.
Matches below `RAG_MIN_SCORE` (default 0.3) are dropped, so when nothing fits, the
assistant says it couldn't find a verified program and offers a volunteer instead of
guessing.

## Safety

- The assistant only describes programs returned by the search, and the prompt forbids
  inventing programs, amounts, documents or steps.
- It says "may be eligible", never "is eligible".
- If someone mentions danger, abuse or self-harm, it gives the national helplines (112,
  181, 1098, Tele-MANAS 14416) before anything else and offers a volunteer.
- It asks permission before saving contact details and stores only a phone number, an
  optional name, and a short summary of the need.
- The Telegram alert includes the phone number so the volunteer can call back. Use a
  private volunteer group.

## Known limitations

- Speech-to-text takes about 3 seconds per turn on a laptop CPU with `small`.
  `WHISPER_MODEL=base` is about three times as fast but much weaker at Hindi.
- The language is fixed for a conversation. To switch, press **End** and start again.
- Speech-to-text and text-to-speech are not streaming, so replies start only after the
  full sentence is transcribed and synthesized.
- Groq's free tier allows about 8,000 tokens per minute, which a long conversation can reach.
- There is no volunteer dashboard. Requests are followed up from Telegram and the SQLite file.
