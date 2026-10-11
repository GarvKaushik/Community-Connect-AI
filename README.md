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
evals/golden_dataset.jsonl  Test cases for retrieval and LLM evaluation
evals/run_eval.py           Scores the assistant against the test cases
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
3. It asks whether he is in school or college, and his class or age if needed. It asks only
   what changes the search, so a detailed first message can go straight to results.
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
category must also be added to `CATEGORIES` in `rag.py` and to the `search_programs`
docstring in `agent.py` so the agent can search it.

`keywords` lists everyday names and Hindi or Hinglish terms for a scheme (for example
"MGNREGA", "रोज़गार", "septic tank"). They are search aids only and must not state rules
or amounts.

Search applies the `category`, `location`, age and level filters first, then ranks by
similarity, embedding each field and each keyword as its own short passage. Matches below
`RAG_MIN_SCORE` (default 0.28), or more than `RAG_RELATIVE_MARGIN` (default 0.12) below the
best match, are dropped. Scores alone cannot tell "relevant" from "same topic" (see
Improvements), so the agent is also told to treat results that don't fit the person as no
match, and to say when a scheme's rules clearly exclude them.

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

## Improvements

The assistant is measured against a golden dataset, and changes are kept only when the
numbers improve.

### Golden dataset

`evals/golden_dataset.jsonl` has 144 test cases (96 English, 48 Hindi) and covers all 43
schemes.

| Case type | Cases | Tests |
| --- | --- | --- |
| `single_match`, `multi_match` | 82 | Retrieval, faithfulness, tool arguments |
| `ineligible_lookalike` | 10 | Says when a scheme's rules exclude the person |
| `no_match` | 12 | Says it found nothing instead of offering a weak match |
| `ask_followup`, `multi_turn` | 16 | Asks one question at a time, searches when ready |
| `crisis` | 10 | Gives helplines first |
| `out_of_scope` | 6 | No medical or legal advice |
| `human_handoff` | 8 | Consent, number read-back, saving the request |

Each case has the query, any earlier turns (`history`), the relevant scheme IDs with
graded relevance (2 = best answer, 1 = also relevant), a reference answer built only from
`programs.json`, the expected intent, tool and tool arguments, and a safety expectation.
`input_style` marks romanized Hindi and speech-recognition errors. Location is left out of
filters and arguments for now, since nearly every scheme is All India.

`split` holds out about a third of the cases as `test`. Tune prompts and settings on `dev`
and check `test` only occasionally, so the scores are not tuned to the test set.

### Running the evals

```powershell
python evals/run_eval.py                  # retrieval scores on the dev cases (no LLM tokens)
python evals/run_eval.py --failures       # also list the cases that missed
python evals/run_eval.py --llm --limit 10 # run the real agent on 10 cases (uses Groq tokens)
```

The retrieval eval prints each metric with a plain explanation, plus breakdowns by case
type, language and input style. The LLM eval plays each case through the real agent and
checks five things: the right tool, the right arguments, the reply language, grounding
(only schemes and amounts from the search), and the case's safety rule. It saves results
to `evals/results/` as it goes, so when Groq's limit is reached you can run the same command
later and it continues. The full set needs roughly 360k tokens, about two days of Groq's
free tier. `--split test`, `--type crisis` and `--fresh` are also available; see the top of
`evals/run_eval.py`.

The LLM eval uses the same `LLM_MODEL`, `LLM_BASE_URL` and `LLM_API_KEY` settings as the
agent, so it can run on another provider when Groq's limit runs out. Each model gets its
own results file, so runs never mix.

| Provider | `LLM_BASE_URL` | `LLM_MODEL` | Notes |
| --- | --- | --- | --- |
| Groq | `https://api.groq.com/openai/v1` | `openai/gpt-oss-120b` | Production model; free tier ~200k tokens a day |
| Ollama Cloud | `https://ollama.com/v1` | `gpt-oss:120b` | Same model; key from ollama.com/settings/keys |
| Local Ollama | `http://127.0.0.1:11434/v1` | e.g. `qwen3.5:4b` | Offline and free; set `LLM_API_KEY=ollama`, `LLM_TIMEOUT=300`, and use `--pause 0` |

Small local models are slow on a laptop CPU (about two minutes per reply) and weaker than
the production model, especially in Hindi. Use them to catch broken behaviour, and report
scores from `gpt-oss-120b`.

### Retrieval scores

Searching the way the agent does (age and level filters, category only used to rank):

| Split | Recall@3 | Precision@3 | Top-1 | MRR | nDCG@3 | No-match given results |
| --- | --- | --- | --- | --- | --- | --- |
| Dev (75 cases) | 0.896 | 0.530 | 0.821 | 0.881 | 0.855 | 8 / 8 |
| Test (36 cases) | 0.891 | 0.573 | 0.844 | 0.901 | 0.872 | 4 / 4 |

English scores higher than Hindi (dev MRR 0.922 vs 0.795). The relative cutoff was chosen on
the whole dataset before the split existed, so these numbers are slightly optimistic.

### Evaluation results (October 2026)

Final scores on the 45 held-out test cases, using the production model (Groq
`gpt-oss-120b`). These are from before the prompt fixes described below.

| Retrieval | Score |
| --- | --- |
| Recall@3 | 0.906 |
| MRR | 0.901 |
| No-match questions that still got results | 4 / 4 |

| Agent behaviour | Score |
| --- | --- |
| Grounded (no invented schemes or amounts) | 100% |
| Replied in the right language | 100% |
| Followed the safety rule | 91% |
| Right tool (searched, asked or saved correctly) | 62% |
| Passed every check on a single reply | 40% |
| Asked a question instead of searching | 38% |
| Serious failures (harmful or misleading) | 2% (1 of 45) |

The full 144-case set on Ollama Cloud (`gpt-oss:120b`) gave similar results: 38% passed
every check, 99% grounded, 6% serious failures.

What the scores show:
- **Answers are reliable.** The agent never invented a scheme or amount on the test set
  and always kept the chosen language.
- **It asks too many questions.** In about 4 out of 10 conversations it asked something it
  didn't need (an age, a school, an existing health card) before searching.
- **112 was over-used.** Medicine and legal questions were told to call 112, and crisis
  replies rarely named the specific helpline (181, 1098 or Tele-MANAS 14416).

The checks score one reply at a time, so an unnecessary question counts as a full failure
even though the person can simply answer it.

**After the fixes** (Ollama Cloud `gpt-oss:120b`, same cases before and after):

| | Dev before | Dev after | Test before | Test after |
| --- | --- | --- | --- | --- |
| Passed every check | 40% | 81% | 33% | 73% |
| Right tool | 59% | 95% | 62% | 96% |
| Followed the safety rule | 85% | 94% | 80% | 96% |
| Grounded | 100% | 99% | 98% | 100% |
| Replied in the right language | 100% | 100% | 100% | 100% |
| Asked a question instead of searching | 37 | 3 | 15 | 2 |
| Said "nothing found" when a scheme exists | 2 | 3 | 3 | 0 |
| Serious failures | 5 | 3 | 3 | 2 |

Dev has 99 cases and test 45. The prompt was tuned on dev only; test was used just to check.
On Groq the test set gave 40% before and 69% after an earlier round of fixes, so the two
providers score similarly.

The remaining serious failures are all one pattern: for a question with no right answer
(an MBA abroad, wedding costs, a tractor subsidy, an electricity bill) the agent describes
an unrelated scheme that the search returned, instead of saying nothing was found.

### Done

- **Keywords per scheme**, each embedded as its own passage. Together with the relative
  cutoff, on the original 120 cases, Precision@3 rose from 0.437 to 0.570, Precision@1 from
  0.772 to 0.823 and MRR from 0.838 to 0.884, for a small recall cost (0.918 to 0.905).
- **Relative cutoff**: results more than 0.12 below the best match are dropped.
- **Prompt rules** for results that don't fit, and for schemes whose rules exclude the
  person.
- **Dataset**: added ineligible lookalikes, romanized Hindi, speech-error and multi-turn
  cases, graded relevance, and the dev/test split.
- **Knowledge base**: vague entries rewritten with figures checked against official sources;
  non-schemes removed.
- **Search first**: the agent searches as soon as the need is clear and asks a question only
  when the need is vague (such as just "a loan") or school vs college is unknown. It no
  longer asks for the state, and doesn't ask for consent twice.
- **112 only for real danger**: medicine and legal questions are referred to a doctor or
  lawyer, and each crisis type gets its own helpline (Tele-MANAS 14416, 181, Childline 1098)
  together with 112.
- **Category as a preference**: the model's category guess now only ranks results higher
  (`RAG_CATEGORY_BONUS`, default 0.05) instead of hiding other categories. The model often
  guesses differently from ours (crop insurance is filed under agriculture), and with 20%
  wrong guesses this keeps MRR at 0.866 instead of 0.826. False "nothing found" replies on
  the test set went from 3 to 0.
- **Only matching schemes**: the agent offers a scheme only if it pays for or provides the
  exact thing asked for, and for a sick child or domestic violence it adds the relevant
  scheme after the helplines.
- **Tolerant tool arguments**: some providers ignore allowed values, sending "class 8" as a
  level or "scholarship" as a category. The agent now cleans these up instead of failing.

### Known gaps

- **No-match detection (accepted limitation).** For a question no scheme covers, the agent
  sometimes describes an unrelated scheme the search returned instead of saying nothing was
  found: 2 of 45 test cases and 3 of 99 dev cases. This is the only remaining serious
  failure pattern. Search scores can't separate these questions from real matches (0.39 to
  0.58 vs from 0.43), and a prompt rule reduced the problem but didn't remove it.
- **Reranker tested and rejected.** A multilingual cross-encoder
  (`cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`, quantized) was tried on the dev cases. Its
  scores for no-match questions overlapped with those for correct schemes, so a cutoff that
  rejected 7 of 8 no-match questions also emptied 26 of 67 correct answers. It ranked worse
  than the current search (MRR 0.828 vs 0.881, and 0.644 in Hindi) and added about 0.5 s
  per search. Larger rerankers were ruled out as too heavy for a laptop.
- **Crisis questions** retrieve poorly (Recall@3 0.43). This is acceptable because the
  helplines come from the prompt, not from search.

### Next

1. Smaller issues: the agent sometimes asks for a name before saving a volunteer request,
   and occasionally answers "nothing found" without searching (passport help, which is
   correct but skips the search).
2. If no-match needs further work: have the model mark each search result as fitting or
   not before replying. Cheap to try on the dev cases, but not guaranteed to help.
3. Human review of the dataset, with a native speaker for the Hindi cases.
4. More romanized Hindi and speech-error cases (10 so far).
5. The eval counts a different category guess as an argument failure. Since the category
   now only ranks results, this check is stricter than needed; 6 of the 12 remaining test
   failures are only this.

### Planned, needs approval (new models or data)

- A stronger multilingual embedding model (for example `multilingual-e5-base` or `bge-m3`)
  for better Hindi retrieval.
- Schemes from two or three states, so location filtering can be tested.
- Re-checking schemes whose guidelines ended on 31 March 2026 and are still running without
  a formal extension: NAMASTE, NAPS, Saksham Anganwadi and POSHAN 2.0, PM YASASVI, NMMSS
  and ADIP.

## Known limitations

- Speech-to-text takes about 3 seconds per turn on a laptop CPU with `small`.
  `WHISPER_MODEL=base` is about three times as fast but much weaker at Hindi.
- The language is fixed for a conversation. To switch, press **End** and start again.
- Speech-to-text and text-to-speech are not streaming, so replies start only after the
  full sentence is transcribed and synthesized.
- Groq's free tier allows about 8,000 tokens per minute, which a long conversation can reach.
- There is no volunteer dashboard. Requests are followed up from Telegram and the SQLite file.
