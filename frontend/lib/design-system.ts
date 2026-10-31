export const COLORS = {
  primary: "#99efe3",
  onPrimary: "#003732",
  primaryContainer: "#7dd3c7",
  onPrimaryContainer: "#005b53",
  primaryFixed: "#9cf2e6",
  primaryFixedDim: "#80d6ca",
  secondary: "#a0d0c6",
  secondaryContainer: "#215149",
  tertiary: "#d0e2f0",
  tertiaryContainer: "#b4c6d3",
  surface: "#08151c",
  surfaceDim: "#08151c",
  surfaceBright: "#2f3b43",
  surfaceLowest: "#040f17",
  surfaceLow: "#111d25",
  surfaceContainer: "#152129",
  surfaceHigh: "#202b34",
  surfaceHighest: "#2a363f",
  error: "#ffb4ab",
  errorContainer: "#93000a",
} as const;

export const FONTS = {
  headline: "Manrope",
  body: "Inter",
  symbols: "Material Symbols Outlined",
} as const;

export const RADIUS = {
  DEFAULT: "0.25rem",
  lg: "0.5rem",
  xl: "0.75rem",
  full: "9999px",
} as const;

export const SPACING = {
  xs: "0.25rem",
  sm: "0.5rem",
  md: "1rem",
  lg: "1.5rem",
  xl: "2.5rem",
  margin: "2rem",
  gutter: "1.5rem",
  gutterSm: "1rem",
} as const;

export const LANG_DATA = {
  hinglish: {
    badge: "Code-Switched Hindi-English",
    confidence: "Decoded: 96%",
    raw: '"Mujhe... wa-ter... cha-hi-ye... bohot jaldi"',
    clean: '"मुझे पानी चाहिए, कृपया थोड़ा जल्दी दीजिए।"',
    translation: '"I need some water, please bring it quickly."',
    alternates: ["Urgent Hydration", "Polite Request", "Direct Command"],
    btnText: "Synthesize in Hinglish Voice",
  },
  hindi: {
    badge: "शुद्ध हिंदी (Standard Hindi)",
    confidence: "Decoded: 98%",
    raw: '"ह-म-को... चाई... दी-जी-ए... ग-रम"',
    clean: '"कृपया मुझे एक कप गर्म चाय दीजिए।"',
    translation: '"Please give me a cup of hot tea."',
    alternates: ["चाय का अनुरोध", "नाश्ते का समय", "गर्म पेय"],
    btnText: "हिंदी वाणी में बोलें",
  },
  marathi: {
    badge: "मराठी बोली (Marathi Dialect)",
    confidence: "Decoded: 95%",
    raw: '"म-ला... बा-हे-र... जा-या-चे... आ-हे"',
    clean: '"मला थोडा वेळ बाहेर फिरायला जायचे आहे."',
    translation: '"I would like to go outside for a short walk."',
    alternates: ["बाहेर जाणे", "ताजी हवा", "मदत हवी आहे"],
    btnText: "मराठी आवाजात उच्चार करा",
  },
  english: {
    badge: "Standard Indian English",
    confidence: "Decoded: 99%",
    raw: '"Pl-ease... call... doc-tor... now"',
    clean: '"Please contact the attending physician immediately."',
    translation: '"Direct high-priority clinical assistance notice."',
    alternates: ["Clinical Notice", "Doctor Call", "Urgent Care"],
    btnText: "Synthesize in English Voice",
  },
} as const;

export type LangKey = keyof typeof LANG_DATA;

export const CLIP_DATA = {
  A: {
    label: "Clip A: Hydration Request",
    verbatim: "I... n-eed wa...ter (<breath 0.4s>) pl-ease now",
    clearEn: "I need a glass of water, please right away.",
    clearHi: "मुझे कृपया तुरंत एक गिलास पानी चाहिए।",
    clearMr: "मला कृपया लगेच एक ग्लास पाणी द्या.",
    rationale: 'Corrected phonetic slurring on "wa...ter", bridged breath interval, and applied user hydration habit context.',
  },
  B: {
    label: "Clip B: Work Standup",
    verbatim: "S-yync... re-poort done (<tremor pause>) pu-shed c-oode",
    clearEn: "I have finished my sync report and pushed the latest updates to repository.",
    clearHi: "मैंने अपनी सिंक रिपोर्ट पूरी कर ली है और कोड पुश कर दिया है।",
    clearMr: "मी माझा कामाचा रिपोर्ट पूर्ण केला आहे आणि कोड पुश केला आहे.",
    rationale: "Rebuilt tech phrasing; mapped 'pu-shed c-oode' to daily standup vocabulary dictionary.",
  },
  C: {
    label: "Clip C: Medication Time",
    verbatim: "T-ime p-ill (<hesitation>) af-ter lu-nch",
    clearEn: "Is it time for my afternoon medication after lunch?",
    clearHi: "क्या दोपहर के भोजन के बाद की दवा लेने का समय हो गया है?",
    clearMr: "दुपारच्या जेवणानंतरचे औषध घेण्याची वेळ झाली आहे का?",
    rationale: "Cross-referenced user medical regimen schedule for lunchtime pill inquiry.",
  },
} as const;

export type ClipKey = keyof typeof CLIP_DATA;
