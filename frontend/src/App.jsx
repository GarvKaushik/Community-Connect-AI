import { useEffect, useRef, useState } from "react";
import { Room, RoomEvent, Track } from "livekit-client";

const TEXT = {
  en: {
    intro: "Talk to find education, health, money, job and community support programs.",
    start: "🎤 Start talking",
    connecting: "Connecting…",
    connected: "Connected",
    status: { listening: "Listening…", thinking: "Thinking…", speaking: "Speaking…", initializing: "Starting…" },
    mute: "Mute mic",
    unmute: "Unmute mic",
    end: "End",
    hintIdle: 'Try: "I need help finding educational support for my younger brother."',
    hintConnected: "Say hello, or type below.",
    placeholder: "Type a message",
    send: "Send",
    saved: (id) => `Your request #${id} was saved. A volunteer will call you back.`,
    programsFound: "Programs found",
    noMatch: "No verified program matched. You can ask to talk to a volunteer.",
    eligible: "Who may be eligible",
    documents: "Documents",
    apply: "How to apply",
    source: "Source",
    checked: "checked",
    disclaimer: "Eligibility is decided by the program office. Please confirm details on the official website.",
  },
  hi: {
    intro: "बात करें और पढ़ाई, स्वास्थ्य, पैसे, रोज़गार और सामुदायिक सहायता योजनाओं के बारे में जानें।",
    start: "🎤 बात शुरू करें",
    connecting: "जोड़ा जा रहा है…",
    connected: "जुड़ गए",
    status: { listening: "सुन रहा है…", thinking: "सोच रहा है…", speaking: "बोल रहा है…", initializing: "शुरू हो रहा है…" },
    mute: "माइक बंद करें",
    unmute: "माइक चालू करें",
    end: "बंद करें",
    hintIdle: 'जैसे: "मुझे अपने छोटे भाई की पढ़ाई के लिए मदद चाहिए।"',
    hintConnected: "नमस्ते कहें, या नीचे लिखें।",
    placeholder: "संदेश लिखें",
    send: "भेजें",
    saved: (id) => `आपका अनुरोध #${id} सेव हो गया है। एक स्वयंसेवक आपको कॉल करेगा।`,
    programsFound: "मिली योजनाएँ",
    noMatch: "कोई सत्यापित योजना नहीं मिली। आप स्वयंसेवक से बात करने के लिए कह सकते हैं।",
    eligible: "कौन पात्र हो सकता है",
    documents: "दस्तावेज़",
    apply: "आवेदन कैसे करें",
    source: "स्रोत",
    checked: "जाँचा गया",
    disclaimer: "पात्रता का फ़ैसला योजना कार्यालय करता है। कृपया आधिकारिक वेबसाइट पर जानकारी की पुष्टि करें।",
  },
};

export default function App() {
  const roomRef = useRef(null);
  const audioRef = useRef(null);
  const logRef = useRef(null);
  const [language, setLanguage] = useState("en");
  const [phase, setPhase] = useState("idle"); // idle | connecting | connected
  const [error, setError] = useState("");
  const [agentStatus, setAgentStatus] = useState("");
  const [muted, setMuted] = useState(false);
  const [messages, setMessages] = useState([]);
  const [programs, setPrograms] = useState(null);
  const [helpRequest, setHelpRequest] = useState(null);
  const [draft, setDraft] = useState("");
  const t = TEXT[language];

  useEffect(() => () => roomRef.current?.disconnect(), []);
  useEffect(() => {
    logRef.current?.scrollTo(0, logRef.current.scrollHeight);
  }, [messages]);

  // LiveKit can send the same transcript segment more than once (an interim copy, then the
  // final one), so messages are keyed by segment id and updated in place.
  const upsertMessage = (id, from, text) => {
    if (!text.trim()) return;
    setMessages((current) => {
      const index = current.findIndex((message) => message.id === id);
      if (index === -1) return [...current, { id, from, text: text.trim() }];
      const next = [...current];
      next[index] = { ...next[index], text: text.trim() };
      return next;
    });
  };

  async function start() {
    setError("");
    setPhase("connecting");
    setMessages([]);
    setPrograms(null);
    setHelpRequest(null);
    try {
      const response = await fetch("/api/token", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ language }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || `Server error ${response.status}`);
      }
      const { url, token } = await response.json();

      const room = new Room();
      roomRef.current = room;

      room.on(RoomEvent.TrackSubscribed, (track) => {
        if (track.kind === Track.Kind.Audio) audioRef.current?.append(track.attach());
      });
      room.on(RoomEvent.ParticipantAttributesChanged, (changed) => {
        if (changed["lk.agent.state"]) setAgentStatus(changed["lk.agent.state"]);
      });
      room.on(RoomEvent.Disconnected, () => {
        setPhase("idle");
        setAgentStatus("");
      });

      room.registerTextStreamHandler("lk.transcription", async (reader, participant) => {
        const id = reader.info.attributes?.["lk.segment_id"] || reader.info.id;
        const from = participant.identity === room.localParticipant.identity ? "you" : "assistant";
        upsertMessage(id, from, await reader.readAll());
      });
      room.registerTextStreamHandler("programs", async (reader) => {
        setPrograms(JSON.parse(await reader.readAll()));
      });
      room.registerTextStreamHandler("help_request", async (reader) => {
        setHelpRequest(JSON.parse(await reader.readAll()));
      });

      await room.connect(url, token);
      await room.localParticipant.setMicrophoneEnabled(true);
      setMuted(false);
      setPhase("connected");
    } catch (err) {
      roomRef.current?.disconnect();
      setError(err.message || "Could not connect.");
      setPhase("idle");
    }
  }

  function stop() {
    roomRef.current?.disconnect();
  }

  async function toggleMute() {
    const room = roomRef.current;
    if (!room) return;
    await room.localParticipant.setMicrophoneEnabled(muted);
    setMuted(!muted);
  }

  async function sendText(event) {
    event.preventDefault();
    const text = draft.trim();
    if (!text || !roomRef.current) return;
    setDraft("");
    upsertMessage(`typed-${Date.now()}`, "you", text);
    await roomRef.current.localParticipant.sendText(text, { topic: "lk.chat" });
  }

  return (
    <div className="page">
      <header>
        <h1>CommunityConnect AI</h1>
        <p>{t.intro}</p>
      </header>

      <section className="language" aria-label="Language">
        <button
          className={language === "en" ? "selected" : ""}
          onClick={() => setLanguage("en")}
          disabled={phase !== "idle"}
        >
          English
        </button>
        <button
          className={language === "hi" ? "selected" : ""}
          onClick={() => setLanguage("hi")}
          disabled={phase !== "idle"}
        >
          हिंदी
        </button>
      </section>

      <section className="controls">
        {phase === "connected" ? (
          <>
            <span className="status">{t.status[agentStatus] || t.connected}</span>
            <button onClick={toggleMute}>{muted ? t.unmute : t.mute}</button>
            <button className="danger" onClick={stop}>{t.end}</button>
          </>
        ) : (
          <button className="primary" onClick={start} disabled={phase === "connecting"}>
            {phase === "connecting" ? t.connecting : t.start}
          </button>
        )}
      </section>
      {error && <p className="error">{error}</p>}
      <div ref={audioRef} hidden />

      <section className="log" ref={logRef}>
        {messages.length === 0 && (
          <p className="hint">{phase === "connected" ? t.hintConnected : t.hintIdle}</p>
        )}
        {messages.map((message) => (
          <div key={message.id} className={`bubble ${message.from}`}>
            {message.text}
          </div>
        ))}
      </section>

      {phase === "connected" && (
        <form className="chat" onSubmit={sendText}>
          <input
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder={t.placeholder}
          />
          <button type="submit">{t.send}</button>
        </form>
      )}

      {helpRequest && <section className="notice">{t.saved(helpRequest.id)}</section>}

      {programs && (
        <section className="programs">
          <h2>{t.programsFound}</h2>
          {programs.length === 0 && <p>{t.noMatch}</p>}
          {programs.map((program) => (
            <article key={program.id}>
              <h3>{program.name}</h3>
              <p className="org">{program.organization}</p>
              <p>{program.benefits || program.description}</p>
              {program.eligibility && (
                <p><strong>{t.eligible}:</strong> {program.eligibility}</p>
              )}
              {program.documents?.length > 0 && (
                <p><strong>{t.documents}:</strong> {program.documents.join(", ")}</p>
              )}
              {program.how_to_apply && (
                <p><strong>{t.apply}:</strong> {program.how_to_apply}</p>
              )}
              <p className="source">
                {t.source}: <a href={program.source_url} target="_blank" rel="noreferrer">{program.source_url}</a>
                {program.last_checked && ` · ${t.checked} ${program.last_checked}`}
              </p>
            </article>
          ))}
          <p className="disclaimer">{t.disclaimer}</p>
        </section>
      )}
    </div>
  );
}
