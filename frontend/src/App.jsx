import { useEffect, useRef, useState } from "react";
import { Room, RoomEvent, Track } from "livekit-client";
import About from "./About.jsx";

const routeFromHash = () => (window.location.hash === "#/about" ? "about" : "home");

// Ask the browser to remove the assistant's own voice and background noise from the
// microphone, which matters most on laptop speakers. Auto gain stays off: it boosts quiet
// moments, which turns room noise into "speech" and keeps the turn from ending.
const MIC_OPTIONS = { echoCancellation: true, noiseSuppression: true, autoGainControl: false };

const TEXT = {
  en: {
    about: "About",
    home: "Assistant",
    tagline: "Find government help for education, health, money, jobs and more — just by talking.",
    start: "Tap to start talking",
    connecting: "Connecting…",
    joining: "The assistant is joining. Please wait a few seconds…",
    ready: "You can speak now",
    readyHint: "Tell me what help you need",
    speaking: "The assistant is speaking…",
    thinking: "Finding the right schemes…",
    muted: "Your microphone is off",
    mute: "Mute",
    unmute: "Unmute",
    end: "End call",
    headphones: "🎧 Tip: headphones work best. On speakers, wait for the assistant to finish before you talk.",
    steps: [
      ["🗣️", "Tell us your need", "Speak or type in English or Hindi"],
      ["🔎", "We find schemes", "Only real government programs"],
      ["🤝", "Get a volunteer", "A person can call you back"],
    ],
    tryLabel: "Try saying",
    examples: [
      "I need help finding educational support for my younger brother.",
      "My father needs an operation and we are poor.",
      "We live in a kutcha house in our village.",
    ],
    conversation: "Conversation",
    emptyIdle: "Your conversation will appear here.",
    you: "You",
    assistant: "Assistant",
    placeholder: "Type a message…",
    placeholderWait: "Please wait for the assistant…",
    send: "Send",
    saved: (id) => `Request #${id} saved. A volunteer will call you back soon.`,
    programsFound: "Schemes that may help",
    noMatch: "No verified scheme matched. You can ask to talk to a volunteer.",
    benefits: "What you get",
    eligible: "Who may be eligible",
    documents: "Documents",
    apply: "How to apply",
    source: "Official source",
    checked: "Checked",
    disclaimer: "Eligibility is decided by the scheme office. Please confirm details on the official website.",
    emergency: "In an emergency call",
    helplines: "Women 181 · Children 1098 · Mental health 14416",
  },
  hi: {
    about: "परिचय",
    home: "सहायक",
    tagline: "बस बात करके पढ़ाई, स्वास्थ्य, पैसे, रोज़गार और अन्य सरकारी मदद पाएँ।",
    start: "बात शुरू करने के लिए दबाएँ",
    connecting: "जोड़ा जा रहा है…",
    joining: "सहायक जुड़ रहा है। कृपया कुछ सेकंड रुकें…",
    ready: "अब आप बोल सकते हैं",
    readyHint: "बताइए आपको किस मदद की ज़रूरत है",
    speaking: "सहायक बोल रहा है…",
    thinking: "सही योजनाएँ ढूँढी जा रही हैं…",
    muted: "आपका माइक बंद है",
    mute: "माइक बंद",
    unmute: "माइक चालू",
    end: "कॉल समाप्त",
    headphones: "🎧 सुझाव: हेडफ़ोन सबसे अच्छे रहते हैं। स्पीकर पर, सहायक के बोल लेने के बाद ही बोलें।",
    steps: [
      ["🗣️", "अपनी ज़रूरत बताएँ", "हिंदी या अंग्रेज़ी में बोलें या लिखें"],
      ["🔎", "हम योजनाएँ ढूँढते हैं", "केवल असली सरकारी योजनाएँ"],
      ["🤝", "स्वयंसेवक की मदद", "कोई व्यक्ति आपको कॉल कर सकता है"],
    ],
    tryLabel: "ऐसे बोलकर देखें",
    examples: [
      "मुझे अपने छोटे भाई की पढ़ाई के लिए मदद चाहिए।",
      "मेरे पिताजी का ऑपरेशन होना है और हम गरीब हैं।",
      "गाँव में हमारा कच्चा घर है।",
    ],
    conversation: "बातचीत",
    emptyIdle: "आपकी बातचीत यहाँ दिखेगी।",
    you: "आप",
    assistant: "सहायक",
    placeholder: "संदेश लिखें…",
    placeholderWait: "कृपया सहायक का इंतज़ार करें…",
    send: "भेजें",
    saved: (id) => `अनुरोध #${id} सेव हो गया। एक स्वयंसेवक जल्द ही आपको कॉल करेगा।`,
    programsFound: "योजनाएँ जो मदद कर सकती हैं",
    noMatch: "कोई सत्यापित योजना नहीं मिली। आप स्वयंसेवक से बात करने के लिए कह सकते हैं।",
    benefits: "क्या मिलेगा",
    eligible: "कौन पात्र हो सकता है",
    documents: "दस्तावेज़",
    apply: "आवेदन कैसे करें",
    source: "आधिकारिक स्रोत",
    checked: "जाँचा गया",
    disclaimer: "पात्रता का फ़ैसला योजना कार्यालय करता है। कृपया आधिकारिक वेबसाइट पर जानकारी की पुष्टि करें।",
    emergency: "आपातकाल में कॉल करें",
    helplines: "महिला 181 · बच्चे 1098 · मानसिक स्वास्थ्य 14416",
  },
};

const CATEGORIES = {
  education: ["🎓", "Education", "शिक्षा"],
  healthcare: ["🏥", "Health", "स्वास्थ्य"],
  financial_assistance: ["💰", "Money help", "आर्थिक सहायता"],
  employment: ["💼", "Jobs & skills", "रोज़गार"],
  disability: ["♿", "Disability", "दिव्यांग"],
  women_child_welfare: ["👩‍👧", "Women & children", "महिला एवं बाल"],
  food: ["🍲", "Food", "भोजन"],
  agriculture: ["🌾", "Farming", "कृषि"],
  housing: ["🏠", "Housing", "आवास"],
  insurance: ["🛡️", "Insurance", "बीमा"],
  pension: ["👵", "Pension", "पेंशन"],
};

export default function App() {
  const roomRef = useRef(null);
  const audioRef = useRef(null);
  const logRef = useRef(null);
  const [language, setLanguage] = useState("en");
  const [phase, setPhase] = useState("idle"); // idle | connecting | connected
  const [agentJoined, setAgentJoined] = useState(false);
  const [agentState, setAgentState] = useState(""); // initializing | listening | thinking | speaking
  const [error, setError] = useState("");
  const [muted, setMuted] = useState(false);
  const [messages, setMessages] = useState([]);
  const [programs, setPrograms] = useState(null);
  const [helpRequest, setHelpRequest] = useState(null);
  const [draft, setDraft] = useState("");
  const [route, setRoute] = useState(routeFromHash);
  const t = TEXT[language];

  useEffect(() => () => roomRef.current?.disconnect(), []);
  useEffect(() => {
    const onHashChange = () => {
      setRoute(routeFromHash());
      window.scrollTo(0, 0);
    };
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);
  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  // The assistant takes a few seconds to join and load. Only tell people to speak once
  // it is actually listening, so their first words aren't lost.
  const status = (() => {
    if (phase === "connecting") return { key: "connecting", text: t.connecting };
    if (phase !== "connected") return null;
    if (!agentJoined || !agentState || agentState === "initializing") return { key: "joining", text: t.joining };
    if (agentState === "speaking") return { key: "speaking", text: t.speaking };
    if (agentState === "thinking") return { key: "thinking", text: t.thinking };
    if (muted) return { key: "muted", text: t.muted };
    return { key: "ready", text: t.ready, hint: t.readyHint };
  })();
  const agentReady = phase === "connected" && agentJoined && agentState && agentState !== "initializing";

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

  const watchAgent = (participant) => {
    if (!participant.isAgent) return;
    setAgentJoined(true);
    const state = participant.attributes?.["lk.agent.state"];
    if (state) setAgentState(state);
  };

  async function start() {
    setError("");
    setPhase("connecting");
    setAgentJoined(false);
    setAgentState("");
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
      room.on(RoomEvent.ParticipantConnected, watchAgent);
      room.on(RoomEvent.ParticipantDisconnected, (participant) => {
        if (participant.isAgent) {
          setAgentJoined(false);
          setAgentState("");
        }
      });
      room.on(RoomEvent.ParticipantAttributesChanged, (changed, participant) => {
        if (participant?.isAgent) setAgentJoined(true);
        if (changed["lk.agent.state"]) setAgentState(changed["lk.agent.state"]);
      });
      room.on(RoomEvent.Disconnected, () => {
        setPhase("idle");
        setAgentJoined(false);
        setAgentState("");
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
      room.remoteParticipants.forEach(watchAgent); // in case the assistant joined first
      await room.localParticipant.setMicrophoneEnabled(true, MIC_OPTIONS);
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
    await room.localParticipant.setMicrophoneEnabled(muted, MIC_OPTIONS);
    setMuted(!muted);
  }

  async function sendText(text) {
    const message = text.trim();
    if (!message || !roomRef.current || !agentReady) return;
    upsertMessage(`typed-${Date.now()}`, "you", message);
    await roomRef.current.localParticipant.sendText(message, { topic: "lk.chat" });
  }

  function onSubmit(event) {
    event.preventDefault();
    sendText(draft);
    setDraft("");
  }

  const orbState = phase === "idle" ? "idle" : status?.key;

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="logo" aria-hidden="true">🤝</span>
          <span className="brand-name">CommunityConnect <span className="brand-ai">AI</span></span>
        </div>
        <nav className="nav">
          <a className="nav-link" href={route === "about" ? "#/" : "#/about"}>
            {route === "about" ? t.home : t.about}
          </a>
        </nav>
        <div className="language" role="group" aria-label="Language">
          {[["en", "English"], ["hi", "हिंदी"]].map(([code, label]) => (
            <button
              key={code}
              className={language === code ? "active" : ""}
              onClick={() => setLanguage(code)}
              disabled={phase !== "idle"}
            >
              {label}
            </button>
          ))}
        </div>
      </header>

      {/* Kept outside the pages so a call keeps playing while the About page is open. */}
      <div ref={audioRef} hidden />

      {route === "about" ? (
        <About language={language} onBack={() => { window.location.hash = "#/"; }} />
      ) : (
      <main>
        <section className="hero">
          <p className="tagline">{t.tagline}</p>

          <button
            className={`orb orb-${orbState}`}
            onClick={phase === "idle" ? start : undefined}
            disabled={phase === "connecting"}
            aria-label={phase === "idle" ? t.start : status?.text}
          >
            <span className="orb-ring" aria-hidden="true" />
            <span className="orb-ring delay" aria-hidden="true" />
            <span className="orb-core" aria-hidden="true">
              {orbState === "speaking" ? (
                <span className="bars"><i /><i /><i /><i /></span>
              ) : orbState === "thinking" || orbState === "joining" || orbState === "connecting" ? (
                <span className="dots"><i /><i /><i /></span>
              ) : (
                <svg viewBox="0 0 24 24" width="44" height="44" fill="currentColor">
                  <path d="M12 14a3 3 0 0 0 3-3V5a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3Zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.92V21h2v-3.08A7 7 0 0 0 19 11h-2Z" />
                </svg>
              )}
            </span>
          </button>

          <div className={`status status-${orbState}`} aria-live="polite">
            {phase === "idle" ? (
              <strong>{t.start}</strong>
            ) : (
              <>
                <strong>{status?.text}</strong>
                {status?.hint && <span>{status.hint}</span>}
              </>
            )}
          </div>

          {phase === "connected" && (
            <div className="controls">
              <button className="pill" onClick={toggleMute}>{muted ? `🎙️ ${t.unmute}` : `🔇 ${t.mute}`}</button>
              <button className="pill danger" onClick={stop}>✕ {t.end}</button>
            </div>
          )}
          {phase === "connected" && <p className="tip">{t.headphones}</p>}
          {error && <p className="error">{error}</p>}
        </section>

        {phase === "idle" && (
          <section className="steps">
            {t.steps.map(([icon, title, text]) => (
              <div className="step" key={title}>
                <span className="step-icon" aria-hidden="true">{icon}</span>
                <strong>{title}</strong>
                <span>{text}</span>
              </div>
            ))}
          </section>
        )}

        {helpRequest && (
          <div className="notice">
            <span aria-hidden="true">✅</span> {t.saved(helpRequest.id)}
          </div>
        )}

        <section className="panel chat">
          <h2>{t.conversation}</h2>
          <div className="log" ref={logRef}>
            {messages.length === 0 ? (
              <div className="empty">
                <p>{phase === "idle" ? t.emptyIdle : status?.text}</p>
                <span className="try-label">{t.tryLabel}</span>
                <div className="chips">
                  {t.examples.map((example) => (
                    <button
                      key={example}
                      className="chip"
                      onClick={() => sendText(example)}
                      disabled={!agentReady}
                    >
                      “{example}”
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((message) => (
                <div key={message.id} className={`message ${message.from}`}>
                  <span className="who">{message.from === "you" ? t.you : t.assistant}</span>
                  <p>{message.text}</p>
                </div>
              ))
            )}
          </div>
          {phase === "connected" && (
            <form className="composer" onSubmit={onSubmit}>
              <input
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                placeholder={agentReady ? t.placeholder : t.placeholderWait}
                disabled={!agentReady}
              />
              <button type="submit" disabled={!agentReady || !draft.trim()}>{t.send}</button>
            </form>
          )}
        </section>

        {programs && (
          <section className="programs">
            <h2>{t.programsFound}</h2>
            {programs.length === 0 && <p className="panel muted-text">{t.noMatch}</p>}
            <div className="cards">
              {programs.map((program) => {
                const [icon, en, hi] = CATEGORIES[program.category] || ["📄", program.category, program.category];
                return (
                  <article className="card" key={program.id}>
                    <span className="badge">{icon} {language === "hi" ? hi : en}</span>
                    <h3>{program.name}</h3>
                    <p className="org">{program.organization}</p>
                    {program.benefits && (
                      <div className="highlight">
                        <span>{t.benefits}</span>
                        <p>{program.benefits}</p>
                      </div>
                    )}
                    {program.eligibility && (
                      <details>
                        <summary>{t.eligible}</summary>
                        <p>{program.eligibility}</p>
                      </details>
                    )}
                    {program.how_to_apply && (
                      <details>
                        <summary>{t.apply}</summary>
                        <p>{program.how_to_apply}</p>
                      </details>
                    )}
                    {program.documents?.length > 0 && (
                      <div className="docs">
                        <span>{t.documents}</span>
                        <ul>
                          {program.documents.map((doc) => <li key={doc}>{doc}</li>)}
                        </ul>
                      </div>
                    )}
                    <a className="source" href={program.source_url} target="_blank" rel="noreferrer">
                      {t.source} ↗
                    </a>
                    {program.last_checked && <span className="checked">{t.checked} {program.last_checked}</span>}
                  </article>
                );
              })}
            </div>
            <p className="disclaimer">{t.disclaimer}</p>
          </section>
        )}
      </main>
      )}

      <footer className="helplines">
        <span>🚨 {t.emergency} <strong>112</strong></span>
        <span className="sep">{t.helplines}</span>
      </footer>
    </div>
  );
}
