// Edit this block to change the creator details shown on the About page.
// Leave a link empty ("") to hide it.
export const CREATOR = {
  name: "Garv Kaushik",
  role: " AI Full-Stack Engineer",
  photo: "https://lh3.googleusercontent.com/d/1IhT8iYBgBcW1Mbq8XozqnGobAs8n9qn3=w400",
  bio: {
    en: "I'm Garv Kaushik, a Computer Science student passionate about AI, intelligent agents, and full-stack development. Community Connect is my idea for exploring how conversational AI could make social welfare information easier to discover and understand. Through voice-based interaction, retrieval-augmented generation, and AI agents, I envision a platform that could help people find relevant schemes and navigate available support more easily.",
    //hi: "आपके बारे में एक छोटा अनुच्छेद: आप क्या करते हैं, और आपने CommunityConnect क्यों बनाया।",
  },
  links: {
    github: "https://github.com/GarvKaushik",
    linkedin: "https://www.linkedin.com/in/garv-kaushik/",
    email: "kaushikgarv0806@gmail.com",
    //website: "",
  },
};

const TEXT = {
  en: {
    back: "← Back to the assistant",
    title: "About CommunityConnect AI",
    intro:
      "CommunityConnect AI is a voice assistant that helps people in India find government support schemes, just by talking in English or Hindi.",
    whyTitle: "Why it exists",
    why:
      "Many people who need help the most find government websites, forms and eligibility rules hard to use. CommunityConnect listens to what someone needs, finds verified schemes that may help, explains them simply, and connects them to a human volunteer when they want more help.",
    whoTitle: "Who it is for",
    who: [
      "People with limited reading or digital confidence",
      "Hindi and English speakers",
      "Families looking for help with education, health, money, jobs, housing, food and more",
    ],
    howTitle: "How it works",
    how: [
      ["🗣️", "You speak", "Your voice is turned into text on our own server (Whisper)."],
      ["🧠", "The assistant understands", "A language model works out what you need and asks only what's missing."],
      ["📚", "It searches verified schemes", "Only schemes from official government sources, never made-up ones."],
      ["🔊", "It explains simply", "The answer is spoken back in your language, with sources on screen."],
      ["🤝", "A volunteer can call", "With your permission, a volunteer gets your request on Telegram."],
    ],
    notTitle: "What it is not",
    not:
      "It is not a government office, social worker, doctor or lawyer. It never promises eligibility: the scheme office decides. In an emergency, call 112.",
    trustTitle: "Trust and privacy",
    trust: [
      "Every scheme links to its official government source.",
      "Your phone number is saved only if you agree to a volunteer call, and it is read back to you first.",
      "Emergency helplines are always shown: 112, women 181, children 1098, mental health 14416.",
    ],
    numbersTitle: "In numbers",
    numbers: [
      ["43", "verified schemes"],
      ["11", "categories"],
      ["2", "languages"],
      ["100%", "of answers grounded in sources*"],
    ],
    footnote: "* On the project's held-out test set of 45 questions. Details are in the README.",
    creatorTitle: "Made by",
    contact: "Get in touch",
    stackTitle: "Built with",
  },
  hi: {
    back: "← सहायक पर वापस जाएँ",
    title: "CommunityConnect AI के बारे में",
    intro:
      "CommunityConnect AI एक आवाज़ सहायक है जो भारत में लोगों को हिंदी या अंग्रेज़ी में बात करके सरकारी सहायता योजनाएँ ढूँढने में मदद करता है।",
    whyTitle: "यह क्यों बना",
    why:
      "जिन लोगों को मदद की सबसे ज़्यादा ज़रूरत होती है, उन्हें अक्सर सरकारी वेबसाइटें, फ़ॉर्म और पात्रता के नियम समझना मुश्किल लगता है। CommunityConnect उनकी ज़रूरत सुनता है, मदद कर सकने वाली सत्यापित योजनाएँ ढूँढता है, उन्हें आसान भाषा में समझाता है, और ज़रूरत हो तो किसी स्वयंसेवक से जोड़ता है।",
    whoTitle: "यह किसके लिए है",
    who: [
      "जिन्हें पढ़ने या मोबाइल-इंटरनेट इस्तेमाल करने में कठिनाई होती है",
      "हिंदी और अंग्रेज़ी बोलने वाले",
      "पढ़ाई, स्वास्थ्य, पैसे, रोज़गार, घर, भोजन आदि में मदद ढूँढ रहे परिवार",
    ],
    howTitle: "यह कैसे काम करता है",
    how: [
      ["🗣️", "आप बोलते हैं", "आपकी आवाज़ हमारे अपने सर्वर पर टेक्स्ट में बदली जाती है (Whisper)।"],
      ["🧠", "सहायक समझता है", "भाषा मॉडल समझता है कि आपको क्या चाहिए और केवल ज़रूरी सवाल पूछता है।"],
      ["📚", "सत्यापित योजनाएँ खोजता है", "केवल आधिकारिक सरकारी स्रोतों की योजनाएँ, कभी मनगढ़ंत नहीं।"],
      ["🔊", "आसान भाषा में बताता है", "जवाब आपकी भाषा में बोला जाता है, और स्रोत स्क्रीन पर दिखते हैं।"],
      ["🤝", "स्वयंसेवक कॉल कर सकता है", "आपकी अनुमति से, स्वयंसेवक को आपका अनुरोध Telegram पर मिलता है।"],
    ],
    notTitle: "यह क्या नहीं है",
    not:
      "यह कोई सरकारी कार्यालय, सामाजिक कार्यकर्ता, डॉक्टर या वकील नहीं है। यह पात्रता का वादा नहीं करता: फ़ैसला योजना कार्यालय करता है। आपातकाल में 112 पर कॉल करें।",
    trustTitle: "भरोसा और गोपनीयता",
    trust: [
      "हर योजना उसके आधिकारिक सरकारी स्रोत से जुड़ी है।",
      "आपका फ़ोन नंबर तभी सेव होता है जब आप स्वयंसेवक कॉल के लिए सहमत हों, और पहले आपको पढ़कर सुनाया जाता है।",
      "आपातकालीन हेल्पलाइन हमेशा दिखती हैं: 112, महिला 181, बच्चे 1098, मानसिक स्वास्थ्य 14416।",
    ],
    numbersTitle: "आँकड़ों में",
    numbers: [
      ["43", "सत्यापित योजनाएँ"],
      ["11", "श्रेणियाँ"],
      ["2", "भाषाएँ"],
      ["100%", "जवाब स्रोतों पर आधारित*"],
    ],
    footnote: "* प्रोजेक्ट के 45 सवालों वाले अलग परीक्षण सेट पर। विवरण README में है।",
    creatorTitle: "बनाने वाले",
    contact: "संपर्क करें",
    stackTitle: "किससे बना है",
  },
};

const STACK = ["LiveKit", "Whisper", "Piper TTS", "gpt-oss", "Multilingual RAG", "FastAPI", "React"];

const LINK_LABELS = {
  github: ["GitHub", (v) => v],
  linkedin: ["LinkedIn", (v) => v],
  email: ["Email", (v) => `mailto:${v}`],
  website: ["Website", (v) => v],
};

function initials(name) {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0].toUpperCase()).join("");
}

export default function About({ language, onBack }) {
  const t = TEXT[language];
  const links = Object.entries(CREATOR.links).filter(([, value]) => value);

  return (
    <div className="about">
      <button className="back" onClick={onBack}>{t.back}</button>

      <section className="about-hero">
        <span className="about-logo" aria-hidden="true">🤝</span>
        <h1>{t.title}</h1>
        <p>{t.intro}</p>
      </section>

      <section className="stats">
        {t.numbers.map(([value, label]) => (
          <div className="stat" key={label}>
            <strong>{value}</strong>
            <span>{label}</span>
          </div>
        ))}
      </section>
      <p className="footnote">{t.footnote}</p>

      <section className="panel">
        <h2>{t.whyTitle}</h2>
        <p className="prose">{t.why}</p>
        <h2 className="spaced">{t.whoTitle}</h2>
        <ul className="ticks">
          {t.who.map((item) => <li key={item}>{item}</li>)}
        </ul>
      </section>

      <section className="panel">
        <h2>{t.howTitle}</h2>
        <ol className="flow">
          {t.how.map(([icon, title, text]) => (
            <li key={title}>
              <span className="flow-icon" aria-hidden="true">{icon}</span>
              <div>
                <strong>{title}</strong>
                <p>{text}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <section className="two-col">
        <div className="panel">
          <h2>{t.trustTitle}</h2>
          <ul className="ticks">
            {t.trust.map((item) => <li key={item}>{item}</li>)}
          </ul>
        </div>
        <div className="panel warn">
          <h2>{t.notTitle}</h2>
          <p className="prose">{t.not}</p>
        </div>
      </section>

      <section className="panel creator">
        <h2>{t.creatorTitle}</h2>
        <div className="creator-row">
          {CREATOR.photo ? (
            <img className="avatar" src={CREATOR.photo} alt={CREATOR.name} referrerPolicy="no-referrer" />
          ) : (
            <span className="avatar" aria-hidden="true">{initials(CREATOR.name)}</span>
          )}
          <div>
            <strong className="creator-name">{CREATOR.name}</strong>
            <span className="creator-role">{CREATOR.role}</span>
          </div>
        </div>
        <p className="prose">{CREATOR.bio[language]}</p>
        {links.length > 0 && (
          <div className="links">
            <span>{t.contact}</span>
            {links.map(([key, value]) => {
              const [label, href] = LINK_LABELS[key];
              return (
                <a key={key} className="pill" href={href(value)} target="_blank" rel="noreferrer">
                  {label} ↗
                </a>
              );
            })}
          </div>
        )}
        <div className="stack">
          <span>{t.stackTitle}</span>
          {STACK.map((item) => <span className="tag" key={item}>{item}</span>)}
        </div>
      </section>
    </div>
  );
}
