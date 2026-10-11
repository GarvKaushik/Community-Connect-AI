import asyncio
import json
import logging
import os
import re

from dotenv import load_dotenv

from livekit import agents, rtc
from livekit.agents import Agent, AgentSession, RunContext, function_tool, metrics
from livekit.plugins import openai, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel
from faster_whisper import WhisperModel

import requests_store
from local_speech import FasterWhisperSTT, PiperTTS, load_piper_voices
from notifications import notify_help_request
from rag import CATEGORIES, Embedder, ProgramIndex

load_dotenv()

logger = logging.getLogger("communityconnect")

LANGUAGE_RULES = {
    "en": "Always reply in English.",
    "hi": "Always reply in Hindi, in Devanagari script, even after English tool results. "
    "A Hindi voice reads your reply, and it mispronounces English letters, so write every "
    "English word, scheme name and abbreviation in Devanagari as it is pronounced "
    "(PM-KISAN -> पीएम किसान, Ayushman Bharat -> आयुष्मान भारत, NMMSS -> एनएमएमएसएस), "
    "and write amounts with the word रुपये, not ₹ or Rs. Example of one question per reply: "
    '"मुझे अपने छोटे भाई की पढ़ाई के लिए मदद चाहिए।" -> '
    '"मैं मदद कर सकता हूँ। क्या वह अभी स्कूल में है या कॉलेज में?"',
}
GREETINGS = {
    "en": "Greet the user briefly in English and ask what help they are looking for.",
    "hi": "Greet the user briefly in Hindi and ask what help they are looking for.",
}
# Spoken as soon as a search starts, so the caller isn't left in silence while the search
# and the second model call run (about 2 seconds).
SEARCH_FILLERS = {
    "en": "One moment, let me check.",
    "hi": "एक पल रुकिए, मैं जानकारी देखता हूँ।",
}


def _first_sentences(text: str, count: int = 2) -> str:
    return " ".join(re.split(r"(?<=[.!?])\s+", text.strip())[:count])


# Some providers don't enforce allowed values in tool arguments, so the model may send
# "scholarship" as a category or "class 8" as a level. Clean these up rather than fail.
def _clean_category(value: str | None) -> str | None:
    category = (value or "").strip().lower().replace(" ", "_")
    return category if category in CATEGORIES else None


def _clean_level(value: str | None) -> str | None:
    level = (value or "").strip().lower()
    if re.search(r"college|graduat|degree|universit|diploma|b\.?tech|\bb\.?a\b|\bb\.?sc\b", level):
        return "college"
    if re.search(r"school|class|grade|standard|matric|\d", level):
        return "school"
    return None

INSTRUCTIONS = """\
You are CommunityConnect, a voice assistant helping people in India find government support
programs. You are not an official, social worker, doctor or lawyer; give no medical or legal advice.
Warm, simple, max 30 words, one question per reply. Spoken aloud: no lists, markdown, links
or brackets. {language_rule}

1 Search first. If the message says what help is needed, call search_programs right away
  with what you know. Do not first ask for age, school, income, location or existing cards.
  Ask one question only if the need itself is unclear (such as just "a loan" or "money" with
  no purpose), or for education when you don't know if it is school or college. Never ask
  income, caste or religion.
  "I need educational support for my younger brother." -> "I can help. Is he currently in school or college?"
  "My son is in class 8 at a government school, we earn 2 lakh" -> search now.
  "My father needs an operation and we are poor" -> search now.
2 You can ask a follow-up after showing results, if it would change which ones fit.
3 Describe one or two results that fit, a sentence each: what it gives, why it may fit. Say
  "may be eligible"; never say they qualify or are eligible. If a result's rules clearly exclude them (age, income,
  school type, land), say so briefly instead of offering it. Then offer more details or help.
4 Mention only programs and facts from the latest search result. Never invent schemes,
  amounts, documents or steps. Full details and official links are on the user's screen.
5 A result fits only if it pays for or provides the exact thing they asked for. Being on a
  similar topic is not enough: a scheme for a different purpose, stage of life or kind of
  study does not fit. On NO_VERIFIED_MATCH, or when no result fits, offer none and say:
  "I couldn't find a verified program matching your situation. I can connect you with a
  volunteer who may be able to help."
6 For a volunteer: ask permission to share their details unless they already agreed, get a
  phone number (name optional), read it back, and call request_human_help after they
  confirm. It is saved only when that tool says so; never claim it before.

Only when someone is in danger now, or mentions abuse, violence, self-harm or a child at
risk: first give both 112 and the matching helpline. If they could also use ongoing help
such as shelter, legal aid or care, search for it and mention it in one sentence. Then
offer a volunteer.
Self-harm or not wanting to live: Tele-MANAS 14416. A woman facing violence: 181.
A child in danger, child labour or child marriage: Childline 1098.
Asking which medicine to take, what a symptom means, or what to do in a legal dispute is
not an emergency: say you can't advise, suggest a doctor or government health centre, or a
lawyer, and do not mention 112. But help paying for treatment or free hospital care,
including for a sick baby or child, is a program need, not a crisis: search for it.\
"""


class Assistant(Agent):
    def __init__(self, index: ProgramIndex, room: rtc.Room, language: str) -> None:
        super().__init__(instructions=INSTRUCTIONS.format(language_rule=LANGUAGE_RULES[language]))
        self._index = index
        self._room = room
        self._found: list[dict] = []
        self._request_id: int | None = None
        self._turn = 0
        self._spoken_digits: list[tuple[int, str]] = []  # (turn, digits in an agent reply)
        self.language = language

    async def on_enter(self) -> None:
        # Fires for spoken and typed messages alike, unlike on_user_turn_completed.
        self.session.on("conversation_item_added", self._on_item_added)

    def _on_item_added(self, event) -> None:
        role = getattr(event.item, "role", None)
        if role not in ("user", "assistant"):
            return
        text = event.item.text_content or ""
        if role == "assistant":
            self._spoken_digits.append((self._turn, re.sub(r"\D", "", text)))
        else:
            self._turn += 1

    def _number_was_read_back(self, digits: str) -> bool:
        """True if an agent reply in an earlier turn contained the number, so the caller
        has heard it and answered since."""
        return any(turn < self._turn and digits in spoken for turn, spoken in self._spoken_digits)

    def _reply_language_note(self) -> str:
        # Repeated in tool results because the model tends to follow their English otherwise.
        return "Reply in Hindi, in Devanagari script." if self.language == "hi" else "Reply in English."

    async def _publish(self, topic: str, payload: object) -> None:
        """Send data to the web page, e.g. the programs found, so it can show sources."""
        try:
            await self._room.local_participant.send_text(json.dumps(payload), topic=topic)
        except Exception:
            logger.debug("could not publish %s to the room", topic, exc_info=True)

    @function_tool
    async def search_programs(
        self,
        context: RunContext,
        need: str,
        category: str | None = None,
        location: str | None = None,
        age: int | None = None,
        education_level: str | None = None,
    ) -> str:
        """Search verified programs.

        Args:
            need: The need in English, e.g. "school scholarship for a 12 year old".
            category: One of education, healthcare, financial_assistance, employment, disability,
                women_child_welfare, food, agriculture, housing, insurance, pension.
            location: Indian state or city, in English.
            education_level: "school" or "college".
        """
        category = _clean_category(category)
        education_level = _clean_level(education_level)
        context.session.say(SEARCH_FILLERS[self.language], add_to_chat_ctx=False)
        # The model's category is a guess and often differs from ours (crop insurance is
        # filed under agriculture, not insurance), so it only ranks results, never hides them.
        results = await asyncio.to_thread(
            self._index.search, need, location=location, age=age, level=education_level,
            prefer_category=category,
        )
        logger.info(
            "rag search need=%r category=%s location=%s age=%s level=%s scores=%s",
            need, category, location, age, education_level,
            {program["id"]: program["score"] for program in results},
        )
        self._found = results
        await self._publish("programs", results)
        if not results:
            return "NO_VERIFIED_MATCH. " + self._reply_language_note()
        # Only what the agent needs to speak about each program, since every result stays in
        # the chat history for later turns. The full record and source link are on screen.
        return json.dumps(
            {
                "programs": [
                    {
                        "name": program["name"],
                        "benefits": _first_sentences(program["benefits"]),
                        "eligibility": _first_sentences(program["eligibility"]),
                    }
                    for program in results
                ],
                "note": "Only these programs exist. Offer only those that provide what was "
                "asked for; if none do, say nothing was found. " + self._reply_language_note(),
            },
            ensure_ascii=False,
        )

    @function_tool
    async def request_human_help(
        self,
        context: RunContext,
        summary: str,
        phone: str,
        name: str | None = None,
        category: str | None = None,
        location: str | None = None,
    ) -> str:
        """Save a volunteer callback request, after the caller confirmed their number.

        Args:
            summary: 1-2 English sentences on who needs what, with key facts. Say "the caller";
                no gender guesses, no phone number.
            category: One of the search_programs categories.
        """
        category = _clean_category(category)
        if self._request_id is not None:
            return f"Request #{self._request_id} already exists. Tell them a volunteer will call."
        try:
            digits = re.sub(r"\D", "", requests_store.validate_phone(phone))
        except ValueError as error:
            return str(error)

        # Enforce the read-back in code: the caller must have heard this exact number in an
        # earlier reply and answered since.
        if not self._number_was_read_back(digits):
            return (
                f"NOT SAVED. Only read the number back ({' '.join(digits)}) and ask if it is "
                "correct, then stop and wait for the answer. Do not say the request was sent. "
                "When they say yes, call request_human_help again to save it. "
                + self._reply_language_note()
            )

        programs = [program["name"] for program in self._found]
        try:
            request_id = await asyncio.to_thread(
                requests_store.save_request,
                name=name,
                phone=phone,
                summary=summary,
                category=category,
                location=location,
                programs=programs,
                language=self.language,
            )
        except ValueError as error:
            return str(error)

        self._request_id = request_id
        logger.info("help request saved id=%s category=%s", request_id, category)
        sent = await notify_help_request(
            request_id=request_id,
            name=name,
            phone=phone,
            category=category,
            location=location,
            summary=summary,
            programs=programs,
        )
        await self._publish("help_request", {"id": request_id, "notified": sent})
        return f"Request #{request_id} saved. Tell them a volunteer will call them back soon."


async def choose_language(ctx: agents.JobContext) -> str:
    """The web page sends the user's choice as a participant attribute. Console mode has no
    browser, so it uses AGENT_LANGUAGE instead."""
    if ctx.is_fake_job():
        language = os.getenv("AGENT_LANGUAGE", "en")
    else:
        participant = await ctx.wait_for_participant()
        language = participant.attributes.get("language", "en")
    return language if language in LANGUAGE_RULES else "en"


async def entrypoint(ctx: agents.JobContext):
    await ctx.connect()
    language = await choose_language(ctx)
    logger.info("session language=%s", language)

    session = AgentSession(
        stt=FasterWhisperSTT(ctx.proc.userdata["whisper_models"][language], language),
        llm=openai.LLM(
            model=os.getenv("LLM_MODEL", "openai/gpt-oss-120b"),
            base_url=os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1"),
            api_key=os.getenv("LLM_API_KEY") or os.getenv("GROQ_API_KEY"),
            # Hidden reasoning tokens count towards the rate limit and add latency.
            reasoning_effort=os.getenv("LLM_REASONING_EFFORT", "low"),
        ),
        tts=PiperTTS(ctx.proc.userdata["piper_voices"][language]),
        # A slightly higher threshold than the default 0.5, so steady background noise
        # (fans, speaker hiss) isn't taken as speech. A short silence (0.35 s) starts
        # transcription sooner; the turn detector below stops this cutting people off.
        vad=silero.VAD.load(activation_threshold=0.6, min_silence_duration=0.35),
        turn_handling={
            # Off by default: on laptop speakers the agent hears its own voice, which would
            # interrupt it or be answered as if the caller had said it. With interruptions
            # off, microphone audio is dropped while the agent speaks. Headphone users can set
            # ALLOW_INTERRUPTIONS=true to talk over the agent.
            "interruption": {"enabled": os.getenv("ALLOW_INTERRUPTIONS", "false").lower() == "true"},
            # A local model reads what was said and judges whether the sentence is finished
            # (English and Hindi). Finished: reply after 0.4 s. Unfinished ("my brother
            # is in class..."): wait up to 3 s for the rest instead of cutting in.
            "turn_detection": MultilingualModel(),
            "endpointing": {"min_delay": 0.4, "max_delay": 3.0},
        },
    )
    assistant = Assistant(ctx.proc.userdata["program_index"], ctx.room, language)
    # Log each turn's timings (end-of-turn delay, speech-to-text, model, voice) so slow
    # replies can be traced to the stage causing them.
    session.on("metrics_collected", lambda event: metrics.log_metrics(event.metrics))
    await session.start(room=ctx.room, agent=assistant)
    await session.generate_reply(instructions=GREETINGS[language])


# One speech-to-text model per language: a fast general model for English, and a model
# fine-tuned on Hindi for Hindi. Any faster-whisper size or Hugging Face repo works here.
WHISPER_MODELS = {
    "en": os.getenv("WHISPER_MODEL_EN", "base"),
    "hi": os.getenv("WHISPER_MODEL_HI", "collabora/faster-whisper-small-hindi"),
}


# Threads for speech-to-text. More threads help only up to a point (on a 12-thread laptop:
# 3.3 s per Hindi turn by default, 3.0 s with 6, 2.9 s with 12), and using every core starves
# the rest of the call and the machine. Default: half the cores, at most 6. Inside Docker,
# os.cpu_count() reports the host's cores, so docker-compose sets STT_THREADS to the
# container's CPU limit.
STT_THREADS = int(os.getenv("STT_THREADS") or max(1, min(6, (os.cpu_count() or 4) // 2)))


def load_whisper(name: str) -> WhisperModel:
    return WhisperModel(name, device="cpu", compute_type="int8", download_root="models/whisper",
                        cpu_threads=STT_THREADS)


def prewarm(proc: agents.JobProcess) -> None:
    requests_store.initialize()
    proc.userdata["whisper_models"] = {language: load_whisper(name) for language, name in WHISPER_MODELS.items()}
    proc.userdata["piper_voices"] = load_piper_voices()
    proc.userdata["program_index"] = ProgramIndex(Embedder())


if __name__ == "__main__":
    agents.cli.run_app(
        agents.WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
            # Loading both Whisper models, both voices and the index takes ~20-60 s on CPU,
            # longer in a CPU-capped container, so allow plenty of time.
            initialize_process_timeout=float(os.getenv("AGENT_INIT_TIMEOUT", "120")),
            # Each ready process loads every model (~1.2 GB). LiveKit keeps 4 ready in
            # production by default; one is enough for a demo or a small server.
            num_idle_processes=int(os.getenv("AGENT_IDLE_PROCESSES", "1")),
            job_memory_warn_mb=2000,
        )
    )
