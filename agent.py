import asyncio
import json
import logging
import os
import re

from dotenv import load_dotenv

from livekit import agents, rtc
from livekit.agents import Agent, AgentSession, RunContext, function_tool
from livekit.plugins import openai, silero
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
    "Keep scheme names as they are. Example of one question per reply: "
    '"मुझे अपने छोटे भाई की पढ़ाई के लिए मदद चाहिए।" -> '
    '"मैं मदद कर सकता हूँ। क्या वह अभी स्कूल में है या कॉलेज में?"',
}
GREETINGS = {
    "en": "Greet the user briefly in English and ask what help they are looking for.",
    "hi": "Greet the user briefly in Hindi and ask what help they are looking for.",
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
5 On NO_VERIFIED_MATCH, or when no result actually fits their need, say: "I couldn't find
  a verified program matching your situation. I can connect you with a volunteer who may be
  able to help."
6 For a volunteer: ask permission to share their details unless they already agreed, get a
  phone number (name optional), read it back, and call request_human_help after they
  confirm. It is saved only when that tool says so; never claim it before.

Only when someone is in danger now, or mentions abuse, violence, self-harm or a child at
risk: first give both 112 and the matching helpline, then offer a volunteer.
Self-harm or not wanting to live: Tele-MANAS 14416. A woman facing violence: 181.
A child in danger, child labour or child marriage: Childline 1098.
Asking which medicine to take, what a symptom means, or what to do in a legal dispute is
not an emergency: say you can't advise, suggest a doctor or government health centre, or a
lawyer, and do not mention 112. But help paying for treatment or free hospital care is a
program need: search for it.\
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
        results = await asyncio.to_thread(
            self._index.search, need, category, location, age, education_level
        )
        if not results and category:
            # The model's category can differ from ours (e.g. crop insurance is filed under
            # agriculture, not insurance), so retry before telling the user nothing exists.
            results = await asyncio.to_thread(
                self._index.search, need, None, location, age, education_level
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
                "note": "Only these programs exist. " + self._reply_language_note(),
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
        stt=FasterWhisperSTT(ctx.proc.userdata["whisper_model"], language),
        llm=openai.LLM(
            model=os.getenv("LLM_MODEL", "openai/gpt-oss-120b"),
            base_url=os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1"),
            api_key=os.getenv("LLM_API_KEY") or os.getenv("GROQ_API_KEY"),
            # Hidden reasoning tokens count towards the rate limit and add latency.
            reasoning_effort=os.getenv("LLM_REASONING_EFFORT", "low"),
        ),
        tts=PiperTTS(ctx.proc.userdata["piper_voices"][language]),
        vad=silero.VAD.load(),
        turn_handling={
            "interruption": {"enabled": True},
            "endpointing": {"min_delay": 1.0},
        },
    )
    assistant = Assistant(ctx.proc.userdata["program_index"], ctx.room, language)
    await session.start(room=ctx.room, agent=assistant)
    await session.generate_reply(instructions=GREETINGS[language])


def prewarm(proc: agents.JobProcess) -> None:
    requests_store.initialize()
    proc.userdata["whisper_model"] = WhisperModel(
        os.getenv("WHISPER_MODEL", "small"),
        device="cpu",
        compute_type="int8",
        download_root="models/whisper",
    )
    proc.userdata["piper_voices"] = load_piper_voices()
    proc.userdata["program_index"] = ProgramIndex(Embedder())


if __name__ == "__main__":
    agents.cli.run_app(
        agents.WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
            # Loading Whisper, both voices and the index takes ~15 s on CPU.
            initialize_process_timeout=60,
        )
    )
