import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "motion/react";
import {
  Wifi, WifiOff, User, Camera, CheckCircle, AlertCircle,
  Zap, Trophy, Star, ArrowRight, RotateCcw, ChevronRight, Medal
} from "lucide-react";

// ── TYPES ──────────────────────────────────────────────────────────────────────

type Screen =
  | "lobby"
  | "topic-select"
  | "round-word"
  | "countdown"
  | "capture"
  | "round-result"
  | "final-results";

type Topic = {
  id: string;
  label: string;
  emoji: string;
  words: string[];
};

type PlayerStatus = {
  id: number;
  name: string;
  deviceId: string;
  connected: boolean;
  personDetected: boolean;
  ready: boolean;
};

type RoundScore = {
  round: number;
  word: string;
  scores: [number, number, number];
  syncScore: number;
};

// ── DATA ───────────────────────────────────────────────────────────────────────

const TOPICS: Topic[] = [
  { id: "sports",   label: "스포츠",   emoji: "⚽", words: ["골프", "농구", "수영", "태권도", "야구"] },
  { id: "emotion",  label: "감정 표현", emoji: "😄", words: ["기쁨", "분노", "슬픔", "놀람", "지루함"] },
  { id: "daily",    label: "일상 생활", emoji: "🏠", words: ["월급날", "지각", "장보기", "낮잠", "청소"] },
  { id: "job",      label: "직업",     emoji: "💼", words: ["의사", "소방관", "요리사", "선생님", "경찰"] },
  { id: "animal",   label: "동물",     emoji: "🦁", words: ["기린", "펭귄", "원숭이", "독수리", "악어"] },
];

const INITIAL_PLAYERS: PlayerStatus[] = [
  { id: 1, name: "PLAYER 1", deviceId: "raspi-001", connected: true,  personDetected: true,  ready: true  },
  { id: 2, name: "PLAYER 2", deviceId: "raspi-002", connected: true,  personDetected: true,  ready: true  },
  { id: 3, name: "PLAYER 3", deviceId: "raspi-003", connected: true,  personDetected: true,  ready: true  },
];

const PLAYER_COLORS = ["#ffe600", "#ff2d78", "#00e5ff"];

// deterministic fake scores per round
function fakeScores(round: number): [number, number, number] {
  const base = [[82, 79, 61], [74, 88, 71], [90, 65, 83], [77, 80, 77], [68, 92, 74]];
  return (base[round % base.length] as [number, number, number]);
}
function fakeSyncScore(scores: [number, number, number]) {
  return Math.round((scores[0] + scores[1] + scores[2]) / 3);
}

// round LLM comments — keyed by "round-worstPlayerIdx"
// worstPlayerIdx: index of lowest scorer (0=P1, 1=P2, 2=P3)
type RoundComment = { text: string; tone: "roast" | "hype" | "neutral" };

const ROUND_LLM_COMMENTS: Record<string, RoundComment[]> = {
  "0-2": [
    { tone: "roast",   text: "아… Player 3, 혹시 '골프'를 '골골' 소리 내는 걸로 이해하신 건가요? 팔은 어디 갔죠?" },
    { tone: "roast",   text: "Player 3의 포즈 분석 결과: 61점. AI가 세 번 돌려봤습니다. 결과는 같았습니다." },
    { tone: "neutral", text: "Player 1과 2는 제법 비슷했네요. Player 3은... 독자적인 해석을 했군요. 존중합니다. 일단은요." },
  ],
  "1-0": [
    { tone: "roast",   text: "Player 1, 농구 선수 흉내가 아니라 리바운드 후 바닥에 쓰러진 모습처럼 보였습니다. 괜찮으세요?" },
    { tone: "hype",    text: "Player 2, 이번 라운드 완벽했습니다! 진짜 NBA 선수 같았어요. Player 1은 다음 라운드 화이팅!" },
    { tone: "neutral", text: "Player 2가 이번 라운드를 제패했네요. Player 1, 74점도 나쁘지 않지만 조금 아쉽죠?" },
  ],
  "2-1": [
    { tone: "roast",   text: "Player 2, 수영을 땅에서 하셨군요. 물 없이도 이렇게 할 수 있다니… 새로운 종목 탄생인가요?" },
    { tone: "hype",    text: "Player 1과 3이 완벽한 접영 자세! Player 2는 아마도 자유형을 자유롭게 해석하신 것 같네요." },
    { tone: "neutral", text: "65점이 나왔네요, Player 2. AI가 보기엔 수영보다는 '낮잠 직전' 자세에 가까웠습니다." },
  ],
  "3-0": [
    { tone: "roast",   text: "Player 1, 태권도 발차기인지 넘어지는 건지 AI가 0.3초 고민했습니다. 결론: 후자에 가깝습니다." },
    { tone: "hype",    text: "Player 2와 3의 태권도 자세 싱크가 80%! 이 정도면 사범님 수준인데요?" },
    { tone: "neutral", text: "이번 라운드 팀 전체 싱크가 높은 편이에요. Player 1이 살짝 자기만의 길을 갔지만 전반적으로 좋았어요." },
  ],
  "4-1": [
    { tone: "roast",   text: "Player 2, 야구 배팅 자세가 마치 모기를 잡으려는 것처럼 보였습니다. 오늘 모기 많나요?" },
    { tone: "hype",    text: "Player 1과 3이 야구 투수 폼까지 맞췄네요! Player 2는 아마 타자 포지션을 혼자 맡은 것 같습니다." },
    { tone: "neutral", text: "마지막 라운드치고 꽤 선방했어요! Player 2의 독창성은 다음 시즌에 빛날 겁니다." },
  ],
};

function getRoundComment(round: number, scores: [number, number, number]): RoundComment {
  const minScore = Math.min(...scores);
  const worstIdx = scores.indexOf(minScore);
  const key = `${round}-${worstIdx}`;
  const pool = ROUND_LLM_COMMENTS[key] ?? [
    { tone: "neutral" as const, text: "세 명 모두 나름의 개성을 보여줬습니다. AI는 최선을 다해 분석했고, 팀도 최선을 다했... 겠죠?" },
  ];
  return pool[round % pool.length];
}

// ── SMALL SHARED COMPONENTS ────────────────────────────────────────────────────

function ScreenLabel({ label }: { label: string }) {
  return (
    <div
      className="inline-flex items-center gap-2 px-3 py-1 mb-6"
      style={{ border: "1px solid var(--border)", backgroundColor: "#1e1e2a", borderRadius: "2px" }}
    >
      <div className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ backgroundColor: "var(--primary)" }} />
      <span style={{ fontFamily: "JetBrains Mono, monospace", fontSize: "11px", color: "#888899", letterSpacing: "0.12em" }}>
        {label}
      </span>
    </div>
  );
}

function SkipBtn({ onClick }: { onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="mt-8 text-xs transition-opacity hover:opacity-60"
      style={{ fontFamily: "JetBrains Mono, monospace", color: "#333344", background: "none", border: "none", cursor: "pointer" }}
    >
      SKIP →
    </button>
  );
}

function RoundPips({ total, current }: { total: number; current: number }) {
  return (
    <div className="flex items-center gap-2">
      {Array.from({ length: total }).map((_, i) => (
        <div
          key={i}
          className="h-1"
          style={{
            width: i === current ? "24px" : "8px",
            backgroundColor: i < current ? "#00e67688" : i === current ? "var(--primary)" : "#1e1e2a",
            borderRadius: "1px",
            transition: "all 0.3s",
          }}
        />
      ))}
    </div>
  );
}

function PoseStickFigure({ variant = 0, color = "#ffe600" }: { variant?: number; color?: string }) {
  const poses = [
    <g key="0">
      <circle cx="50" cy="18" r="9" fill="none" stroke={color} strokeWidth="3" />
      <line x1="50" y1="27" x2="50" y2="62" stroke={color} strokeWidth="3" />
      <line x1="50" y1="38" x2="24" y2="22" stroke={color} strokeWidth="3" />
      <line x1="50" y1="38" x2="76" y2="22" stroke={color} strokeWidth="3" />
      <line x1="50" y1="62" x2="32" y2="88" stroke={color} strokeWidth="3" />
      <line x1="50" y1="62" x2="68" y2="88" stroke={color} strokeWidth="3" />
    </g>,
    <g key="1">
      <circle cx="50" cy="18" r="9" fill="none" stroke={color} strokeWidth="3" />
      <line x1="50" y1="27" x2="50" y2="62" stroke={color} strokeWidth="3" />
      <line x1="50" y1="40" x2="14" y2="42" stroke={color} strokeWidth="3" />
      <line x1="50" y1="40" x2="86" y2="42" stroke={color} strokeWidth="3" />
      <line x1="50" y1="62" x2="36" y2="90" stroke={color} strokeWidth="3" />
      <line x1="50" y1="62" x2="64" y2="90" stroke={color} strokeWidth="3" />
    </g>,
    <g key="2">
      <circle cx="50" cy="18" r="9" fill="none" stroke={color} strokeWidth="3" />
      <line x1="50" y1="27" x2="50" y2="62" stroke={color} strokeWidth="3" />
      <line x1="50" y1="40" x2="28" y2="56" stroke={color} strokeWidth="3" />
      <line x1="28" y1="56" x2="36" y2="38" stroke={color} strokeWidth="3" />
      <line x1="50" y1="40" x2="72" y2="56" stroke={color} strokeWidth="3" />
      <line x1="72" y1="56" x2="64" y2="38" stroke={color} strokeWidth="3" />
      <line x1="50" y1="62" x2="36" y2="90" stroke={color} strokeWidth="3" />
      <line x1="50" y1="62" x2="64" y2="90" stroke={color} strokeWidth="3" />
    </g>,
    <g key="3">
      <circle cx="50" cy="18" r="9" fill="none" stroke={color} strokeWidth="3" />
      <line x1="50" y1="27" x2="50" y2="62" stroke={color} strokeWidth="3" />
      <line x1="50" y1="36" x2="30" y2="28" stroke={color} strokeWidth="3" />
      <line x1="50" y1="36" x2="68" y2="50" stroke={color} strokeWidth="3" />
      <line x1="50" y1="62" x2="30" y2="85" stroke={color} strokeWidth="3" />
      <line x1="50" y1="62" x2="62" y2="88" stroke={color} strokeWidth="3" />
    </g>,
    <g key="4">
      <circle cx="50" cy="18" r="9" fill="none" stroke={color} strokeWidth="3" />
      <line x1="50" y1="27" x2="50" y2="62" stroke={color} strokeWidth="3" />
      <line x1="50" y1="38" x2="22" y2="30" stroke={color} strokeWidth="3" />
      <line x1="22" y1="30" x2="18" y2="14" stroke={color} strokeWidth="3" />
      <line x1="50" y1="38" x2="78" y2="30" stroke={color} strokeWidth="3" />
      <line x1="78" y1="30" x2="82" y2="14" stroke={color} strokeWidth="3" />
      <line x1="50" y1="62" x2="36" y2="90" stroke={color} strokeWidth="3" />
      <line x1="50" y1="62" x2="64" y2="90" stroke={color} strokeWidth="3" />
    </g>,
  ];
  return (
    <svg viewBox="0 0 100 100" className="w-full h-full" style={{ filter: `drop-shadow(0 0 5px ${color}88)` }}>
      {poses[variant % poses.length]}
    </svg>
  );
}

// ── SCREEN 01: LOBBY ───────────────────────────────────────────────────────────

function LobbyScreen({ onStart }: { onStart: () => void }) {
  const players = INITIAL_PLAYERS;
  const readyCount = players.filter((p) => p.ready).length;
  const allReady = readyCount === players.length;

  return (
    <div className="flex flex-col h-full p-8 max-w-5xl mx-auto w-full">
      <ScreenLabel label="SCREEN 01 — 대기방" />
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="text-4xl font-black mb-1" style={{ fontFamily: "Noto Sans KR, sans-serif", letterSpacing: "-0.02em" }}>
            이구동성
          </h1>
          <p style={{ color: "var(--muted-foreground)", fontSize: "14px" }}>3명이 같은 포즈를 취하는 게임</p>
        </div>
        <div className="flex items-center gap-2 px-4 py-2" style={{ border: "1px solid var(--border)", backgroundColor: "var(--secondary)" }}>
          <Zap size={14} style={{ color: "var(--primary)" }} />
          <span style={{ fontFamily: "JetBrains Mono, monospace", fontSize: "12px", color: "var(--muted-foreground)" }}>
            {readyCount}/3 준비 완료
          </span>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4 flex-1 mb-8">
        {players.map((player) => {
          const color = PLAYER_COLORS[player.id - 1];
          const statusColor = !player.connected ? "#444455" : !player.personDetected ? "#ff8c00" : "#00e676";
          return (
            <div key={player.id} className="flex flex-col border" style={{ backgroundColor: "var(--card)", borderColor: `${color}44` }}>
              <div className="flex items-center justify-between px-4 py-3 border-b" style={{ borderColor: "var(--border)" }}>
                <span className="text-xs font-bold tracking-widest" style={{ fontFamily: "JetBrains Mono, monospace", color }}>
                  {player.name}
                </span>
                <div className="flex items-center gap-2">
                  {player.connected ? <Wifi size={13} style={{ color: statusColor }} /> : <WifiOff size={13} style={{ color: statusColor }} />}
                  <span style={{ fontFamily: "JetBrains Mono, monospace", fontSize: "10px", color: statusColor }}>{player.deviceId}</span>
                </div>
              </div>
              <div className="relative flex-1 flex items-center justify-center" style={{ backgroundColor: "#0d0d14", minHeight: "120px" }}>
                <Camera size={22} style={{ color: "#222233" }} />
                <div className="absolute bottom-2 right-2 flex items-center gap-1 px-2 py-0.5"
                  style={{ backgroundColor: "#00e67622", border: "1px solid #00e67644", borderRadius: "2px" }}>
                  <User size={9} style={{ color: "#00e676" }} />
                  <span style={{ fontFamily: "JetBrains Mono, monospace", fontSize: "9px", color: "#00e676" }}>DETECTED</span>
                </div>
                <div className="absolute top-2 left-2 flex items-center gap-1">
                  <div className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ backgroundColor: "#ff2d2d" }} />
                  <span style={{ fontFamily: "JetBrains Mono, monospace", fontSize: "9px", color: "#555566" }}>LIVE</span>
                </div>
              </div>
              <div className="px-4 py-2.5 flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: "#00e676" }} />
                  <span style={{ fontFamily: "JetBrains Mono, monospace", fontSize: "10px", color: "#666677" }}>준비 완료</span>
                </div>
                <CheckCircle size={13} style={{ color: "#00e676" }} />
              </div>
            </div>
          );
        })}
      </div>

      <button
        onClick={onStart}
        className="w-full py-4 flex items-center justify-center gap-3 font-black text-lg transition-opacity hover:opacity-90"
        style={{
          fontFamily: "Noto Sans KR, sans-serif",
          backgroundColor: "var(--primary)",
          color: "#0a0a0f",
          border: "1px solid var(--primary)",
          cursor: "pointer",
          letterSpacing: "0.05em",
        }}
      >
        주제 선택하기 <ArrowRight size={20} />
      </button>
    </div>
  );
}

// ── SCREEN 02: TOPIC SELECT ────────────────────────────────────────────────────

function TopicSelectScreen({ onSelect }: { onSelect: (topic: Topic) => void }) {
  const [hovered, setHovered] = useState<string | null>(null);

  return (
    <div className="flex flex-col h-full items-center justify-center p-8 max-w-3xl mx-auto w-full">
      <ScreenLabel label="SCREEN 02 — 주제 선택" />

      <p className="mb-2 text-center" style={{ fontFamily: "JetBrains Mono, monospace", fontSize: "11px", color: "#888899", letterSpacing: "0.2em" }}>
        오늘의 주제를 선택하세요
      </p>
      <h2 className="font-black text-3xl mb-10 text-center" style={{ fontFamily: "Noto Sans KR, sans-serif" }}>
        어떤 걸로 할까요?
      </h2>

      <div className="w-full space-y-2">
        {TOPICS.map((topic) => {
          const isHovered = hovered === topic.id;
          return (
            <motion.button
              key={topic.id}
              onHoverStart={() => setHovered(topic.id)}
              onHoverEnd={() => setHovered(null)}
              onClick={() => onSelect(topic)}
              className="w-full flex items-center justify-between px-6 py-4 transition-colors"
              style={{
                backgroundColor: isHovered ? "#1e1e2a" : "var(--card)",
                border: `1px solid ${isHovered ? "var(--primary)" : "var(--border)"}`,
                cursor: "pointer",
                fontFamily: "Noto Sans KR, sans-serif",
              }}
            >
              <div className="flex items-center gap-5">
                <span style={{ fontSize: "28px" }}>{topic.emoji}</span>
                <div className="text-left">
                  <p className="font-black text-xl" style={{ color: isHovered ? "var(--primary)" : "var(--foreground)" }}>
                    {topic.label}
                  </p>
                  <p style={{ fontSize: "12px", color: "#666677", fontFamily: "JetBrains Mono, monospace", marginTop: "2px" }}>
                    {topic.words.join(" · ")}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className="flex gap-1">
                  {topic.words.slice(0, 5).map((_, i) => (
                    <div key={i} className="w-1 h-4" style={{ backgroundColor: isHovered ? "#ffe60044" : "#1e1e2a", borderRadius: "1px" }} />
                  ))}
                </div>
                <span style={{ fontFamily: "JetBrains Mono, monospace", fontSize: "11px", color: "#444455" }}>
                  5 라운드
                </span>
                <ChevronRight size={16} style={{ color: isHovered ? "var(--primary)" : "#444455" }} />
              </div>
            </motion.button>
          );
        })}
      </div>
    </div>
  );
}

// ── SCREEN 03: ROUND WORD REVEAL ──────────────────────────────────────────────

function RoundWordScreen({
  topic, word, round, total, onNext,
}: { topic: Topic; word: string; round: number; total: number; onNext: () => void }) {
  const [revealed, setRevealed] = useState(false);
  useEffect(() => { const t = setTimeout(() => setRevealed(true), 400); return () => clearTimeout(t); }, [word]);

  return (
    <div className="flex flex-col h-full items-center justify-center p-8 max-w-3xl mx-auto w-full">
      <div className="flex items-center gap-3 mb-8">
        <ScreenLabel label={`ROUND ${round + 1} / ${total}`} />
        <RoundPips total={total} current={round} />
      </div>

      <p className="mb-3" style={{ fontFamily: "JetBrains Mono, monospace", fontSize: "11px", color: "#888899", letterSpacing: "0.2em" }}>
        주제 : {topic.label} {topic.emoji}
      </p>

      <div
        className="relative inline-block px-16 py-10 mb-10"
        style={{ border: "1px solid var(--border)", backgroundColor: "var(--card)" }}
      >
        {[
          "top-0 left-0 -translate-x-px -translate-y-px border-t-2 border-l-2",
          "top-0 right-0 translate-x-px -translate-y-px border-t-2 border-r-2",
          "bottom-0 left-0 -translate-x-px translate-y-px border-b-2 border-l-2",
          "bottom-0 right-0 translate-x-px translate-y-px border-b-2 border-r-2",
        ].map((cls, i) => (
          <div key={i} className={`absolute w-5 h-5 ${cls}`} style={{ borderColor: "var(--primary)" }} />
        ))}
        <motion.span
          key={word}
          initial={{ opacity: 0, filter: "blur(16px)", scale: 0.85 }}
          animate={revealed ? { opacity: 1, filter: "blur(0px)", scale: 1 } : {}}
          transition={{ duration: 0.5, ease: "easeOut" }}
          className="block font-black"
          style={{
            fontFamily: "Noto Sans KR, sans-serif",
            fontSize: "clamp(52px, 9vw, 88px)",
            color: "var(--primary)",
            letterSpacing: "-0.02em",
            lineHeight: 1,
          }}
        >
          {word}
        </motion.span>
      </div>

      <motion.p
        initial={{ opacity: 0 }}
        animate={revealed ? { opacity: 1 } : {}}
        transition={{ delay: 0.3 }}
        style={{ fontFamily: "Noto Sans KR, sans-serif", fontSize: "15px", color: "var(--muted-foreground)", marginBottom: "40px" }}
      >
        몸으로 표현하세요
      </motion.p>

      <motion.button
        initial={{ opacity: 0 }}
        animate={revealed ? { opacity: 1 } : {}}
        transition={{ delay: 0.5 }}
        onClick={onNext}
        className="px-12 py-4 font-black text-base flex items-center gap-3 transition-opacity hover:opacity-80"
        style={{ fontFamily: "Noto Sans KR, sans-serif", backgroundColor: "var(--primary)", color: "#0a0a0f", border: "none", cursor: "pointer" }}
      >
        카운트다운 시작 <ArrowRight size={18} />
      </motion.button>
    </div>
  );
}

// ── SCREEN 04: COUNTDOWN ──────────────────────────────────────────────────────

function CountdownScreen({ round, total, onNext }: { round: number; total: number; onNext: () => void }) {
  const [count, setCount] = useState(3);
  const [done, setDone] = useState(false);

  useEffect(() => {
    setCount(3);
    setDone(false);
  }, [round]);

  useEffect(() => {
    if (count <= 0) {
      setDone(true);
      const t = setTimeout(onNext, 600);
      return () => clearTimeout(t);
    }
    const t = setTimeout(() => setCount((c) => c - 1), 900);
    return () => clearTimeout(t);
  }, [count, onNext]);

  return (
    <div className="flex flex-col h-full items-center justify-center p-8 max-w-2xl mx-auto w-full">
      <div className="flex items-center gap-3 mb-8">
        <ScreenLabel label={`ROUND ${round + 1} / ${total}`} />
        <RoundPips total={total} current={round} />
      </div>

      <div className="relative flex items-center justify-center w-56 h-56 mb-6">
        <div className="absolute inset-0 rounded-full" style={{ border: "1px solid var(--border)" }} />
        <div className="absolute inset-3 rounded-full" style={{ border: `2px solid ${done ? "var(--accent)" : "var(--primary)"}44` }} />
        <AnimatePresence mode="wait">
          <motion.span
            key={done ? "go" : count}
            initial={{ opacity: 0, scale: 1.6 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.4 }}
            transition={{ duration: 0.25 }}
            className="font-black"
            style={{
              fontFamily: done ? "Noto Sans KR, sans-serif" : "JetBrains Mono, monospace",
              fontSize: done ? "64px" : "108px",
              color: done ? "var(--accent)" : "var(--primary)",
              lineHeight: 1,
            }}
          >
            {done ? "GO!" : count}
          </motion.span>
        </AnimatePresence>
      </div>

      <div className="flex items-center gap-3">
        {[3, 2, 1].map((n) => (
          <div
            key={n}
            className="w-8 h-8 flex items-center justify-center"
            style={{
              border: `1px solid ${count < n || done ? "#ffe60066" : "var(--border)"}`,
              backgroundColor: count < n || done ? "#ffe60011" : "transparent",
              fontFamily: "JetBrains Mono, monospace", fontSize: "13px",
              color: count < n || done ? "var(--primary)" : "#333344",
            }}
          >
            {n}
          </div>
        ))}
      </div>
      <SkipBtn onClick={onNext} />
    </div>
  );
}

// ── SCREEN 05: CAPTURE ────────────────────────────────────────────────────────

function CaptureScreen({ round, total, word, onNext }: { round: number; total: number; word: string; onNext: () => void }) {
  const [phase, setPhase] = useState<"capturing" | "done">("capturing");
  useEffect(() => {
    setPhase("capturing");
    const t1 = setTimeout(() => setPhase("done"), 1400);
    const t2 = setTimeout(onNext, 2200);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, [round, onNext]);

  return (
    <div className="flex flex-col h-full p-8 max-w-5xl mx-auto w-full">
      <div className="flex items-center gap-3 mb-6">
        <ScreenLabel label={`ROUND ${round + 1} / ${total} — 포즈 캡처`} />
        <RoundPips total={total} current={round} />
      </div>

      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-3">
          <span className="font-black text-2xl" style={{ fontFamily: "Noto Sans KR, sans-serif", color: "var(--primary)" }}>
            {word}
          </span>
          <span style={{ fontFamily: "Noto Sans KR, sans-serif", fontSize: "14px", color: "#666677" }}>포즈 분석 중</span>
        </div>
        <div
          className="flex items-center gap-2 px-3 py-1.5"
          style={{ border: `1px solid ${phase === "done" ? "#00e67644" : "#ffe60044"}`, backgroundColor: phase === "done" ? "#00e67611" : "#ffe60011" }}
        >
          <div className="w-2 h-2 rounded-full" style={{ backgroundColor: phase === "done" ? "#00e676" : "var(--primary)", animation: phase === "done" ? "none" : "pulse 0.8s infinite" }} />
          <span style={{ fontFamily: "JetBrains Mono, monospace", fontSize: "11px", color: phase === "done" ? "#00e676" : "var(--primary)" }}>
            {phase === "done" ? "캡처 완료" : "캡처 중..."}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4 flex-1">
        {INITIAL_PLAYERS.map((player, i) => {
          const color = PLAYER_COLORS[i];
          return (
            <div key={player.id} className="flex flex-col border" style={{ backgroundColor: "var(--card)", borderColor: `${color}33` }}>
              <div className="flex items-center justify-between px-4 py-3 border-b" style={{ borderColor: "var(--border)" }}>
                <span className="text-xs font-bold tracking-widest" style={{ fontFamily: "JetBrains Mono, monospace", color }}>{player.name}</span>
                <div className="flex items-center gap-1">
                  <div className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ backgroundColor: "#ff2d2d" }} />
                  <span style={{ fontFamily: "JetBrains Mono, monospace", fontSize: "9px", color: "#555566" }}>REC</span>
                </div>
              </div>
              <div className="relative flex-1 flex items-center justify-center" style={{ backgroundColor: "#0d0d14", minHeight: "160px" }}>
                <div className="absolute inset-0 opacity-10" style={{
                  backgroundImage: `linear-gradient(${color}44 1px, transparent 1px), linear-gradient(90deg, ${color}44 1px, transparent 1px)`,
                  backgroundSize: "20px 20px",
                }} />
                <div className="relative w-24 h-24">
                  <PoseStickFigure variant={(round + i) % 5} color={color} />
                </div>
                {phase === "done" && (
                  <div className="absolute inset-0 flex items-center justify-center" style={{ backgroundColor: "#0a0a0f88" }}>
                    <CheckCircle size={30} style={{ color: "#00e676" }} />
                  </div>
                )}
              </div>
              <div className="px-4 py-2.5 flex items-center gap-2">
                <span style={{ fontFamily: "JetBrains Mono, monospace", fontSize: "9px", color: "#444455" }}>MediaPipe Pose</span>
                <div className="flex-1 h-px" style={{ backgroundColor: `${color}22` }} />
                <span style={{ fontFamily: "JetBrains Mono, monospace", fontSize: "9px", color }}>
                  {phase === "done" ? "✓ 33 pts" : "추출 중..."}
                </span>
              </div>
            </div>
          );
        })}
      </div>
      <SkipBtn onClick={onNext} />
    </div>
  );
}

// ── SCREEN 06: ROUND RESULT (quick) ───────────────────────────────────────────

const TONE_CONFIG = {
  roast:   { border: "#ff2d7844", bg: "#ff2d7808", dot: "#ff2d78", label: "AI 독설", icon: "🔥" },
  hype:    { border: "#ffe60044", bg: "#ffe60008", dot: "#ffe600", label: "AI 칭찬", icon: "⚡" },
  neutral: { border: "#ffffff22", bg: "#ffffff05", dot: "#888899", label: "AI 해설", icon: "🤖" },
};

function RoundResultScreen({
  round, total, word, scores, syncScore, onNext,
}: { round: number; total: number; word: string; scores: [number, number, number]; syncScore: number; onNext: () => void }) {
  const isLast = round === total - 1;
  const [commentVisible, setCommentVisible] = useState(false);
  const comment = getRoundComment(round, scores);
  const toneStyle = TONE_CONFIG[comment.tone];

  useEffect(() => {
    setCommentVisible(false);
    const t1 = setTimeout(() => setCommentVisible(true), 600);
    const t2 = setTimeout(onNext, isLast ? 999999 : 4200);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, [round, isLast, onNext]);

  const maxScore = Math.max(...scores);
  const minScore = Math.min(...scores);
  const worstIdx = scores.indexOf(minScore);

  return (
    <div className="flex flex-col h-full items-center justify-center p-8 max-w-3xl mx-auto w-full">
      <div className="flex items-center gap-3 mb-6">
        <ScreenLabel label={`ROUND ${round + 1} 결과`} />
        <RoundPips total={total} current={round} />
      </div>

      <div className="flex items-center gap-3 mb-6">
        <span className="font-black text-3xl" style={{ fontFamily: "Noto Sans KR, sans-serif", color: "var(--primary)" }}>{word}</span>
        <div
          className="px-3 py-1"
          style={{ border: "1px solid #ffe60033", backgroundColor: "#ffe60011", fontFamily: "JetBrains Mono, monospace", fontSize: "13px", color: "var(--primary)" }}
        >
          싱크 {syncScore}점
        </div>
      </div>

      <div className="w-full grid grid-cols-3 gap-3 mb-5">
        {INITIAL_PLAYERS.map((player, i) => {
          const color = PLAYER_COLORS[i];
          const score = scores[i];
          const isBest = score === maxScore;
          const isWorst = i === worstIdx && score !== maxScore;
          return (
            <div
              key={player.id}
              className="flex flex-col items-center p-5 relative"
              style={{
                border: `1px solid ${isBest ? `${color}66` : isWorst ? "#ff2d7844" : "var(--border)"}`,
                backgroundColor: isBest ? `${color}0a` : isWorst ? "#ff2d7806" : "var(--card)",
              }}
            >
              {isWorst && (
                <div
                  className="absolute -top-3 left-1/2 -translate-x-1/2 px-2 py-0.5 text-xs font-bold"
                  style={{
                    fontFamily: "JetBrains Mono, monospace",
                    fontSize: "9px",
                    backgroundColor: "#ff2d78",
                    color: "#fff",
                    letterSpacing: "0.08em",
                    whiteSpace: "nowrap",
                  }}
                >
                  AI 주목 👀
                </div>
              )}
              <div className="w-16 h-16 mb-4">
                <PoseStickFigure variant={(round + i) % 5} color={color} />
              </div>
              <span className="font-bold text-xs mb-2" style={{ fontFamily: "JetBrains Mono, monospace", color, letterSpacing: "0.1em" }}>
                {player.name}
              </span>
              <span className="font-black text-3xl" style={{ fontFamily: "JetBrains Mono, monospace", color: isBest ? color : "var(--foreground)" }}>
                {score}
              </span>
              {isBest && (
                <span className="mt-1 text-xs" style={{ fontFamily: "JetBrains Mono, monospace", color }}>BEST ✨</span>
              )}
              {isWorst && (
                <span className="mt-1 text-xs" style={{ fontFamily: "JetBrains Mono, monospace", color: "#ff2d78" }}>MY WAY 🤷</span>
              )}
            </div>
          );
        })}
      </div>

      {/* LLM round comment */}
      <AnimatePresence>
        {commentVisible && (
          <motion.div
            initial={{ opacity: 0, y: 10, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.35, ease: "easeOut" }}
            className="w-full mb-6 p-4"
            style={{ border: `1px solid ${toneStyle.border}`, backgroundColor: toneStyle.bg }}
          >
            <div className="flex items-center gap-2 mb-2.5">
              <div
                className="px-2 py-0.5 flex items-center gap-1.5"
                style={{ backgroundColor: "#1e1e2a", border: "1px solid #333344", borderRadius: "2px" }}
              >
                <div className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ backgroundColor: toneStyle.dot }} />
                <span style={{ fontFamily: "JetBrains Mono, monospace", fontSize: "9px", color: "#888899" }}>
                  ON-DEVICE LLM — {toneStyle.label}
                </span>
              </div>
              <span style={{ fontSize: "14px" }}>{toneStyle.icon}</span>
            </div>
            <p style={{ fontFamily: "Noto Sans KR, sans-serif", fontSize: "14px", color: "#ddddee", lineHeight: "1.7" }}>
              {comment.text}
            </p>
          </motion.div>
        )}
      </AnimatePresence>

      <button
        onClick={onNext}
        className="px-10 py-3.5 font-black flex items-center gap-3 transition-opacity hover:opacity-80"
        style={{
          fontFamily: "Noto Sans KR, sans-serif",
          backgroundColor: isLast ? "var(--primary)" : "var(--secondary)",
          color: isLast ? "#0a0a0f" : "var(--foreground)",
          border: `1px solid ${isLast ? "var(--primary)" : "var(--border)"}`,
          cursor: "pointer",
        }}
      >
        {isLast ? (
          <><Trophy size={18} /> 최종 결과 보기</>
        ) : (
          <>다음 라운드 <ArrowRight size={16} /></>
        )}
      </button>
    </div>
  );
}

// ── SCREEN 07: FINAL RESULTS ──────────────────────────────────────────────────

const LLM_COMMENTS: Record<number, string> = {
  1: "Player 2는 5라운드 내내 일관된 자세를 유지해 가장 안정적인 포즈 표현력을 보여줬습니다. Player 1은 상체 동작이 풍부했고, Player 3은 독창적이었지만 팀 싱크에서 아쉬운 모습을 보였습니다.",
  2: "Player 3은 순위는 낮았지만 개성 있는 표현이 인상적이었습니다. 다음 게임에선 팀원의 포즈를 살짝 더 참고해보세요!",
  3: "세 플레이어 모두 스포츠 주제에서 활발한 동작을 보여줬습니다. 전반적으로 팀 싱크가 높아 이구동성 고수 팀이라 할 수 있습니다.",
};

function FinalResultsScreen({ topic, roundScores, onReset }: {
  topic: Topic;
  roundScores: RoundScore[];
  onReset: () => void;
}) {
  const [tab, setTab] = useState<"overview" | "leaderboard">("overview");

  const totalScores = [0, 1, 2].map((i) =>
    Math.round(roundScores.reduce((sum, r) => sum + r.scores[i], 0) / roundScores.length)
  ) as [number, number, number];

  const avgSync = Math.round(roundScores.reduce((sum, r) => sum + r.syncScore, 0) / roundScores.length);

  const ranked = [0, 1, 2]
    .map((i) => ({ playerIdx: i, score: totalScores[i] }))
    .sort((a, b) => b.score - a.score);

  const medalColors = ["#FFD700", "#C0C0C0", "#CD7F32"];

  // fake leaderboard history
  const leaderboard = [
    { session: "2025-01-15 오후 3시", topic: "스포츠", sync: 81, scores: [88, 85, 70] },
    { session: "2025-01-14 오후 7시", topic: "감정 표현", sync: 74, scores: [79, 76, 68] },
    { session: "2025-01-13 오후 2시", topic: "직업", sync: 68, scores: [72, 65, 67] },
    { session: "오늘 현재", topic: topic.label, sync: avgSync, scores: totalScores, current: true },
  ].sort((a, b) => b.sync - a.sync);

  return (
    <div className="flex flex-col h-full p-8 max-w-5xl mx-auto w-full overflow-y-auto">
      <ScreenLabel label="SCREEN 07 — 최종 결과" />

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="font-black text-3xl" style={{ fontFamily: "Noto Sans KR, sans-serif" }}>
            {topic.emoji} {topic.label} — 최종 결과
          </h2>
          <p style={{ fontFamily: "JetBrains Mono, monospace", fontSize: "12px", color: "#666677", marginTop: "4px" }}>
            {roundScores.length}라운드 완료
          </p>
        </div>
        <div
          className="flex flex-col items-end"
          style={{ border: "1px solid #ffe60033", backgroundColor: "#ffe60008", padding: "12px 20px" }}
        >
          <span style={{ fontFamily: "JetBrains Mono, monospace", fontSize: "10px", color: "#888899", letterSpacing: "0.15em" }}>
            평균 이구동성
          </span>
          <span className="font-black" style={{ fontFamily: "JetBrains Mono, monospace", fontSize: "48px", color: "var(--primary)", lineHeight: 1.1 }}>
            {avgSync}
          </span>
        </div>
      </div>

      {/* Tab switcher */}
      <div className="flex mb-6 border-b" style={{ borderColor: "var(--border)" }}>
        {[
          { key: "overview" as const, label: "플레이어 분석" },
          { key: "leaderboard" as const, label: "리더보드" },
        ].map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className="px-6 py-3 font-bold text-sm transition-colors"
            style={{
              fontFamily: "Noto Sans KR, sans-serif",
              borderBottom: `2px solid ${tab === key ? "var(--primary)" : "transparent"}`,
              color: tab === key ? "var(--primary)" : "#666677",
              backgroundColor: "transparent",
              border: "none",
              borderBottom: `2px solid ${tab === key ? "var(--primary)" : "transparent"}`,
              cursor: "pointer",
              marginBottom: "-1px",
            }}
          >
            {label}
          </button>
        ))}
      </div>

      <AnimatePresence mode="wait">
        {tab === "overview" && (
          <motion.div key="overview" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            {/* Player podium */}
            <div className="grid grid-cols-3 gap-4 mb-6">
              {ranked.map(({ playerIdx, score }, rankIdx) => {
                const color = PLAYER_COLORS[playerIdx];
                return (
                  <div
                    key={playerIdx}
                    className="flex flex-col items-center p-6"
                    style={{
                      border: `1px solid ${rankIdx === 0 ? `${color}66` : "var(--border)"}`,
                      backgroundColor: rankIdx === 0 ? `${color}0a` : "var(--card)",
                      order: rankIdx === 0 ? -1 : rankIdx,
                    }}
                  >
                    {rankIdx === 0 && (
                      <div className="mb-2">
                        <Trophy size={20} style={{ color: medalColors[0] }} />
                      </div>
                    )}
                    <Medal size={16} style={{ color: medalColors[rankIdx], marginBottom: "8px" }} />
                    <span className="font-bold text-xs mb-1" style={{ fontFamily: "JetBrains Mono, monospace", color, letterSpacing: "0.1em" }}>
                      PLAYER {playerIdx + 1}
                    </span>
                    <span className="font-black" style={{ fontFamily: "JetBrains Mono, monospace", fontSize: "52px", color, lineHeight: 1 }}>
                      {score}
                    </span>
                    <span className="mt-1 text-xs" style={{ fontFamily: "JetBrains Mono, monospace", color: "#666677" }}>평균 점수</span>
                    {/* Round-by-round bars */}
                    <div className="w-full mt-4 space-y-1.5">
                      {roundScores.map((r, ri) => (
                        <div key={ri} className="flex items-center gap-2">
                          <span style={{ fontFamily: "JetBrains Mono, monospace", fontSize: "9px", color: "#444455", width: "14px" }}>
                            R{ri + 1}
                          </span>
                          <div className="flex-1 h-1.5 rounded-sm" style={{ backgroundColor: "#1e1e2a" }}>
                            <div
                              className="h-full rounded-sm"
                              style={{ width: `${r.scores[playerIdx]}%`, backgroundColor: `${color}88` }}
                            />
                          </div>
                          <span style={{ fontFamily: "JetBrains Mono, monospace", fontSize: "9px", color: "#555566", width: "24px", textAlign: "right" }}>
                            {r.scores[playerIdx]}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* LLM Commentary */}
            <div className="p-5 mb-6" style={{ border: "1px solid var(--border)", backgroundColor: "var(--card)" }}>
              <div className="flex items-center gap-2 mb-3">
                <div className="px-2 py-0.5" style={{ backgroundColor: "#1e1e2a", border: "1px solid #333344", borderRadius: "2px" }}>
                  <span style={{ fontFamily: "JetBrains Mono, monospace", fontSize: "9px", color: "#888899" }}>ON-DEVICE LLM</span>
                </div>
                <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: "#00e676" }} />
              </div>
              <p className="leading-relaxed" style={{ fontFamily: "Noto Sans KR, sans-serif", fontSize: "15px", color: "#ccccdd" }}>
                {LLM_COMMENTS[ranked[0].playerIdx + 1]}
              </p>
            </div>
          </motion.div>
        )}

        {tab === "leaderboard" && (
          <motion.div key="leaderboard" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <div className="mb-4" style={{ border: "1px solid var(--border)" }}>
              {/* Table header */}
              <div
                className="grid px-5 py-3"
                style={{
                  gridTemplateColumns: "2fr 1fr 1fr 1fr 1fr 1fr",
                  borderBottom: "1px solid var(--border)",
                  backgroundColor: "#0d0d14",
                }}
              >
                {["세션", "주제", "싱크", "P1", "P2", "P3"].map((h) => (
                  <span key={h} style={{ fontFamily: "JetBrains Mono, monospace", fontSize: "10px", color: "#555566", letterSpacing: "0.1em" }}>
                    {h}
                  </span>
                ))}
              </div>
              {leaderboard.map((row, ri) => (
                <div
                  key={ri}
                  className="grid items-center px-5 py-4"
                  style={{
                    gridTemplateColumns: "2fr 1fr 1fr 1fr 1fr 1fr",
                    borderBottom: ri < leaderboard.length - 1 ? "1px solid var(--border)" : "none",
                    backgroundColor: (row as any).current ? "#ffe60006" : "transparent",
                  }}
                >
                  <div className="flex items-center gap-2">
                    {ri === 0 && <Trophy size={12} style={{ color: "#FFD700" }} />}
                    <span style={{
                      fontFamily: "JetBrains Mono, monospace",
                      fontSize: "11px",
                      color: (row as any).current ? "var(--primary)" : "#888899",
                    }}>
                      {row.session}
                    </span>
                    {(row as any).current && (
                      <span style={{ fontFamily: "JetBrains Mono, monospace", fontSize: "9px", color: "var(--primary)", border: "1px solid #ffe60044", padding: "0 4px" }}>
                        NOW
                      </span>
                    )}
                  </div>
                  <span style={{ fontFamily: "Noto Sans KR, sans-serif", fontSize: "12px", color: "#ccccdd" }}>{row.topic}</span>
                  <span className="font-bold" style={{
                    fontFamily: "JetBrains Mono, monospace",
                    fontSize: "14px",
                    color: ri === 0 ? "#FFD700" : (row as any).current ? "var(--primary)" : "var(--foreground)",
                  }}>
                    {row.sync}
                  </span>
                  {[0, 1, 2].map((pi) => (
                    <span key={pi} style={{ fontFamily: "JetBrains Mono, monospace", fontSize: "12px", color: PLAYER_COLORS[pi] }}>
                      {row.scores[pi]}
                    </span>
                  ))}
                </div>
              ))}
            </div>
            <p style={{ fontFamily: "JetBrains Mono, monospace", fontSize: "11px", color: "#444455", textAlign: "right" }}>
              높을수록 더 잘 맞은 팀
            </p>
          </motion.div>
        )}
      </AnimatePresence>

      <button
        onClick={onReset}
        className="w-full py-4 flex items-center justify-center gap-3 font-black text-base mt-6 transition-opacity hover:opacity-80"
        style={{ fontFamily: "Noto Sans KR, sans-serif", backgroundColor: "var(--secondary)", color: "var(--foreground)", border: "1px solid var(--border)", cursor: "pointer" }}
      >
        <RotateCcw size={18} /> 다시 하기
      </button>
    </div>
  );
}

// ── NAV BAR ────────────────────────────────────────────────────────────────────

const SCREEN_META: { key: Screen; label: string }[] = [
  { key: "lobby",        label: "대기방" },
  { key: "topic-select", label: "주제 선택" },
  { key: "round-word",   label: "제시어" },
  { key: "countdown",    label: "카운트다운" },
  { key: "capture",      label: "포즈 캡처" },
  { key: "round-result", label: "라운드 결과" },
  { key: "final-results",label: "최종 결과" },
];

function NavBar({ current, onJump }: { current: Screen; onJump: (s: Screen) => void }) {
  const currentIdx = SCREEN_META.findIndex((s) => s.key === current);
  return (
    <div className="flex items-center gap-0 border-b flex-shrink-0 overflow-x-auto px-4"
      style={{ borderColor: "var(--border)", backgroundColor: "#0d0d14" }}>
      {SCREEN_META.map(({ key, label }, i) => {
        const active = current === key;
        const past = currentIdx > i;
        return (
          <button
            key={key}
            onClick={() => onJump(key)}
            className="flex items-center gap-1.5 px-4 py-3.5 whitespace-nowrap transition-colors"
            style={{
              fontFamily: "JetBrains Mono, monospace", fontSize: "10px",
              color: active ? "var(--primary)" : past ? "#555566" : "#2a2a3a",
              border: "none",
              borderBottom: `2px solid ${active ? "var(--primary)" : "transparent"}`,
              backgroundColor: "transparent",
              cursor: "pointer",
              letterSpacing: "0.08em",
            }}
          >
            <span style={{ color: active ? "var(--primary)" : past ? "#3a3a4a" : "#1e1e2a" }}>
              {String(i + 1).padStart(2, "0")}
            </span>
            {label}
          </button>
        );
      })}
      <div className="flex-1" />
      <span style={{ fontFamily: "JetBrains Mono, monospace", fontSize: "9px", color: "#2a2a3a", letterSpacing: "0.1em", padding: "0 12px" }}>
        WIREFRAME
      </span>
    </div>
  );
}

// ── ROOT ───────────────────────────────────────────────────────────────────────

export default function App() {
  const [screen, setScreen] = useState<Screen>("lobby");
  const [selectedTopic, setSelectedTopic] = useState<Topic>(TOPICS[0]);
  const [currentRound, setCurrentRound] = useState(0);
  const [roundScores, setRoundScores] = useState<RoundScore[]>([]);

  const TOTAL_ROUNDS = selectedTopic.words.length;
  const currentWord = selectedTopic.words[currentRound] ?? "";

  function commitRoundScore() {
    const scores = fakeScores(currentRound);
    const syncScore = fakeSyncScore(scores);
    setRoundScores((prev) => [
      ...prev.filter((r) => r.round !== currentRound),
      { round: currentRound, word: currentWord, scores, syncScore },
    ]);
  }

  function handleTopicSelect(topic: Topic) {
    setSelectedTopic(topic);
    setCurrentRound(0);
    setRoundScores([]);
    setScreen("round-word");
  }

  function handleRoundResultNext() {
    if (currentRound < TOTAL_ROUNDS - 1) {
      setCurrentRound((r) => r + 1);
      setScreen("round-word");
    } else {
      setScreen("final-results");
    }
  }

  function handleReset() {
    setCurrentRound(0);
    setRoundScores([]);
    setScreen("lobby");
  }

  function handleJump(s: Screen) {
    if (s === "round-word" || s === "countdown" || s === "capture" || s === "round-result") {
      setCurrentRound(0);
      if (roundScores.length === 0) {
        const scores = fakeScores(0);
        setRoundScores([{ round: 0, word: selectedTopic.words[0], scores, syncScore: fakeSyncScore(scores) }]);
      }
    }
    setScreen(s);
  }

  const currentRoundData = roundScores.find((r) => r.round === currentRound);

  return (
    <div className="flex flex-col h-screen overflow-hidden" style={{ fontFamily: "Noto Sans KR, sans-serif", backgroundColor: "var(--background)" }}>
      <NavBar current={screen} onJump={handleJump} />

      <div className="flex-1 overflow-y-auto">
        <AnimatePresence mode="wait">
          <motion.div
            key={`${screen}-${currentRound}`}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.18 }}
            className="h-full"
          >
            {screen === "lobby" && (
              <LobbyScreen onStart={() => setScreen("topic-select")} />
            )}
            {screen === "topic-select" && (
              <TopicSelectScreen onSelect={handleTopicSelect} />
            )}
            {screen === "round-word" && (
              <RoundWordScreen
                topic={selectedTopic}
                word={currentWord}
                round={currentRound}
                total={TOTAL_ROUNDS}
                onNext={() => setScreen("countdown")}
              />
            )}
            {screen === "countdown" && (
              <CountdownScreen
                round={currentRound}
                total={TOTAL_ROUNDS}
                onNext={() => setScreen("capture")}
              />
            )}
            {screen === "capture" && (
              <CaptureScreen
                round={currentRound}
                total={TOTAL_ROUNDS}
                word={currentWord}
                onNext={() => { commitRoundScore(); setScreen("round-result"); }}
              />
            )}
            {screen === "round-result" && currentRoundData && (
              <RoundResultScreen
                round={currentRound}
                total={TOTAL_ROUNDS}
                word={currentRoundData.word}
                scores={currentRoundData.scores}
                syncScore={currentRoundData.syncScore}
                onNext={handleRoundResultNext}
              />
            )}
            {screen === "final-results" && (
              <FinalResultsScreen
                topic={selectedTopic}
                roundScores={roundScores.length > 0 ? roundScores : selectedTopic.words.map((w, i) => {
                  const scores = fakeScores(i);
                  return { round: i, word: w, scores, syncScore: fakeSyncScore(scores) };
                })}
                onReset={handleReset}
              />
            )}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}
