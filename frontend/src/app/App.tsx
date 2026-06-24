import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "motion/react";
import {
  Wifi, WifiOff, CheckCircle, Trophy, ArrowRight,
  RotateCcw, ChevronRight, Zap, Star, Medal, Flame
} from "lucide-react";

// ── TYPES ──────────────────────────────────────────────────────────────────────

type Screen = "lobby" | "topic-select" | "round-word" | "countdown" | "capture" | "round-result" | "final-results";

type Topic = { id: string; label: string; emoji: string; color: string; words: string[] };

type RoundScore = { round: number; word: string; scores: [number, number, number]; syncScore: number };

// ── DATA ───────────────────────────────────────────────────────────────────────

const TOPICS: Topic[] = [
  { id: "sports",  label: "스포츠",    emoji: "⚽", color: "#00e5ff", words: ["골프", "농구", "수영", "태권도", "야구"] },
  { id: "emotion", label: "감정 표현", emoji: "😄", color: "#ff2d78", words: ["기쁨", "분노", "슬픔", "놀람", "지루함"] },
  { id: "daily",   label: "일상 생활", emoji: "🏠", color: "#ffe600", words: ["월급날", "지각", "장보기", "낮잠", "청소"] },
  { id: "job",     label: "직업",      emoji: "💼", color: "#b46eff", words: ["의사", "소방관", "요리사", "선생님", "경찰"] },
  { id: "animal",  label: "동물",      emoji: "🦁", color: "#00ff99", words: ["기린", "펭귄", "원숭이", "독수리", "악어"] },
];

const P_COLORS = ["#ffe600", "#ff2d78", "#00e5ff"];
const P_NAMES  = ["PLAYER 1", "PLAYER 2", "PLAYER 3"];
const P_DEVICE = ["raspi-001", "raspi-002", "raspi-003"];

function fakeScores(round: number): [number, number, number] {
  return ([[82,79,61],[74,88,71],[90,65,83],[77,80,77],[68,92,74]] as [number,number,number][])[round % 5];
}
function avgSync(s: [number,number,number]) { return Math.round((s[0]+s[1]+s[2])/3); }

// ── ROUND COMMENTS ─────────────────────────────────────────────────────────────

type RoundComment = { text: string; tone: "roast"|"hype"|"neutral" };
const COMMENTS: Record<string, RoundComment[]> = {
  "0-2": [{ tone:"roast",   text:"아… Player 3, 혹시 '골프'를 골골 소리 내는 걸로 이해하신 건가요? 팔은 어디 갔죠?" }],
  "1-0": [{ tone:"roast",   text:"Player 1, 농구 배팅 자세가 마치 모기를 잡으려는 것처럼 보였습니다. 오늘 모기 많나요?" }],
  "2-1": [{ tone:"roast",   text:"Player 2, 수영을 땅에서 하셨군요. 물 없이도 이렇게 할 수 있다니… 새로운 종목 탄생인가요?" }],
  "3-0": [{ tone:"roast",   text:"Player 1, 태권도 발차기인지 넘어지는 건지 AI가 0.3초 고민했습니다. 결론: 후자에 가깝습니다." }],
  "4-1": [{ tone:"hype",    text:"마지막 라운드! Player 1과 3이 야구 투수 폼까지 맞췄네요. Player 2는 아마 타자 포지션을 혼자 맡은 것 같습니다." }],
};
function getRoundComment(round: number, scores: [number,number,number]): RoundComment {
  const min = Math.min(...scores);
  const wi  = scores.indexOf(min);
  const key = `${round}-${wi}`;
  return (COMMENTS[key] ?? [{ tone:"neutral" as const, text:"세 명 모두 나름의 개성을 보여줬습니다. AI는 최선을 다해 분석했고, 팀도 최선을 다했겠죠?" }])[0];
}

// ── UTILS ──────────────────────────────────────────────────────────────────────

function useCountUp(target: number, duration = 1200) {
  const [val, setVal] = useState(0);
  useEffect(() => {
    let start = 0; const step = 16;
    const inc = target / (duration / step);
    const id = setInterval(() => {
      start += inc;
      if (start >= target) { setVal(target); clearInterval(id); }
      else setVal(Math.floor(start));
    }, step);
    return () => clearInterval(id);
  }, [target, duration]);
  return val;
}

// ── DESIGN PRIMITIVES ──────────────────────────────────────────────────────────

function Glow({ color, size = 300, opacity = 0.12 }: { color: string; size?: number; opacity?: number }) {
  return (
    <div className="absolute pointer-events-none" style={{
      width: size, height: size,
      borderRadius: "50%",
      background: `radial-gradient(circle, ${color} 0%, transparent 70%)`,
      opacity, filter: "blur(40px)",
      transform: "translate(-50%, -50%)",
    }} />
  );
}

function NeonBorder({ color, children, className = "", style = {} }: { color: string; children: React.ReactNode; className?: string; style?: React.CSSProperties }) {
  return (
    <div className={`relative ${className}`} style={{
      border: `1px solid ${color}55`,
      boxShadow: `0 0 20px ${color}15, inset 0 0 20px ${color}05`,
      ...style,
    }}>
      {children}
    </div>
  );
}

function CornerDeco({ color }: { color: string }) {
  return <>
    {[["top-0 left-0","border-t-2 border-l-2"],["top-0 right-0","border-t-2 border-r-2"],
      ["bottom-0 left-0","border-b-2 border-l-2"],["bottom-0 right-0","border-b-2 border-r-2"]
    ].map(([pos, bord], i) => (
      <div key={i} className={`absolute w-4 h-4 ${pos} ${bord}`} style={{ borderColor: color, margin: "-1px" }} />
    ))}
  </>;
}

function RoundPips({ total, current }: { total: number; current: number }) {
  return (
    <div className="flex items-center gap-1.5">
      {Array.from({length: total}).map((_,i) => (
        <motion.div key={i} layout className="h-1 rounded-full" style={{
          width: i === current ? 24 : 8,
          backgroundColor: i < current ? "#ffffff55" : i === current ? "var(--primary)" : "#ffffff1a",
        }} transition={{ duration: 0.3 }} />
      ))}
    </div>
  );
}

function ScanlineOverlay() {
  return (
    <div className="absolute inset-0 pointer-events-none" style={{
      backgroundImage: "repeating-linear-gradient(0deg, transparent, transparent 3px, rgba(0,0,0,0.08) 3px, rgba(0,0,0,0.08) 4px)",
      zIndex: 1,
    }} />
  );
}

function GridBg({ color = "#ffffff", opacity = 0.03 }: { color?: string; opacity?: number }) {
  return (
    <div className="absolute inset-0 pointer-events-none" style={{
      backgroundImage: `linear-gradient(${color}${Math.round(opacity*255).toString(16).padStart(2,"0")} 1px, transparent 1px), linear-gradient(90deg, ${color}${Math.round(opacity*255).toString(16).padStart(2,"0")} 1px, transparent 1px)`,
      backgroundSize: "40px 40px",
    }} />
  );
}

// ── POSE STICK FIGURES ─────────────────────────────────────────────────────────

const POSES = [
  // arms-up
  (c: string) => <g><circle cx="50" cy="16" r="9" fill="none" stroke={c} strokeWidth="3.5" strokeLinecap="round"/><line x1="50" y1="25" x2="50" y2="62" stroke={c} strokeWidth="3.5" strokeLinecap="round"/><line x1="50" y1="36" x2="22" y2="18" stroke={c} strokeWidth="3.5" strokeLinecap="round"/><line x1="50" y1="36" x2="78" y2="18" stroke={c} strokeWidth="3.5" strokeLinecap="round"/><line x1="50" y1="62" x2="32" y2="90" stroke={c} strokeWidth="3.5" strokeLinecap="round"/><line x1="50" y1="62" x2="68" y2="90" stroke={c} strokeWidth="3.5" strokeLinecap="round"/></g>,
  // T-pose
  (c: string) => <g><circle cx="50" cy="16" r="9" fill="none" stroke={c} strokeWidth="3.5" strokeLinecap="round"/><line x1="50" y1="25" x2="50" y2="62" stroke={c} strokeWidth="3.5" strokeLinecap="round"/><line x1="50" y1="38" x2="12" y2="38" stroke={c} strokeWidth="3.5" strokeLinecap="round"/><line x1="50" y1="38" x2="88" y2="38" stroke={c} strokeWidth="3.5" strokeLinecap="round"/><line x1="50" y1="62" x2="34" y2="90" stroke={c} strokeWidth="3.5" strokeLinecap="round"/><line x1="50" y1="62" x2="66" y2="90" stroke={c} strokeWidth="3.5" strokeLinecap="round"/></g>,
  // one-arm-up
  (c: string) => <g><circle cx="50" cy="16" r="9" fill="none" stroke={c} strokeWidth="3.5" strokeLinecap="round"/><line x1="50" y1="25" x2="50" y2="62" stroke={c} strokeWidth="3.5" strokeLinecap="round"/><line x1="50" y1="36" x2="24" y2="20" stroke={c} strokeWidth="3.5" strokeLinecap="round"/><line x1="50" y1="36" x2="72" y2="48" stroke={c} strokeWidth="3.5" strokeLinecap="round"/><line x1="50" y1="62" x2="28" y2="86" stroke={c} strokeWidth="3.5" strokeLinecap="round"/><line x1="50" y1="62" x2="64" y2="90" stroke={c} strokeWidth="3.5" strokeLinecap="round"/></g>,
  // crouch
  (c: string) => <g><circle cx="50" cy="22" r="9" fill="none" stroke={c} strokeWidth="3.5" strokeLinecap="round"/><line x1="50" y1="31" x2="50" y2="60" stroke={c} strokeWidth="3.5" strokeLinecap="round"/><line x1="50" y1="40" x2="26" y2="52" stroke={c} strokeWidth="3.5" strokeLinecap="round"/><line x1="26" y1="52" x2="34" y2="34" stroke={c} strokeWidth="3.5" strokeLinecap="round"/><line x1="50" y1="40" x2="74" y2="52" stroke={c} strokeWidth="3.5" strokeLinecap="round"/><line x1="74" y1="52" x2="66" y2="34" stroke={c} strokeWidth="3.5" strokeLinecap="round"/><line x1="50" y1="60" x2="30" y2="82" stroke={c} strokeWidth="3.5" strokeLinecap="round"/><line x1="50" y1="60" x2="70" y2="82" stroke={c} strokeWidth="3.5" strokeLinecap="round"/></g>,
  // kick
  (c: string) => <g><circle cx="50" cy="16" r="9" fill="none" stroke={c} strokeWidth="3.5" strokeLinecap="round"/><line x1="50" y1="25" x2="50" y2="62" stroke={c} strokeWidth="3.5" strokeLinecap="round"/><line x1="50" y1="36" x2="20" y2="26" stroke={c} strokeWidth="3.5" strokeLinecap="round"/><line x1="20" y1="26" x2="14" y2="10" stroke={c} strokeWidth="3.5" strokeLinecap="round"/><line x1="50" y1="36" x2="76" y2="28" stroke={c} strokeWidth="3.5" strokeLinecap="round"/><line x1="76" y1="28" x2="84" y2="12" stroke={c} strokeWidth="3.5" strokeLinecap="round"/><line x1="50" y1="62" x2="28" y2="88" stroke={c} strokeWidth="3.5" strokeLinecap="round"/><line x1="50" y1="62" x2="78" y2="72" stroke={c} strokeWidth="3.5" strokeLinecap="round"/><line x1="78" y1="72" x2="90" y2="60" stroke={c} strokeWidth="3.5" strokeLinecap="round"/></g>,
];

function StickFigure({ variant = 0, color = "#ffe600", size = 80, glow = true }: { variant?: number; color?: string; size?: number; glow?: boolean }) {
  return (
    <svg viewBox="0 0 100 100" width={size} height={size} style={glow ? { filter: `drop-shadow(0 0 8px ${color}cc)` } : {}}>
      {POSES[variant % POSES.length](color)}
    </svg>
  );
}

// ── SCREEN: LOBBY ──────────────────────────────────────────────────────────────

function LobbyScreen({ onStart }: { onStart: () => void }) {
  const [tick, setTick] = useState(0);
  useEffect(() => { const id = setInterval(() => setTick(t=>t+1), 2000); return () => clearInterval(id); }, []);

  return (
    <div className="relative flex flex-col h-full items-center justify-center overflow-hidden" style={{ background: "#080810" }}>
      <GridBg opacity={0.04} />
      <div className="absolute top-1/3 left-1/2" style={{ transform:"translate(-50%,-50%)" }}>
        <Glow color="#ffe600" size={600} opacity={0.06} />
      </div>

      {/* Title */}
      <motion.div initial={{ opacity:0, y:-30 }} animate={{ opacity:1, y:0 }} transition={{ duration:0.7, ease:"easeOut" }} className="text-center mb-14">
        <div className="flex items-center justify-center gap-3 mb-3">
          <div className="h-px w-16" style={{ background:"linear-gradient(90deg,transparent,#ffe600)" }} />
          <span style={{ fontFamily:"JetBrains Mono,monospace", fontSize:11, color:"#ffe60088", letterSpacing:"0.25em" }}>POSE SYNC GAME</span>
          <div className="h-px w-16" style={{ background:"linear-gradient(90deg,#ffe600,transparent)" }} />
        </div>
        <h1 style={{
          fontFamily:"Noto Sans KR,sans-serif", fontSize:"clamp(56px,8vw,88px)",
          fontWeight:900, letterSpacing:"-0.03em", lineHeight:1,
          background:"linear-gradient(135deg,#ffe600 0%,#ffaa00 50%,#ffe600 100%)",
          WebkitBackgroundClip:"text", WebkitTextFillColor:"transparent",
          filter:"drop-shadow(0 0 30px #ffe60055)",
        }}>이구동성</h1>
        <p className="mt-4" style={{ fontFamily:"Noto Sans KR,sans-serif", fontSize:16, color:"#ffffff66" }}>
          3명이 같은 포즈를 취하는 리얼타임 싱크 게임
        </p>
      </motion.div>

      {/* Player cards */}
      <div className="grid grid-cols-3 gap-5 mb-12 w-full px-8" style={{ maxWidth:860 }}>
        {P_NAMES.map((name, i) => (
          <motion.div key={i} initial={{ opacity:0, y:20 }} animate={{ opacity:1, y:0 }} transition={{ delay:0.2+i*0.1, duration:0.5 }}>
            <NeonBorder color={P_COLORS[i]} style={{ backgroundColor:"#0d0d18" }}>
              <CornerDeco color={P_COLORS[i]} />
              {/* camera view */}
              <div className="relative flex items-center justify-center" style={{ height:140, backgroundColor:"#050508" }}>
                <ScanlineOverlay />
                <motion.div animate={{ opacity:[0.4,1,0.4] }} transition={{ duration:2, repeat:Infinity, delay:i*0.6 }}>
                  <StickFigure variant={(tick+i)%5} color={P_COLORS[i]} size={72} />
                </motion.div>
                {/* REC badge */}
                <div className="absolute top-2.5 left-3 flex items-center gap-1.5">
                  <motion.div className="w-2 h-2 rounded-full" style={{ backgroundColor:"#ff2d2d" }}
                    animate={{ opacity:[1,0.2,1] }} transition={{ duration:1.2, repeat:Infinity }} />
                  <span style={{ fontFamily:"JetBrains Mono,monospace", fontSize:9, color:"#ff2d2d88", letterSpacing:"0.15em" }}>LIVE</span>
                </div>
                {/* DETECTED badge */}
                <div className="absolute bottom-2.5 right-3 px-2 py-0.5 flex items-center gap-1" style={{ backgroundColor:"#00e67611", border:"1px solid #00e67633" }}>
                  <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor:"#00e676" }} />
                  <span style={{ fontFamily:"JetBrains Mono,monospace", fontSize:9, color:"#00e676" }}>DETECTED</span>
                </div>
              </div>
              {/* info row */}
              <div className="flex items-center justify-between px-4 py-3">
                <div>
                  <p style={{ fontFamily:"JetBrains Mono,monospace", fontSize:11, fontWeight:700, color:P_COLORS[i], letterSpacing:"0.12em" }}>{name}</p>
                  <p style={{ fontFamily:"JetBrains Mono,monospace", fontSize:9, color:"#ffffff33", marginTop:2 }}>{P_DEVICE[i]}</p>
                </div>
                <div className="flex items-center gap-1.5">
                  <Wifi size={12} style={{ color:"#00e676" }} />
                  <CheckCircle size={12} style={{ color:"#00e676" }} />
                </div>
              </div>
            </NeonBorder>
          </motion.div>
        ))}
      </div>

      {/* Start button */}
      <motion.button
        initial={{ opacity:0, y:10 }} animate={{ opacity:1, y:0 }} transition={{ delay:0.6 }}
        whileHover={{ scale:1.03 }} whileTap={{ scale:0.97 }}
        onClick={onStart}
        className="flex items-center gap-3 px-14 py-5 font-black text-lg"
        style={{
          fontFamily:"Noto Sans KR,sans-serif",
          background:"linear-gradient(135deg,#ffe600,#ffaa00)",
          color:"#080810", border:"none", cursor:"pointer",
          boxShadow:"0 0 40px #ffe60055, 0 8px 32px rgba(0,0,0,0.4)",
          letterSpacing:"0.05em",
        }}
      >
        주제 선택하기 <ArrowRight size={20} />
      </motion.button>

      <p className="mt-4" style={{ fontFamily:"JetBrains Mono,monospace", fontSize:10, color:"#ffffff22", letterSpacing:"0.1em" }}>
        3 / 3 PLAYERS READY
      </p>
    </div>
  );
}

// ── SCREEN: TOPIC SELECT ───────────────────────────────────────────────────────

function TopicSelectScreen({ onSelect }: { onSelect: (t: Topic) => void }) {
  const [hovered, setHovered] = useState<string|null>(null);

  return (
    <div className="relative flex flex-col h-full items-center justify-center overflow-hidden p-8" style={{ background:"#080810" }}>
      <GridBg opacity={0.035} />

      <motion.div initial={{ opacity:0, y:-20 }} animate={{ opacity:1, y:0 }} className="text-center mb-10">
        <p style={{ fontFamily:"JetBrains Mono,monospace", fontSize:11, color:"#ffffff44", letterSpacing:"0.2em", marginBottom:10 }}>STEP 01</p>
        <h2 style={{ fontFamily:"Noto Sans KR,sans-serif", fontSize:"clamp(32px,5vw,52px)", fontWeight:900, letterSpacing:"-0.03em" }}>
          오늘의 주제를 <span style={{ color:"var(--primary)" }}>선택</span>하세요
        </h2>
      </motion.div>

      <div className="w-full space-y-2.5" style={{ maxWidth:680 }}>
        {TOPICS.map((topic, idx) => {
          const isHov = hovered === topic.id;
          return (
            <motion.button
              key={topic.id}
              initial={{ opacity:0, x:-20 }} animate={{ opacity:1, x:0 }} transition={{ delay:0.05*idx }}
              onHoverStart={() => setHovered(topic.id)} onHoverEnd={() => setHovered(null)}
              onClick={() => onSelect(topic)}
              className="w-full flex items-center justify-between px-6 py-4 relative overflow-hidden"
              style={{
                backgroundColor: isHov ? `${topic.color}11` : "#0d0d18",
                border:`1px solid ${isHov ? topic.color+"88" : "#ffffff0f"}`,
                boxShadow: isHov ? `0 0 24px ${topic.color}22` : "none",
                cursor:"pointer",
                transition:"all 0.2s",
              }}
            >
              {isHov && <div className="absolute inset-0 pointer-events-none" style={{ background:`linear-gradient(90deg, ${topic.color}08, transparent)` }} />}
              <div className="flex items-center gap-5">
                <span style={{ fontSize:32 }}>{topic.emoji}</span>
                <div className="text-left">
                  <p style={{ fontFamily:"Noto Sans KR,sans-serif", fontSize:20, fontWeight:900, color: isHov ? topic.color : "#ffffff", letterSpacing:"-0.01em" }}>
                    {topic.label}
                  </p>
                  <p style={{ fontFamily:"JetBrains Mono,monospace", fontSize:11, color:"#ffffff33", marginTop:3 }}>
                    {topic.words.join("  ·  ")}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <div className="flex gap-1">
                  {topic.words.map((_,i) => (
                    <div key={i} className="w-1 h-5 rounded-sm" style={{ backgroundColor: isHov ? `${topic.color}66` : "#ffffff11" }} />
                  ))}
                </div>
                <span style={{ fontFamily:"JetBrains Mono,monospace", fontSize:10, color:"#ffffff33" }}>5 ROUNDS</span>
                <ChevronRight size={16} style={{ color: isHov ? topic.color : "#ffffff22", transition:"color 0.2s" }} />
              </div>
            </motion.button>
          );
        })}
      </div>
    </div>
  );
}

// ── SCREEN: ROUND WORD ─────────────────────────────────────────────────────────

function RoundWordScreen({ topic, word, round, total, onNext }: { topic:Topic; word:string; round:number; total:number; onNext:()=>void }) {
  const [phase, setPhase] = useState<0|1|2>(0);
  useEffect(() => {
    setPhase(0);
    const t1 = setTimeout(() => setPhase(1), 400);
    const t2 = setTimeout(() => setPhase(2), 900);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, [word]);

  return (
    <div className="relative flex flex-col h-full items-center justify-center overflow-hidden" style={{ background:"#080810" }}>
      <GridBg opacity={0.04} />
      <div className="absolute top-1/2 left-1/2" style={{ transform:"translate(-50%,-50%)" }}>
        <Glow color={topic.color} size={500} opacity={0.1} />
      </div>

      {/* Round indicator */}
      <motion.div initial={{ opacity:0 }} animate={{ opacity:1 }} className="absolute top-8 left-0 right-0 flex flex-col items-center gap-3">
        <RoundPips total={total} current={round} />
        <span style={{ fontFamily:"JetBrains Mono,monospace", fontSize:11, color:"#ffffff33", letterSpacing:"0.2em" }}>
          ROUND {round+1} / {total} — {topic.label} {topic.emoji}
        </span>
      </motion.div>

      <div className="relative flex flex-col items-center gap-8">
        <motion.p initial={{ opacity:0 }} animate={{ opacity: phase>=1?1:0 }} transition={{ duration:0.4 }}
          style={{ fontFamily:"JetBrains Mono,monospace", fontSize:13, color:"#ffffff44", letterSpacing:"0.25em" }}>
          이번 라운드 주제
        </motion.p>

        {/* Word reveal box */}
        <div className="relative px-20 py-10" style={{ border:`1px solid ${topic.color}33`, backgroundColor:"#0d0d18" }}>
          <CornerDeco color={topic.color} />
          <AnimatePresence mode="wait">
            <motion.div key={word}
              initial={{ opacity:0, scale:0.7, filter:"blur(20px)" }}
              animate={{ opacity: phase>=2?1:0, scale: phase>=2?1:0.7, filter: phase>=2?"blur(0px)":"blur(20px)" }}
              transition={{ duration:0.5, ease:[0.16,1,0.3,1] }}
            >
              <span style={{
                fontFamily:"Noto Sans KR,sans-serif",
                fontSize:"clamp(60px,10vw,100px)",
                fontWeight:900, letterSpacing:"-0.03em", lineHeight:1,
                color:topic.color,
                textShadow:`0 0 40px ${topic.color}88, 0 0 80px ${topic.color}44`,
              }}>
                {word}
              </span>
            </motion.div>
          </AnimatePresence>
        </div>

        <motion.p initial={{ opacity:0 }} animate={{ opacity: phase>=2?1:0 }} transition={{ delay:0.3 }}
          style={{ fontFamily:"Noto Sans KR,sans-serif", fontSize:16, color:"#ffffff55" }}>
          몸으로 표현하세요
        </motion.p>

        <motion.button
          initial={{ opacity:0, y:10 }} animate={{ opacity: phase>=2?1:0, y: phase>=2?0:10 }} transition={{ delay:0.5 }}
          whileHover={{ scale:1.04 }} whileTap={{ scale:0.96 }}
          onClick={onNext}
          className="flex items-center gap-3 px-12 py-4 font-black"
          style={{
            fontFamily:"Noto Sans KR,sans-serif", fontSize:16,
            background:`linear-gradient(135deg,${topic.color},${topic.color}bb)`,
            color:"#080810", border:"none", cursor:"pointer",
            boxShadow:`0 0 30px ${topic.color}44`,
          }}
        >
          카운트다운 시작 <ArrowRight size={18} />
        </motion.button>
      </div>
    </div>
  );
}

// ── SCREEN: COUNTDOWN ──────────────────────────────────────────────────────────

function CountdownScreen({ topic, round, total, onNext }: { topic:Topic; round:number; total:number; onNext:()=>void }) {
  const [count, setCount] = useState(3);
  const [done, setDone] = useState(false);

  useEffect(() => {
    setCount(3); setDone(false);
    const timers: ReturnType<typeof setTimeout>[] = [];
    timers.push(setTimeout(() => setCount(2), 900));
    timers.push(setTimeout(() => setCount(1), 1800));
    timers.push(setTimeout(() => { setCount(0); setDone(true); }, 2700));
    timers.push(setTimeout(onNext, 3300));
    return () => timers.forEach(clearTimeout);
  }, [round]);

  return (
    <div className="relative flex flex-col h-full items-center justify-center overflow-hidden" style={{ background:"#080810" }}>
      <GridBg opacity={0.04} />
      <AnimatePresence>
        <motion.div key="glow" className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <Glow color={done?"#ff2d78":topic.color} size={800} opacity={done?0.18:0.12} />
        </motion.div>
      </AnimatePresence>

      <div className="absolute top-8 left-0 right-0 flex flex-col items-center gap-3">
        <RoundPips total={total} current={round} />
        <span style={{ fontFamily:"JetBrains Mono,monospace", fontSize:11, color:"#ffffff33", letterSpacing:"0.2em" }}>
          ROUND {round+1} — 준비하세요
        </span>
      </div>

      <div className="flex flex-col items-center gap-6">
        {/* Outer ring */}
        <div className="relative flex items-center justify-center" style={{ width:260, height:260 }}>
          <div className="absolute inset-0 rounded-full" style={{ border:`1px solid ${topic.color}22` }} />
          <div className="absolute inset-5 rounded-full" style={{ border:`1px solid ${topic.color}44` }} />
          <motion.div className="absolute inset-10 rounded-full" style={{ border:`2px solid ${done?"#ff2d78":topic.color}`, boxShadow:`0 0 20px ${done?"#ff2d78":topic.color}55` }} />

          <AnimatePresence mode="wait">
            <motion.span key={done?"go":count}
              initial={{ opacity:0, scale:1.8, filter:"blur(8px)" }}
              animate={{ opacity:1, scale:1, filter:"blur(0px)" }}
              exit={{ opacity:0, scale:0.3, filter:"blur(8px)" }}
              transition={{ duration:0.25, ease:[0.16,1,0.3,1] }}
              style={{
                fontFamily: done ? "Noto Sans KR,sans-serif" : "JetBrains Mono,monospace",
                fontSize: done ? 72 : 120,
                fontWeight:900, lineHeight:1,
                color: done ? "#ff2d78" : topic.color,
                textShadow:`0 0 40px ${done?"#ff2d78":topic.color}`,
              }}
            >
              {done ? "GO!" : count}
            </motion.span>
          </AnimatePresence>
        </div>

        {/* step indicators */}
        <div className="flex gap-3">
          {[3,2,1].map(n => (
            <div key={n} className="w-10 h-10 flex items-center justify-center" style={{
              border:`1px solid ${count<n||done ? `${topic.color}88` : "#ffffff11"}`,
              backgroundColor: count<n||done ? `${topic.color}11` : "transparent",
              fontFamily:"JetBrains Mono,monospace", fontSize:14, fontWeight:700,
              color: count<n||done ? topic.color : "#ffffff22",
            }}>{n}</div>
          ))}
        </div>
      </div>

      <button onClick={onNext} style={{ position:"absolute", bottom:24, fontFamily:"JetBrains Mono,monospace", fontSize:10, color:"#ffffff1a", background:"none", border:"none", cursor:"pointer" }}>
        SKIP →
      </button>
    </div>
  );
}

// ── SCREEN: CAPTURE ────────────────────────────────────────────────────────────

function CaptureScreen({ topic, round, total, word, onNext }: { topic:Topic; round:number; total:number; word:string; onNext:()=>void }) {
  const [phase, setPhase] = useState<"active"|"captured">("active");
  useEffect(() => {
    setPhase("active");
    const t1 = setTimeout(() => setPhase("captured"), 1500);
    const t2 = setTimeout(onNext, 2400);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, [round]);

  return (
    <div className="relative flex flex-col h-full overflow-hidden" style={{ background:"#080810" }}>
      <GridBg opacity={0.035} />

      {/* top bar */}
      <div className="relative z-10 flex items-center justify-between px-8 pt-6 pb-4">
        <div className="flex items-center gap-4">
          <RoundPips total={total} current={round} />
          <span style={{ fontFamily:"JetBrains Mono,monospace", fontSize:11, color:"#ffffff33", letterSpacing:"0.15em" }}>
            ROUND {round+1} — 포즈 캡처
          </span>
        </div>
        <div className="flex items-center gap-3">
          <span style={{ fontFamily:"Noto Sans KR,sans-serif", fontSize:22, fontWeight:900, color:topic.color, textShadow:`0 0 20px ${topic.color}88` }}>{word}</span>
          <div className="flex items-center gap-2 px-3 py-1.5" style={{
            border:`1px solid ${phase==="captured"?"#00e67644":"#ffe60044"}`,
            backgroundColor: phase==="captured"?"#00e67611":"#ffe60011",
          }}>
            <motion.div className="w-2 h-2 rounded-full" style={{ backgroundColor: phase==="captured"?"#00e676":topic.color }}
              animate={phase==="active"?{ opacity:[1,0.2,1] }:{}} transition={{ duration:0.7, repeat:Infinity }} />
            <span style={{ fontFamily:"JetBrains Mono,monospace", fontSize:11, color: phase==="captured"?"#00e676":topic.color }}>
              {phase==="captured"?"CAPTURED":"CAPTURING..."}
            </span>
          </div>
        </div>
      </div>

      {/* player feeds */}
      <div className="flex-1 grid grid-cols-3 gap-4 px-8 pb-8 relative z-10">
        {P_NAMES.map((name, i) => {
          const color = P_COLORS[i];
          return (
            <NeonBorder key={i} color={color} style={{ backgroundColor:"#0a0a12", display:"flex", flexDirection:"column" }}>
              {/* header */}
              <div className="flex items-center justify-between px-4 py-3" style={{ borderBottom:"1px solid #ffffff08" }}>
                <span style={{ fontFamily:"JetBrains Mono,monospace", fontSize:11, fontWeight:700, color, letterSpacing:"0.12em" }}>{name}</span>
                <div className="flex items-center gap-1.5">
                  <motion.div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor:"#ff2d2d" }}
                    animate={{ opacity:[1,0.1,1] }} transition={{ duration:1, repeat:Infinity }} />
                  <span style={{ fontFamily:"JetBrains Mono,monospace", fontSize:9, color:"#ff2d2d66" }}>REC</span>
                </div>
              </div>

              {/* pose view */}
              <div className="flex-1 relative flex items-center justify-center" style={{ backgroundColor:"#05050d", minHeight:180 }}>
                <ScanlineOverlay />
                {/* grid */}
                <div className="absolute inset-0" style={{
                  backgroundImage:`linear-gradient(${color}11 1px,transparent 1px),linear-gradient(90deg,${color}11 1px,transparent 1px)`,
                  backgroundSize:"24px 24px",
                }} />

                {/* joint dots */}
                {phase==="active" && (
                  <div className="absolute inset-0 pointer-events-none">
                    {[[50,18],[50,38],[50,60],[28,36],[72,36],[34,86],[66,86]].map(([x,y],ji) => (
                      <motion.div key={ji} animate={{ scale:[1,1.4,1], opacity:[0.7,1,0.7] }}
                        transition={{ duration:0.8+ji*0.1, repeat:Infinity }}
                        className="absolute w-2 h-2 rounded-full"
                        style={{ left:`${x}%`, top:`${y}%`, transform:"translate(-50%,-50%)", backgroundColor:color, boxShadow:`0 0 6px ${color}` }} />
                    ))}
                  </div>
                )}

                <StickFigure variant={(round+i)%5} color={color} size={90} />

                {phase==="captured" && (
                  <motion.div initial={{ opacity:0 }} animate={{ opacity:1 }}
                    className="absolute inset-0 flex items-center justify-center"
                    style={{ backgroundColor:"#05050dee" }}>
                    <motion.div initial={{ scale:0 }} animate={{ scale:1 }} transition={{ type:"spring", stiffness:300 }}>
                      <CheckCircle size={40} style={{ color:"#00e676", filter:"drop-shadow(0 0 12px #00e676)" }} />
                    </motion.div>
                  </motion.div>
                )}
              </div>

              {/* MediaPipe bar */}
              <div className="flex items-center gap-2 px-4 py-3">
                <span style={{ fontFamily:"JetBrains Mono,monospace", fontSize:9, color:"#ffffff22" }}>MEDIAPIPE POSE</span>
                <div className="flex-1 h-px" style={{ backgroundColor:`${color}22` }} />
                <span style={{ fontFamily:"JetBrains Mono,monospace", fontSize:9, color }}>
                  {phase==="captured"?"✓ 33 pts":"추출 중..."}
                </span>
              </div>
            </NeonBorder>
          );
        })}
      </div>
    </div>
  );
}

// ── SCREEN: ROUND RESULT ───────────────────────────────────────────────────────

const TONE_CFG = {
  roast:   { border:"#ff2d7866", bg:"#ff2d7810", dot:"#ff2d78", label:"AI 독설", icon:"🔥" },
  hype:    { border:"#ffe60066", bg:"#ffe60010", dot:"#ffe600", label:"AI 칭찬", icon:"⚡" },
  neutral: { border:"#ffffff22", bg:"#ffffff08", dot:"#888899", label:"AI 해설", icon:"🤖" },
};

function ScoreBar({ score, color }: { score:number; color:string }) {
  const display = useCountUp(score, 900);
  return (
    <div className="w-full mt-3">
      <div className="w-full h-1.5 rounded-sm" style={{ backgroundColor:"#ffffff0f" }}>
        <motion.div initial={{ width:0 }} animate={{ width:`${score}%` }} transition={{ duration:0.9, ease:"easeOut" }}
          className="h-full rounded-sm" style={{ backgroundColor:color, boxShadow:`0 0 6px ${color}88` }} />
      </div>
      <p className="text-right mt-1" style={{ fontFamily:"JetBrains Mono,monospace", fontSize:9, color:"#ffffff44" }}>{display}</p>
    </div>
  );
}

function RoundResultScreen({ topic, round, total, word, scores, syncScore, onNext }:
  { topic:Topic; round:number; total:number; word:string; scores:[number,number,number]; syncScore:number; onNext:()=>void }) {
  const isLast = round===total-1;
  const [commentVisible, setCommentVisible] = useState(false);
  const comment = getRoundComment(round, scores);
  const toneStyle = TONE_CFG[comment.tone];
  const syncDisplay = useCountUp(syncScore, 1000);

  useEffect(() => {
    setCommentVisible(false);
    const t1 = setTimeout(() => setCommentVisible(true), 700);
    const t2 = setTimeout(onNext, isLast ? 9999999 : 4500);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, [round, isLast]);

  const maxScore = Math.max(...scores);
  const minScore = Math.min(...scores);
  const worstIdx = scores.indexOf(minScore);

  return (
    <div className="relative flex flex-col h-full items-center justify-center overflow-hidden p-8" style={{ background:"#080810" }}>
      <GridBg opacity={0.035} />
      <div className="absolute top-1/2 left-1/2" style={{ transform:"translate(-50%,-50%)" }}>
        <Glow color={topic.color} size={600} opacity={0.07} />
      </div>

      {/* Top */}
      <div className="relative z-10 flex items-center gap-4 mb-8">
        <RoundPips total={total} current={round} />
        <span style={{ fontFamily:"JetBrains Mono,monospace", fontSize:11, color:"#ffffff33", letterSpacing:"0.15em" }}>
          ROUND {round+1} 결과
        </span>
      </div>

      {/* Sync score banner */}
      <motion.div initial={{ opacity:0, y:-16 }} animate={{ opacity:1, y:0 }} transition={{ duration:0.5 }}
        className="relative z-10 flex items-center gap-6 px-10 py-5 mb-8"
        style={{ border:`1px solid ${topic.color}44`, backgroundColor:`${topic.color}08`, boxShadow:`0 0 40px ${topic.color}18` }}>
        <CornerDeco color={topic.color} />
        <span style={{ fontFamily:"Noto Sans KR,sans-serif", fontSize:28, fontWeight:900, color:topic.color, textShadow:`0 0 20px ${topic.color}88` }}>{word}</span>
        <div className="w-px h-10" style={{ backgroundColor:topic.color+"33" }} />
        <div>
          <p style={{ fontFamily:"JetBrains Mono,monospace", fontSize:10, color:"#ffffff33", letterSpacing:"0.15em", marginBottom:2 }}>팀 이구동성</p>
          <p style={{ fontFamily:"JetBrains Mono,monospace", fontSize:36, fontWeight:700, color:topic.color, lineHeight:1 }}>{syncDisplay}<span style={{ fontSize:16, color:`${topic.color}88` }}> / 100</span></p>
        </div>
      </motion.div>

      {/* Player cards */}
      <div className="relative z-10 grid grid-cols-3 gap-4 w-full mb-6" style={{ maxWidth:740 }}>
        {P_NAMES.map((name, i) => {
          const color = P_COLORS[i];
          const score = scores[i];
          const isBest = score === maxScore;
          const isWorst = i === worstIdx && score !== maxScore;
          return (
            <motion.div key={i} initial={{ opacity:0, y:20 }} animate={{ opacity:1, y:0 }} transition={{ delay:0.1+i*0.08 }}>
              <NeonBorder color={color} style={{
                backgroundColor: isBest?`${color}0d`:"#0d0d18",
                boxShadow: isBest?`0 0 30px ${color}22`:"none",
              }}>
                {isBest && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-0.5" style={{
                    background:`linear-gradient(90deg,${color},${color}bb)`, color:"#080810",
                    fontFamily:"JetBrains Mono,monospace", fontSize:9, fontWeight:700, letterSpacing:"0.1em", whiteSpace:"nowrap",
                  }}>✨ BEST</div>
                )}
                {isWorst && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-0.5" style={{
                    backgroundColor:"#ff2d78", color:"#fff",
                    fontFamily:"JetBrains Mono,monospace", fontSize:9, fontWeight:700, letterSpacing:"0.1em", whiteSpace:"nowrap",
                  }}>👀 AI 주목</div>
                )}
                <div className="flex flex-col items-center p-5">
                  <StickFigure variant={(round+i)%5} color={color} size={72} />
                  <p className="mt-3 mb-1" style={{ fontFamily:"JetBrains Mono,monospace", fontSize:10, fontWeight:700, color, letterSpacing:"0.12em" }}>{name}</p>
                  <p style={{ fontFamily:"JetBrains Mono,monospace", fontSize:44, fontWeight:700, color: isBest?color:"#ffffff", lineHeight:1, textShadow: isBest?`0 0 20px ${color}`:"none" }}>
                    {score}
                  </p>
                  <ScoreBar score={score} color={color} />
                </div>
              </NeonBorder>
            </motion.div>
          );
        })}
      </div>

      {/* LLM comment */}
      <div className="relative z-10 w-full" style={{ maxWidth:740 }}>
        <AnimatePresence>
          {commentVisible && (
            <motion.div initial={{ opacity:0, y:12, scale:0.97 }} animate={{ opacity:1, y:0, scale:1 }} exit={{ opacity:0 }}
              transition={{ duration:0.4, ease:"easeOut" }}
              className="p-4" style={{ border:`1px solid ${toneStyle.border}`, backgroundColor:toneStyle.bg }}>
              <div className="flex items-center gap-3 mb-3">
                <div className="flex items-center gap-1.5 px-2 py-0.5" style={{ backgroundColor:"#ffffff08", border:"1px solid #ffffff11" }}>
                  <motion.div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor:toneStyle.dot }}
                    animate={{ opacity:[1,0.3,1] }} transition={{ duration:1.5, repeat:Infinity }} />
                  <span style={{ fontFamily:"JetBrains Mono,monospace", fontSize:9, color:"#ffffff55" }}>ON-DEVICE LLM — {toneStyle.label}</span>
                </div>
                <span style={{ fontSize:16 }}>{toneStyle.icon}</span>
              </div>
              <p style={{ fontFamily:"Noto Sans KR,sans-serif", fontSize:14, color:"#ffffffcc", lineHeight:1.8 }}>
                {comment.text}
              </p>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <motion.button
        initial={{ opacity:0 }} animate={{ opacity:1 }} transition={{ delay:0.5 }}
        whileHover={{ scale:1.03 }} whileTap={{ scale:0.97 }}
        onClick={onNext}
        className="relative z-10 mt-6 flex items-center gap-3 px-10 py-4 font-black"
        style={{
          fontFamily:"Noto Sans KR,sans-serif", fontSize:15,
          background: isLast ? `linear-gradient(135deg,#ffe600,#ffaa00)` : "#1a1a28",
          color: isLast ? "#080810" : "#ffffff",
          border: isLast ? "none" : "1px solid #ffffff22",
          boxShadow: isLast ? "0 0 30px #ffe60055" : "none",
          cursor:"pointer",
        }}
      >
        {isLast ? <><Trophy size={18}/> 최종 결과 보기</> : <>다음 라운드 <ArrowRight size={16}/></>}
      </motion.button>
    </div>
  );
}

// ── SCREEN: FINAL RESULTS ──────────────────────────────────────────────────────

const FINAL_LLM = [
  "Player 2가 5라운드 내내 팀의 중심을 잡았습니다. 일관된 포즈 유지력이 인상적이었어요. Player 1은 표현력이 풍부했고, Player 3은 독창적이었지만 팀 싱크에서 아쉬운 모습이었습니다. 다음엔 팀원 포즈를 살짝 더 참고해보세요!",
  "전반적으로 팀 싱크가 높은 편이었습니다! 세 명 모두 주제를 잘 이해하고 적극적으로 표현했어요. 특히 마지막 라운드의 팀워크가 돋보였습니다.",
  "오늘 가장 빛난 플레이어는 단연 1위 플레이어! AI가 33개 관절을 분석한 결과, 포즈의 정확도와 일관성에서 최고점을 기록했습니다.",
];

function FinalResultsScreen({ topic, roundScores, onReset }: { topic:Topic; roundScores:RoundScore[]; onReset:()=>void }) {
  const [tab, setTab] = useState<"overview"|"leaderboard">("overview");

  const totalScores = [0,1,2].map(i =>
    Math.round(roundScores.reduce((s,r)=>s+r.scores[i],0)/roundScores.length)
  ) as [number,number,number];
  const avgSyncVal = Math.round(roundScores.reduce((s,r)=>s+r.syncScore,0)/roundScores.length);

  const ranked = [0,1,2].map(i=>({ i, score:totalScores[i] })).sort((a,b)=>b.score-a.score);
  const medalColors = ["#FFD700","#C0C0C0","#CD7F32"];
  const medalIcons  = ["🥇","🥈","🥉"];

  const leaderboard = [
    { session:"2025-01-15", topic:"스포츠",    sync:81, scores:[88,85,70] as [number,number,number] },
    { session:"2025-01-14", topic:"감정 표현", sync:74, scores:[79,76,68] as [number,number,number] },
    { session:"2025-01-13", topic:"직업",      sync:68, scores:[72,65,67] as [number,number,number] },
    { session:"오늘",        topic:topic.label, sync:avgSyncVal, scores:totalScores, current:true },
  ].sort((a,b)=>b.sync-a.sync);

  return (
    <div className="relative flex flex-col h-full overflow-hidden" style={{ background:"#080810" }}>
      <GridBg opacity={0.03} />

      {/* Header */}
      <div className="relative z-10 px-8 pt-8 pb-6" style={{ borderBottom:"1px solid #ffffff08" }}>
        <div className="flex items-end justify-between" style={{ maxWidth:960, margin:"0 auto", width:"100%" }}>
          <div>
            <p style={{ fontFamily:"JetBrains Mono,monospace", fontSize:11, color:"#ffffff33", letterSpacing:"0.2em", marginBottom:6 }}>FINAL RESULTS — {topic.emoji} {topic.label}</p>
            <h2 style={{ fontFamily:"Noto Sans KR,sans-serif", fontSize:"clamp(28px,4vw,44px)", fontWeight:900, letterSpacing:"-0.03em" }}>
              최종 <span style={{ color:"var(--primary)" }}>결과</span>
            </h2>
          </div>
          <div className="text-right">
            <p style={{ fontFamily:"JetBrains Mono,monospace", fontSize:10, color:"#ffffff33", letterSpacing:"0.15em", marginBottom:4 }}>평균 이구동성 지수</p>
            <p style={{ fontFamily:"JetBrains Mono,monospace", fontSize:52, fontWeight:700, color:"var(--primary)", lineHeight:1,
              textShadow:"0 0 30px #ffe60077" }}>
              {avgSyncVal}<span style={{ fontSize:20, color:"#ffe60066" }}> pts</span>
            </p>
          </div>
        </div>
      </div>

      {/* Tab bar */}
      <div className="relative z-10 flex px-8" style={{ borderBottom:"1px solid #ffffff08", maxWidth:960, margin:"0 auto", width:"100%" }}>
        {[{k:"overview",l:"플레이어 분석"},{k:"leaderboard",l:"리더보드"}].map(({k,l})=>(
          <button key={k} onClick={()=>setTab(k as any)}
            className="px-6 py-3.5 font-bold text-sm relative"
            style={{ fontFamily:"Noto Sans KR,sans-serif", background:"none", border:"none", cursor:"pointer",
              color: tab===k?"var(--primary)":"#ffffff44",
              borderBottom:`2px solid ${tab===k?"var(--primary)":"transparent"}`,
              marginBottom:"-1px",
            }}>
            {l}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto relative z-10">
        <div style={{ maxWidth:960, margin:"0 auto", padding:"24px 32px 32px", width:"100%" }}>
          <AnimatePresence mode="wait">
            {tab==="overview" && (
              <motion.div key="ov" initial={{ opacity:0, y:10 }} animate={{ opacity:1, y:0 }} exit={{ opacity:0 }}>
                {/* Podium */}
                <div className="grid grid-cols-3 gap-5 mb-6">
                  {ranked.map(({i, score}, rank) => {
                    const color = P_COLORS[i];
                    return (
                      <motion.div key={i} initial={{ opacity:0, y:30 }} animate={{ opacity:1, y:0 }} transition={{ delay:rank*0.1, duration:0.5 }}>
                        <NeonBorder color={rank===0?color:"#ffffff22"} style={{
                          backgroundColor: rank===0?`${color}0a`:"#0d0d18",
                          boxShadow: rank===0?`0 0 40px ${color}22`:"none",
                        }}>
                          <div className="flex flex-col items-center p-6">
                            <span style={{ fontSize:28, marginBottom:8 }}>{medalIcons[rank]}</span>
                            <StickFigure variant={(rank+i)%5} color={color} size={80} />
                            <p className="mt-3" style={{ fontFamily:"JetBrains Mono,monospace", fontSize:11, fontWeight:700, color, letterSpacing:"0.12em" }}>
                              {P_NAMES[i]}
                            </p>
                            <p style={{ fontFamily:"JetBrains Mono,monospace", fontSize:52, fontWeight:700, color, lineHeight:1.1,
                              textShadow: rank===0?`0 0 24px ${color}`:"none" }}>
                              {score}
                            </p>
                            <p style={{ fontFamily:"JetBrains Mono,monospace", fontSize:9, color:"#ffffff33", marginTop:2 }}>평균 점수</p>

                            {/* Per-round mini bars */}
                            <div className="w-full mt-4 space-y-2">
                              {roundScores.map((r, ri)=>(
                                <div key={ri} className="flex items-center gap-2">
                                  <span style={{ fontFamily:"JetBrains Mono,monospace", fontSize:9, color:"#ffffff22", width:14 }}>R{ri+1}</span>
                                  <div className="flex-1 h-1.5 rounded-sm" style={{ backgroundColor:"#ffffff0a" }}>
                                    <motion.div initial={{ width:0 }} animate={{ width:`${r.scores[i]}%` }}
                                      transition={{ delay:0.3+ri*0.05, duration:0.6 }}
                                      className="h-full rounded-sm" style={{ backgroundColor:`${color}88` }} />
                                  </div>
                                  <span style={{ fontFamily:"JetBrains Mono,monospace", fontSize:9, color:"#ffffff33", width:22, textAlign:"right" }}>
                                    {r.scores[i]}
                                  </span>
                                </div>
                              ))}
                            </div>
                          </div>
                        </NeonBorder>
                      </motion.div>
                    );
                  })}
                </div>

                {/* LLM final comment */}
                <motion.div initial={{ opacity:0, y:10 }} animate={{ opacity:1, y:0 }} transition={{ delay:0.5 }}
                  className="p-5" style={{ border:"1px solid #ffe60033", backgroundColor:"#ffe60008" }}>
                  <div className="flex items-center gap-3 mb-3">
                    <div className="flex items-center gap-1.5 px-2 py-0.5" style={{ backgroundColor:"#ffffff08", border:"1px solid #ffffff11" }}>
                      <motion.div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor:"#ffe600" }}
                        animate={{ opacity:[1,0.3,1] }} transition={{ duration:1.5, repeat:Infinity }} />
                      <span style={{ fontFamily:"JetBrains Mono,monospace", fontSize:9, color:"#ffffff55" }}>ON-DEVICE LLM — 최종 해설</span>
                    </div>
                    <span>🤖</span>
                  </div>
                  <p style={{ fontFamily:"Noto Sans KR,sans-serif", fontSize:15, color:"#ffffffcc", lineHeight:1.8 }}>
                    {FINAL_LLM[ranked[0].i]}
                  </p>
                </motion.div>
              </motion.div>
            )}

            {tab==="leaderboard" && (
              <motion.div key="lb" initial={{ opacity:0, y:10 }} animate={{ opacity:1, y:0 }} exit={{ opacity:0 }}>
                <div style={{ border:"1px solid #ffffff08" }}>
                  {/* header */}
                  <div className="grid px-6 py-3" style={{
                    gridTemplateColumns:"32px 1fr 80px 80px 60px 60px 60px",
                    borderBottom:"1px solid #ffffff08", backgroundColor:"#0d0d18",
                  }}>
                    {["","세션","주제","싱크","P1","P2","P3"].map(h=>(
                      <span key={h} style={{ fontFamily:"JetBrains Mono,monospace", fontSize:10, color:"#ffffff33", letterSpacing:"0.1em" }}>{h}</span>
                    ))}
                  </div>
                  {leaderboard.map((row, ri)=>{
                    const isCurrent = (row as any).current;
                    return (
                      <motion.div key={ri} initial={{ opacity:0, x:-10 }} animate={{ opacity:1, x:0 }} transition={{ delay:ri*0.06 }}
                        className="grid items-center px-6 py-4"
                        style={{
                          gridTemplateColumns:"32px 1fr 80px 80px 60px 60px 60px",
                          borderBottom: ri<leaderboard.length-1?"1px solid #ffffff06":"none",
                          backgroundColor: isCurrent?"#ffe60008":"transparent",
                        }}>
                        <span style={{ fontSize:16 }}>{ri===0?"🏆":["","","",""][ri]}</span>
                        <div className="flex items-center gap-2">
                          <span style={{ fontFamily:"JetBrains Mono,monospace", fontSize:12, color: isCurrent?"var(--primary)":"#ffffff77" }}>
                            {row.session}
                          </span>
                          {isCurrent && (
                            <span style={{ fontFamily:"JetBrains Mono,monospace", fontSize:8, color:"var(--primary)", border:"1px solid #ffe60055", padding:"1px 4px" }}>NOW</span>
                          )}
                        </div>
                        <span style={{ fontFamily:"Noto Sans KR,sans-serif", fontSize:13, color:"#ffffffcc" }}>{row.topic}</span>
                        <span style={{ fontFamily:"JetBrains Mono,monospace", fontSize:16, fontWeight:700,
                          color: ri===0?"#FFD700": isCurrent?"var(--primary)":"#ffffff" }}>
                          {row.sync}
                        </span>
                        {[0,1,2].map(pi=>(
                          <span key={pi} style={{ fontFamily:"JetBrains Mono,monospace", fontSize:13, color:P_COLORS[pi] }}>
                            {row.scores[pi]}
                          </span>
                        ))}
                      </motion.div>
                    );
                  })}
                </div>
                <p className="mt-3 text-right" style={{ fontFamily:"JetBrains Mono,monospace", fontSize:10, color:"#ffffff22" }}>
                  싱크 점수 기준 정렬
                </p>
              </motion.div>
            )}
          </AnimatePresence>

          <motion.button
            initial={{ opacity:0 }} animate={{ opacity:1 }} transition={{ delay:0.3 }}
            whileHover={{ scale:1.02 }} whileTap={{ scale:0.98 }}
            onClick={onReset}
            className="w-full mt-8 py-4 flex items-center justify-center gap-3 font-black"
            style={{ fontFamily:"Noto Sans KR,sans-serif", fontSize:15, backgroundColor:"#1a1a28", color:"#ffffff", border:"1px solid #ffffff11", cursor:"pointer" }}
          >
            <RotateCcw size={16} /> 다시 하기
          </motion.button>
        </div>
      </div>
    </div>
  );
}

// ── NAV BAR ────────────────────────────────────────────────────────────────────

const NAV: {key:Screen; label:string}[] = [
  {key:"lobby",         label:"대기방"},
  {key:"topic-select",  label:"주제 선택"},
  {key:"round-word",    label:"제시어"},
  {key:"countdown",     label:"카운트다운"},
  {key:"capture",       label:"포즈 캡처"},
  {key:"round-result",  label:"라운드 결과"},
  {key:"final-results", label:"최종 결과"},
];

function NavBar({ current, onJump }: { current:Screen; onJump:(s:Screen)=>void }) {
  const ci = NAV.findIndex(n=>n.key===current);
  return (
    <div className="flex items-center flex-shrink-0 overflow-x-auto px-4"
      style={{ borderBottom:"1px solid #ffffff08", backgroundColor:"#06060e", height:44 }}>
      {NAV.map(({key,label},i)=>{
        const active = current===key;
        const past = ci>i;
        return (
          <button key={key} onClick={()=>onJump(key)}
            className="flex items-center gap-1.5 px-3.5 h-full whitespace-nowrap relative"
            style={{ fontFamily:"JetBrains Mono,monospace", fontSize:10, letterSpacing:"0.08em",
              color: active?"var(--primary)":past?"#ffffff33":"#ffffff16",
              background:"none", border:"none",
              borderBottom:`2px solid ${active?"var(--primary)":"transparent"}`,
              cursor:"pointer", marginBottom:"-1px",
            }}>
            <span style={{ fontSize:9, color: active?"#ffe60066":past?"#ffffff22":"#ffffff0f" }}>{String(i+1).padStart(2,"0")}</span>
            {label}
          </button>
        );
      })}
      <div className="flex-1" />
      <span style={{ fontFamily:"JetBrains Mono,monospace", fontSize:9, color:"#ffffff11", padding:"0 12px", letterSpacing:"0.1em" }}>
        WIREFRAME
      </span>
    </div>
  );
}

// ── ROOT ───────────────────────────────────────────────────────────────────────

export default function App() {
  const [screen, setScreen] = useState<Screen>("lobby");
  const [topic, setTopic] = useState<Topic>(TOPICS[0]);
  const [round, setRound] = useState(0);
  const [roundScores, setRoundScores] = useState<RoundScore[]>([]);

  const TOTAL = topic.words.length;
  const word  = topic.words[round] ?? "";

  function commitScore() {
    const scores = fakeScores(round);
    setRoundScores(prev => [...prev.filter(r=>r.round!==round), { round, word, scores, syncScore:avgSync(scores) }]);
  }

  function handleReset() { setRound(0); setRoundScores([]); setScreen("lobby"); }

  function handleJump(s: Screen) {
    if (["round-word","countdown","capture","round-result"].includes(s)) {
      if (roundScores.length===0) {
        const sc = fakeScores(0);
        setRoundScores([{round:0,word:topic.words[0],scores:sc,syncScore:avgSync(sc)}]);
      }
      setRound(0);
    }
    setScreen(s);
  }

  const currentRoundData = roundScores.find(r=>r.round===round);
  const allRoundScores = roundScores.length>0 ? roundScores : topic.words.map((w,i)=>{
    const sc=fakeScores(i); return {round:i,word:w,scores:sc,syncScore:avgSync(sc)};
  });

  return (
    <div className="flex flex-col h-screen overflow-hidden" style={{ fontFamily:"Noto Sans KR,sans-serif", backgroundColor:"#080810" }}>
      <NavBar current={screen} onJump={handleJump} />
      <div className="flex-1 overflow-hidden">
        <AnimatePresence mode="wait">
          <motion.div key={`${screen}-${round}`}
            initial={{ opacity:0 }} animate={{ opacity:1 }} exit={{ opacity:0 }}
            transition={{ duration:0.2 }} style={{ height:"100%" }}>
            {screen==="lobby"         && <LobbyScreen onStart={()=>setScreen("topic-select")} />}
            {screen==="topic-select"  && <TopicSelectScreen onSelect={t=>{setTopic(t);setRound(0);setRoundScores([]);setScreen("round-word");}} />}
            {screen==="round-word"    && <RoundWordScreen topic={topic} word={word} round={round} total={TOTAL} onNext={()=>setScreen("countdown")} />}
            {screen==="countdown"     && <CountdownScreen topic={topic} round={round} total={TOTAL} onNext={()=>setScreen("capture")} />}
            {screen==="capture"       && <CaptureScreen topic={topic} round={round} total={TOTAL} word={word} onNext={()=>{commitScore();setScreen("round-result");}} />}
            {screen==="round-result" && currentRoundData && (
              <RoundResultScreen
                topic={topic} round={round} total={TOTAL}
                word={currentRoundData.word} scores={currentRoundData.scores} syncScore={currentRoundData.syncScore}
                onNext={()=>{
                  if (round<TOTAL-1){setRound(r=>r+1);setScreen("round-word");}
                  else setScreen("final-results");
                }}
              />
            )}
            {screen==="final-results" && <FinalResultsScreen topic={topic} roundScores={allRoundScores} onReset={handleReset} />}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}
