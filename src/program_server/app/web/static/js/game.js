const GAUGE_CIRCUMFERENCE = 2 * Math.PI * 104;

const screens = {
  idle: document.getElementById("screen-idle"),
  category: document.getElementById("screen-category"),
  catpick: document.getElementById("screen-category"),
  confirm: document.getElementById("screen-camtest"),
  camtest: document.getElementById("screen-camtest"),
  intro: document.getElementById("screen-intro"),
  countdown: document.getElementById("screen-countdown"),
  playing: document.getElementById("screen-playing"),
  giveup: document.getElementById("screen-playing"),
  reveal: document.getElementById("screen-playing"),
  timeup: document.getElementById("screen-timeup"),
  result: document.getElementById("screen-result"),
  finished: document.getElementById("screen-final"),
};

const el = {
  conn: document.getElementById("conn"),
  roundPill: document.getElementById("round-pill"),
  restartBtn: document.getElementById("restart-btn"),
  idlePlayers: document.getElementById("idle-players"),
  cdNumber: document.getElementById("cd-number"),
  playPrompt: document.getElementById("play-prompt"),
  playTagline: document.getElementById("play-tagline"),
  gaugeFill: document.getElementById("gauge-fill"),
  gaugeValue: document.getElementById("gauge-value"),
  timerFill: document.getElementById("timer-fill"),
  timerText: document.getElementById("timer-text"),
  resultRound: document.getElementById("result-round"),
  resultPrompt: document.getElementById("result-prompt"),
  resultScore: document.getElementById("result-score"),
  resultComment: document.getElementById("result-comment"),
  mcText: document.getElementById("mc-text"),
  finalScore: document.getElementById("final-score"),
  finalSummary: document.getElementById("final-summary"),
  finalTitle: document.getElementById("final-title"),
  finalReport: document.getElementById("final-report"),
  finalBreakdown: document.getElementById("final-breakdown"),
  reportCards: document.getElementById("report-cards"),
  saveReportBtn: document.getElementById("save-report-btn"),
  introSpeech: document.getElementById("intro-speech"),
  introPlayers: document.getElementById("intro-players"),
  themePicker: document.getElementById("theme-picker"),
  coachText: document.getElementById("coach-text"),
  ttsToggle: document.getElementById("tts-toggle"),
  restartGameBtn: document.getElementById("restart-game-btn"),
  mcStage: document.getElementById("mc-stage"),
  mcLiveBubble: document.getElementById("mc-live-bubble"),
  mcLiveText: document.getElementById("mc-live-text"),
  teamName: document.getElementById("team-name"),
  leaderboardList: document.getElementById("leaderboard-list"),
  leaderboardEmpty: document.getElementById("leaderboard-empty"),
  leaderboardReset: document.getElementById("leaderboard-reset"),
  finalLeaderboardList: document.getElementById("final-leaderboard-list"),
  finalLeaderboardEmpty: document.getElementById("final-leaderboard-empty"),
  finalTeam: document.getElementById("final-team"),
  finalRank: document.getElementById("final-rank"),
  tposeCue: document.getElementById("tpose-cue"),
  tposeProgressFill: document.getElementById("tpose-progress-fill"),
  catCards: document.getElementById("cat-cards"),
  catSpeech: document.getElementById("cat-speech"),
  catConfirmFill: document.getElementById("cat-confirm-fill"),
  manualStartBtn: document.getElementById("manual-start-btn"),
  skipIntroBtn: document.getElementById("skip-intro-btn"),
  catPrevBtn: document.getElementById("cat-prev-btn"),
  catNextBtn: document.getElementById("cat-next-btn"),
  catConfirmBtn: document.getElementById("cat-confirm-btn"),
  camtestCams: document.getElementById("camtest-cams"),
  camtestSkipBtn: document.getElementById("camtest-skip-btn"),
  camtestMc: document.getElementById("camtest-mc"),
  camHintOverlay: document.getElementById("cam-hint-overlay"),
  camHintCams: document.getElementById("cam-hint-cams"),
  giveupOverlay: document.getElementById("giveup-overlay"),
  giveupPrompt: document.getElementById("giveup-prompt"),
  giveupShots: document.getElementById("giveup-shots"),
  revealOverlay: document.getElementById("reveal-overlay"),
  revealWord: document.getElementById("reveal-word"),
};

const playerCount = Number(document.body.dataset.playerCount || "3");
const PLAYER_INDICES = Array.from({ length: playerCount }, (_, i) => i);
let lbLastPhase = null;
let lastResultRound = 0;

// --- AI MC voice: prefers natural server audio (edge-tts), falls back to the
// browser's Web Speech voice. Also drives the avatar's talking animation. ---
const tts = {
  muted: false,
  lastSpokenId: 0,
  supported: "speechSynthesis" in window,
  voice: null,
};
let currentAudio = null;

// --- Autoplay unlock -------------------------------------------------------
// The game can auto-start from a T-pose (computer vision) with no DOM click, so
// the browser may block the first audio.play(). We prime the media + speech +
// WebAudio engines on the first real user interaction (typing the team name,
// tapping anywhere, clicking start) so the MC voice is never silenced.
let audioPrimed = false;
const SILENT_WAV =
  "data:audio/wav;base64,UklGRiwAAABXQVZFZm10IBAAAAABAAEAQB8AAIA+AAACABAAZGF0YQgAAAAAAAAAAAAAAA==";
function primeAudio() {
  // Always nudge the chime context back to life (it can get suspended).
  try {
    const ctx = chime.ctx || (chime.ctx = new (window.AudioContext || window.webkitAudioContext)());
    if (ctx.state === "suspended") ctx.resume();
  } catch (e) { /* ignore */ }
  if (audioPrimed) return;
  audioPrimed = true;
  // Unlock <audio> element autoplay by playing a silent clip from the gesture.
  try {
    const a = new Audio(SILENT_WAV);
    a.volume = 0;
    const p = a.play();
    if (p && p.catch) p.catch(() => {});
  } catch (e) { /* ignore */ }
  // Warm the Web Speech engine so the fallback voice is ready instantly.
  try {
    if (tts.supported) {
      const u = new SpeechSynthesisUtterance(" ");
      u.volume = 0;
      window.speechSynthesis.speak(u);
    }
  } catch (e) { /* ignore */ }
}
["pointerdown", "touchstart", "keydown", "click"].forEach((evt) =>
  window.addEventListener(evt, primeAudio, { passive: true })
);

// Tell the server the MC opening finished so the countdown starts exactly when
// speech ends (never cut off, never too early). Fires once per intro.
let introDoneSent = false;
function sendIntroDone() {
  if (introDoneSent) return;
  introDoneSent = true;
  fetch("/api/game/intro-done", { method: "POST" }).catch(() => {});
}

function pickKoreanVoice() {
  if (!tts.supported) return null;
  const voices = window.speechSynthesis.getVoices();
  return (
    voices.find((v) => v.lang && v.lang.toLowerCase().startsWith("ko")) || null
  );
}

if (tts.supported) {
  tts.voice = pickKoreanVoice();
  window.speechSynthesis.onvoiceschanged = () => {
    tts.voice = pickKoreanVoice();
  };
}

// Speech/MC lines are written phonetically in Korean so the TTS voice pronounces
// English acronyms correctly ("에이아이 엠씨"). On-screen captions read nicer with
// the real English, so swap the common ones back for DISPLAY ONLY — the text sent
// to the voice engine is never touched.
const CAPTION_REPLACEMENTS = [
  [/에이아이/g, "AI"],
  [/엠\s*씨/g, "MC"],
];
function toCaption(text) {
  let out = text || "";
  for (const [re, rep] of CAPTION_REPLACEMENTS) out = out.replace(re, rep);
  return out;
}

function setMcTalking(on, text) {
  if (el.mcStage) el.mcStage.classList.toggle("is-talking", Boolean(on));
  // 결산 화면에선 같은 멘트가 이미 화면 가운데에 떠 있으므로 말풍선은 띄우지 않는다.
  // 인트로 투어·카테고리 화면에선 아래 글자로 대사가 나오므로 말풍선을 숨겨 데모를 안 가리게 한다.
  const suppressBubble =
    currentPhase === "finished" || currentPhase === "intro" || currentPhase === "category" || currentPhase === "catpick" || currentPhase === "confirm" || currentPhase === "camtest" || currentPhase === "reveal";
  if (on && text && !suppressBubble && el.mcLiveText && el.mcLiveBubble) {
    el.mcLiveText.textContent = toCaption(text);
    el.mcLiveBubble.classList.add("is-visible");
  } else if ((!on || suppressBubble) && el.mcLiveBubble) {
    el.mcLiveBubble.classList.remove("is-visible");
  }
}

function stopSpeaking() {
  if (currentAudio) {
    try {
      currentAudio.pause();
    } catch {
      /* ignore */
    }
    currentAudio = null;
  }
  if (tts.supported) window.speechSynthesis.cancel();
  setMcTalking(false);
}

function speakLine(text) {
  if (!tts.supported || tts.muted || !text) return;
  try {
    const utter = new SpeechSynthesisUtterance(text);
    utter.lang = "ko-KR";
    utter.rate = 1.05;
    utter.pitch = 1.05;
    if (tts.voice) utter.voice = tts.voice;
    utter.onstart = () => setMcTalking(true, text);
    utter.onend = () => { setMcTalking(false); if (currentPhase === "intro" || currentPhase === "confirm") sendIntroDone(); };
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utter);
  } catch {
    setMcTalking(false);
  }
}

function playServerAudio(id, text, attempt) {
  // A newer line arrived (or muted) -> abandon this one.
  if (tts.muted || id !== tts.lastSpokenId) return;
  fetch(`/api/game/speech/${id}.mp3`, { cache: "no-store" })
    .then((r) => {
      if (r.ok) return r.blob();
      throw new Error("not-ready");
    })
    .then((blob) => {
      if (tts.muted || id !== tts.lastSpokenId) return;
      const audio = new Audio(URL.createObjectURL(blob));
      currentAudio = audio;
      audio.onplay = () => setMcTalking(true, text);
      audio.onended = () => {
        setMcTalking(false);
        if (currentAudio === audio) currentAudio = null;
        if (currentPhase === "intro" || currentPhase === "confirm") sendIntroDone();
      };
      audio.onerror = () => {
        setMcTalking(false);
        speakLine(text);
      };
      audio.play().catch(() => speakLine(text));
    })
    .catch(() => {
      // edge-tts generation takes ~1s; retry a while so the natural (server)
      // voice is used instead of falling back to the browser voice mid-intro.
      if (attempt < 30 && !tts.muted && id === tts.lastSpokenId) {
        setTimeout(() => playServerAudio(id, text, attempt + 1), 400);
      } else if (!tts.muted && id === tts.lastSpokenId) {
        speakLine(text);
      }
    });
}

function maybeSpeak(state) {
  const id = state.speech_id || 0;
  if (id <= tts.lastSpokenId) return;
  // Each new intro/confirm line must re-arm the audio-end signal so we advance
  // the moment that line finishes (instead of waiting on the fallback timer).
  if (state.phase === "intro" || state.phase === "confirm") introDoneSent = false;
  tts.lastSpokenId = id;
  if (tts.muted) return;
  stopSpeaking();
  tts.lastSpokenId = id; // stopSpeaking doesn't touch this; keep explicit
  if (state.speech_audio) playServerAudio(id, state.speech, 0);
  else speakLine(state.speech);
}

if (el.ttsToggle) {
  el.ttsToggle.addEventListener("click", () => {
    tts.muted = !tts.muted;
    el.ttsToggle.textContent = tts.muted ? "🔇" : "🔊";
    el.ttsToggle.classList.toggle("is-muted", tts.muted);
    if (tts.muted) stopSpeaking();
  });
}

// Manual fallback buttons (in case the T-pose / hand gestures don't register).
const postGame = (path) => fetch(path, { method: "POST" }).catch(() => {});
if (el.manualStartBtn)
  el.manualStartBtn.addEventListener("click", () => {
    const name = (el.teamName && el.teamName.value.trim()) || "";
    fetch("/api/game/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ team_name: name }),
    }).catch(() => {});
  });
if (el.skipIntroBtn) el.skipIntroBtn.addEventListener("click", () => postGame("/api/game/skip-intro"));
if (el.catPrevBtn) el.catPrevBtn.addEventListener("click", () => postGame("/api/game/category-step/prev"));
if (el.catNextBtn) el.catNextBtn.addEventListener("click", () => postGame("/api/game/category-step/next"));
if (el.catConfirmBtn) el.catConfirmBtn.addEventListener("click", () => postGame("/api/game/confirm-category"));
if (el.camtestSkipBtn) el.camtestSkipBtn.addEventListener("click", () => postGame("/api/game/skip-camtest"));

function gaugeColor(value) {
  if (value >= 75) return "#00ffc6";
  if (value >= 50) return "#9cff57";
  if (value >= 30) return "#ffd34d";
  return "#ff6b6b";
}

function taglineFor(value, readyCount) {
  if (readyCount < 2) return "플레이어를 기다리는 중…";
  if (value >= 90) return "완벽한 텔레파시! 소름 돋아요";
  if (value >= 70) return "거의 다 통했어요!";
  if (value >= 45) return "조금씩 맞아가는 중…";
  if (value >= 20) return "음… 생각이 다른데요?";
  return "전혀 다른 동작이에요!";
}

function buildPlayerDots(container) {
  container.innerHTML = "";
  const dots = [];
  for (let i = 0; i < playerCount; i += 1) {
    const dot = document.createElement("div");
    dot.className = "pdot";
    dot.innerHTML = `<span class="led"></span><span>P${i + 1}</span>`;
    container.appendChild(dot);
    dots.push(dot);
  }
  return dots;
}

const idleDots = buildPlayerDots(el.idlePlayers);
const introDots = el.introPlayers ? buildPlayerDots(el.introPlayers) : [];

// Per-round skeleton snapshots for the final report (round number -> data).
const roundCaptures = {};
let currentRoundMeta = null;
let lastResultPoseRound = 0;
let lastGiveupRound = 0;
let lastFinalState = null;

function updatePlayerDots(dots, players) {
  dots.forEach((dot, index) => {
    const player = players && players[index];
    dot.classList.toggle("ready", Boolean(player && player.ready));
  });
}

function showScreen(phase) {
  const activeNode = screens[phase];
  Object.values(screens).forEach((node) => {
    node.classList.toggle("is-active", node === activeNode);
  });
}

function setGauge(value) {
  const clamped = Math.max(0, Math.min(100, value));
  const offset = GAUGE_CIRCUMFERENCE * (1 - clamped / 100);
  const color = gaugeColor(clamped);
  el.gaugeFill.style.strokeDashoffset = String(offset);
  el.gaugeFill.style.stroke = color;
  el.gaugeValue.textContent = String(Math.round(clamped));
  el.gaugeValue.style.color = color;
}

function render(state) {
  const prevPhase = currentPhase;
  showScreen(state.phase);
  maybeSpeak(state);

  // A fresh game just began (idle/finished -> intro): clear the per-round
  // capture state that startGame() used to reset before the button was removed.
  if (state.phase === "intro" && prevPhase !== "intro") {
    introDoneSent = false;
    lastResultRound = 0;
    lastResultPoseRound = 0;
    lastGiveupRound = 0;
    currentRoundMeta = null;
    Object.keys(roundCaptures).forEach((k) => delete roundCaptures[k]);
  }

  // Refresh the leaderboard only on phase transitions (not every snapshot):
  // when returning to the idle board, and when a game has just finished.
  if (state.phase !== lbLastPhase) {
    lbLastPhase = state.phase;
    if (state.phase === "idle") refreshLeaderboardIdle();
    else if (state.phase === "finished") refreshLeaderboardFinal(state);
  }

  if (state.phase === "idle") {
    el.roundPill.textContent = "READY";
    if (el.tposeProgressFill) {
      const pct = Math.round((state.ready_pose_hold_progress || 0) * 100);
      el.tposeProgressFill.style.width = `${pct}%`;
    }
    if (el.tposeCue) el.tposeCue.classList.toggle("is-holding", (state.ready_pose_hold_progress || 0) > 0);
  } else if (state.phase === "finished") {
    el.roundPill.textContent = "FINAL";
  } else {
    el.roundPill.textContent = `맞춘 개수 ${state.cleared_count || 0}`;
  }

  updatePlayerDots(idleDots, state.players);
  updatePlayerDots(introDots, state.players);
  if (el.mcStage) {
    // MC 민수 무대 위치를 단계별로 정한다:
    //  - intro: 코너에 머문 채 살짝 커져 인사 멘트를 한다 (is-center)
    //  - finished: 중앙의 최종 리포트 옆으로 날아가 그 문구를 읽어주는 자리 (is-final)
    //  - 그 외 진행 중: 옆에서 귀신처럼 둥둥 떠다닌다 (is-side)
    const mcHidden = state.phase === "idle";
    const mcCenter = state.phase === "intro" || state.phase === "confirm";
    const mcFinal = state.phase === "finished";
    const mcReveal = state.phase === "reveal";
    const mcGiveup = state.phase === "giveup";
    const mcHint = Boolean(state.show_hint_cams);
    el.mcStage.classList.toggle("is-hidden", mcHidden);
    el.mcStage.classList.toggle("is-center", !mcHidden && mcCenter);
    el.mcStage.classList.toggle("is-final", !mcHidden && mcFinal);
    el.mcStage.classList.toggle("is-reveal", !mcHidden && mcReveal);
    el.mcStage.classList.toggle("is-giveup", !mcHidden && mcGiveup);
    el.mcStage.classList.toggle("is-hint", !mcHidden && mcHint);
    el.mcStage.classList.toggle("is-side", !mcHidden && !mcCenter && !mcFinal && !mcReveal && !mcGiveup);
    el.mcStage.classList.toggle("is-category", state.phase === "category");
    // Guided intro tour: fly to the demo element the MC is explaining.
    const tour = state.phase === "intro" ? (state.tour_target || "intro") : "";
    ["prompt", "gauge", "hint", "ready", "intro"].forEach((t) =>
      el.mcStage.classList.toggle(`tour-${t}`, tour === t)
    );
    document.querySelectorAll(".intro-demo [data-tour]").forEach((node) =>
      node.classList.toggle("is-spotlight", tour === node.dataset.tour)
    );
  }
  // The "start over" button only makes sense once a game is under way.
  if (el.restartGameBtn) el.restartGameBtn.classList.toggle("is-hidden", state.phase === "idle");

  latestPlayers = Array.isArray(state.players) ? state.players : [];
  currentPhase = state.phase;

  if (state.phase === "intro") {
    el.introSpeech.textContent = toCaption(state.speech) || "민수가 인사 중…";
  }

  if (state.phase === "category" && prevPhase !== "category") {
    lastCatIndex = -1;
    lastCatConfirmed = "";
  }
  if (state.phase === "category") renderCategory(state);
  // 카테고리 확정 직후(catpick) 같은 화면에서 "선택하셨네요" 멘트가 끝나길 기다린다.
  // 이때는 고른 카테고리 하나만 크게 남겨서 무엇이 선택됐는지 확실히 보여준다.
  if (state.phase === "catpick") {
    renderCategoryConfirmed(state);
    if (el.catSpeech) el.catSpeech.textContent = toCaption(state.speech);
  }
  // 카테고리 확정 후 안내 멘트(확정 → 시작) 동안 선택된 카테고리만 크게 유지한다.
  if (state.phase === "confirm") {
    renderCategoryConfirmed(state);
    if (el.catSpeech) el.catSpeech.textContent = toCaption(state.speech);
  }

  // camtest/confirm 화면(둘 다 screen-camtest)에서 민수의 멘트를 글자로도 보여준다.
  if (el.camtestMc) {
    if (state.phase === "camtest" || state.phase === "confirm") {
      el.camtestMc.textContent = toCaption(state.speech);
    } else {
      el.camtestMc.textContent = "";
    }
  }

  if (state.phase === "camtest") renderCamtest(state, prevPhase);
  else teardownCamtestStreams();

  if (state.phase === "countdown") {
    // The prompt is intentionally hidden during 3-2-1 so the first reveal
    // ("이번 제시어는!") stays a surprise.
    const left = state.time_left == null ? 0 : state.time_left;
    el.cdNumber.textContent = String(Math.min(3, Math.max(1, Math.ceil(left))));
  }

  if (state.phase === "playing") {
    el.playPrompt.textContent = state.prompt || "";
    setGauge(state.gauge);
    latestGauge = state.gauge;
    el.playTagline.textContent = taglineFor(state.gauge, state.ready_count);
    if (el.coachText && state.coach) el.coachText.textContent = state.coach;
    // Coaching is voiced by the server in the same MC voice (edge-tts) via the
    // shared speech pipeline, so we no longer speak it with the browser voice.

    // The timer is the whole-game 60s sprint clock (not a per-round timer).
    const total = state.game_total || 60;
    const left = state.game_time_left == null ? total : state.game_time_left;
    el.timerFill.style.width = `${Math.max(0, Math.min(100, (left / total) * 100))}%`;
    el.timerText.textContent = left.toFixed(1);
    renderCamHint(state);
  }
  if (state.phase !== "playing" && camHintShown && el.camHintOverlay) {
    camHintShown = false;
    setCamStreams(el.camHintCams, false);
    el.camHintOverlay.classList.remove("is-visible");
    el.camHintOverlay.setAttribute("aria-hidden", "true");
  }

  // Timeout notice: keep the (failed) prompt + frozen clock on screen and pop
  // the "next prompt coming" overlay until the server swaps in a fresh prompt.
  if (state.phase === "giveup") {
    el.playPrompt.textContent = state.prompt || "";
    const total = state.game_total || 60;
    const left = state.game_time_left == null ? total : state.game_time_left;
    el.timerFill.style.width = `${Math.max(0, Math.min(100, (left / total) * 100))}%`;
    el.timerText.textContent = left.toFixed(1);
    if (el.giveupPrompt) el.giveupPrompt.textContent = state.prompt || "";
    // Show the frames the server captured at timeout so the team can see why it
    // didn't match. Build them once per round (broken frames remove themselves).
    const round = (state.round_scores || []).length;
    if (el.giveupShots && round && round !== lastGiveupRound) {
      lastGiveupRound = round;
      el.giveupShots.innerHTML = PLAYER_INDICES.map(
        (i) => `<img src="/api/game/result-frame/${round}/${i}.jpg" alt="" onerror="this.remove()" />`
      ).join("");
    }
  }
  if (el.giveupOverlay) {
    const showGiveup = state.phase === "giveup";
    el.giveupOverlay.classList.toggle("is-visible", showGiveup);
    el.giveupOverlay.setAttribute("aria-hidden", showGiveup ? "false" : "true");
  }

  // Prompt reveal: show the new prompt big (clock frozen) while the MC reads it,
  // then the gauge game appears behind once the overlay fades.
  if (state.phase === "reveal") {
    el.playPrompt.textContent = state.prompt || "";
    if (el.revealWord) el.revealWord.textContent = state.prompt || "";
    // Replay the pop-in animation each time a new prompt is revealed.
    if (prevPhase !== "reveal" && el.revealWord) {
      el.revealWord.style.animation = "none";
      void el.revealWord.offsetWidth;
      el.revealWord.style.animation = "";
    }
    setGauge(0);
    const total = state.game_total || 60;
    const left = state.game_time_left == null ? total : state.game_time_left;
    el.timerFill.style.width = `${Math.max(0, Math.min(100, (left / total) * 100))}%`;
    el.timerText.textContent = left.toFixed(1);
  }
  if (el.revealOverlay) {
    const showReveal = state.phase === "reveal";
    el.revealOverlay.classList.toggle("is-visible", showReveal);
    el.revealOverlay.setAttribute("aria-hidden", showReveal ? "false" : "true");
  }

  if (state.phase === "result") {
    const scores = state.round_scores || [];
    const roundScore = scores.length ? scores[scores.length - 1] : 0;
    el.resultRound.textContent = `ROUND ${scores.length}`;
    el.resultPrompt.textContent = state.prompt || "";
    if (scores.length !== lastResultRound) {
      lastResultRound = scores.length;
      el.resultScore.style.animation = "none";
      void el.resultScore.offsetWidth;
      el.resultScore.style.animation = "";
    }
    el.resultScore.textContent = String(Math.round(roundScore));
    currentRoundMeta = {
      round: scores.length,
      prompt: state.prompt || (state.prompts || [])[scores.length - 1] || "",
      score: Math.round(roundScore),
    };
    if (scores.length && scores.length !== lastResultPoseRound) {
      lastResultPoseRound = scores.length;
      revealResultFrames(scores.length, state.result_poses || []);
    }
    if (state.mc_status === "pending") {
      el.mcText.textContent = "🎤 AI MC가 멘트를 준비 중…";
      el.resultComment.classList.add("is-pending");
    } else if (state.mc_comment) {
      el.mcText.textContent = toCaption(state.mc_comment);
      el.resultComment.classList.remove("is-pending");
    } else {
      el.mcText.textContent = taglineFor(roundScore, 2);
      el.resultComment.classList.remove("is-pending");
    }
  }

  if (state.phase === "finished") {
    lastFinalState = state;
    el.finalScore.textContent = String(Math.round(state.total_score || 0));
    el.finalTitle.textContent = state.final_title || "";
    if (el.finalSummary) {
      const secs = Number(state.final_seconds || 0);
      el.finalSummary.textContent = `⏱ ${secs.toFixed(1)}초 동안 ${state.cleared_count || 0}개 클리어!`;
    }
    if (el.finalTeam) {
      el.finalTeam.textContent = state.team_name ? `🏷 ${state.team_name}` : "";
    }
    if (state.final_status === "pending") {
      el.finalReport.textContent = "📜 AI가 텔레파시 궤합을 분석 중…";
      el.finalReport.classList.add("is-pending");
    } else if (state.final_report) {
      el.finalReport.textContent = toCaption(state.final_report);
      el.finalReport.classList.remove("is-pending");
    } else {
      el.finalReport.textContent = "";
      el.finalReport.classList.remove("is-pending");
    }
    el.finalBreakdown.innerHTML = "";
    const results = state.round_results || [];
    const breakdownPrompts = state.prompts || [];
    results.forEach((passed, index) => {
      const word = breakdownPrompts[index] || `R${index + 1}`;
      const li = document.createElement("li");
      li.className = passed ? "fb-pass" : "fb-fail";
      li.innerHTML =
        `<span class="fb-word">${word}</span>` +
        `<span class="fb-result">${passed ? "✅ 통과" : "❌ 실패"}</span>`;
      el.finalBreakdown.appendChild(li);
    });
    renderReport(state);
  }
}

// --- Body-controlled category picker ---
let lastCatIndex = -1;
let lastCatConfirmed = "";
function renderCategory(state) {
  const options = state.category_options || [];
  const index = state.category_index || 0;
  if (screens.category) screens.category.classList.remove("is-confirmed");
  if (el.catCards && lastCatIndex !== index) {
    el.catCards.innerHTML = "";
    options.forEach((name, i) => {
      const card = document.createElement("div");
      card.className = "cat-card" + (i === index ? " is-active" : "");
      card.textContent = name;
      el.catCards.appendChild(card);
    });
    lastCatIndex = index;
  }
  if (el.catConfirmFill) {
    const pct = Math.round((state.category_confirm_progress || 0) * 100);
    el.catConfirmFill.style.width = `${pct}%`;
  }
  if (el.catSpeech) el.catSpeech.textContent = toCaption(state.speech);
}

// 카테고리 확정 후: 고른 카테고리 하나만 큼지막하게 남겨 "이게 선택됐다"를 확실히 보여준다.
function renderCategoryConfirmed(state) {
  const options = state.category_options || [];
  const index = state.category_index || 0;
  const chosen = state.theme || options[index] || "";
  if (screens.category) screens.category.classList.add("is-confirmed");
  if (el.catCards && lastCatConfirmed !== chosen) {
    el.catCards.innerHTML = "";
    const card = document.createElement("div");
    card.className = "cat-card cat-card-chosen";
    card.innerHTML = `<span class="cat-chosen-check">✅</span><span class="cat-chosen-name">${chosen}</span><span class="cat-chosen-tag">선택 완료!</span>`;
    el.catCards.appendChild(card);
    lastCatConfirmed = chosen;
    lastCatIndex = -1;
  }
  if (el.catConfirmFill) el.catConfirmFill.style.width = "100%";
}

// --- Camera test: 3 large live feeds; each turns green + chimes when its
// player holds the T-pose, all green -> proceed. Manual skip button fallback. ---
let camtestLastChime = 0;
function chime() {
  try {
    const ctx = chime.ctx || (chime.ctx = new (window.AudioContext || window.webkitAudioContext)());
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain).connect(ctx.destination);
    osc.frequency.setValueAtTime(880, ctx.currentTime);
    osc.frequency.setValueAtTime(1320, ctx.currentTime + 0.09);
    gain.gain.setValueAtTime(0.001, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.3, ctx.currentTime + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.35);
    osc.start();
    osc.stop(ctx.currentTime + 0.36);
  } catch (e) {}
}

function renderCamtest(state, prevPhase) {
  const players = Array.isArray(state.players) ? state.players : [];
  const passed = new Set(state.camtest_pass || []);
  if (prevPhase !== "camtest") camtestLastChime = 0;
  if (el.camtestCams && (prevPhase !== "camtest" || el.camtestCams.childElementCount !== players.length)) {
    el.camtestCams.innerHTML = "";
    players.forEach((p, i) => {
      const cam = document.createElement("div");
      cam.className = "camtest-cam";
      cam.dataset.cameraId = p.camera_id;
      cam.innerHTML =
        `<img alt="" />` +
        `<div class="camtest-badge">카메라 ${i + 1}</div>` +
        `<div class="camtest-pose">🙌</div>` +
        `<div class="camtest-ok">통과!</div>`;
      el.camtestCams.appendChild(cam);
    });
  }
  // Show the LATEST camera frame via snapshot polling instead of a persistent
  // MJPEG stream. MJPEG decode/network buffers make the video fall further and
  // further behind real time (you 만세 but the tile is still frozen); snapshots
  // always fetch the newest stored frame, so the tile stays current.
  startCamtestSnapshots();
  if (el.camtestCams) {
    el.camtestCams.querySelectorAll(".camtest-cam").forEach((cam) =>
      cam.classList.toggle("is-pass", passed.has(cam.dataset.cameraId))
    );
  }
  const chimeCount = state.camtest_chime || 0;
  if (chimeCount > camtestLastChime) chime();
  camtestLastChime = chimeCount;
}

// Camera-image hint: when the server flags show_hint_cams (stuck on a prompt for
// 10s), flash the live camera feeds big for ~2.5s, then fade out.
let camHintShown = false;
let camHintTimer = null;

// Refresh the hint tiles from the single-frame snapshot endpoint. Unlike a fresh
// MJPEG <img> (which shows BLACK until its first frame boundary arrives — the
// cause of the occasional black tile), the snapshot returns the latest stored
// frame immediately, so every tile shows a real image right away. Polling keeps
// it near-live without holding persistent connections open.
function refreshCamHintSnapshots() {
  if (!el.camHintCams) return;
  const stamp = Date.now();
  el.camHintCams.querySelectorAll(".cam-hint-cam").forEach((cam) => {
    const img = cam.querySelector("img");
    const id = cam.dataset.cameraId;
    if (img && id) img.src = `/api/cameras/${id}/snapshot?t=${stamp}`;
  });
}

function startCamHintSnapshots() {
  if (camHintTimer) return;
  refreshCamHintSnapshots();
  camHintTimer = setInterval(refreshCamHintSnapshots, 150);
}

function stopCamHintSnapshots() {
  if (camHintTimer) {
    clearInterval(camHintTimer);
    camHintTimer = null;
  }
  if (el.camHintCams) {
    el.camHintCams.querySelectorAll(".cam-hint-cam img").forEach((img) =>
      img.removeAttribute("src")
    );
  }
}

function renderCamHint(state) {
  if (!el.camHintOverlay || !el.camHintCams) return;
  const players = Array.isArray(state.players) ? state.players : [];
  // Build the camera tiles once (or when the player count changes). The <img>
  // src is left EMPTY here and only filled (via snapshot polling) while the
  // overlay is actually visible, then cleared again when hidden.
  if (el.camHintCams.childElementCount !== players.length) {
    el.camHintCams.innerHTML = "";
    players.forEach((p, i) => {
      const cam = document.createElement("div");
      cam.className = "cam-hint-cam";
      cam.dataset.cameraId = p.camera_id;
      cam.innerHTML =
        `<img alt="" />` +
        `<div class="cam-hint-badge">${i + 1}</div>`;
      el.camHintCams.appendChild(cam);
    });
  }
  const show = Boolean(state.show_hint_cams);
  if (show !== camHintShown) {
    camHintShown = show;
    if (show) startCamHintSnapshots();
    else stopCamHintSnapshots();
    el.camHintOverlay.classList.toggle("is-visible", show);
    el.camHintOverlay.setAttribute("aria-hidden", show ? "false" : "true");
  }
}

// Attach (active=true) or release (active=false) the live MJPEG <img> streams in
// a container. Releasing clears the src so the persistent connection closes and
// stops consuming the browser's per-host connection budget.
function setCamStreams(container, active) {
  if (!container) return;
  container.querySelectorAll(".cam-hint-cam, .camtest-cam").forEach((cam) => {
    const img = cam.querySelector("img");
    if (!img) return;
    if (active) {
      const id = cam.dataset.cameraId;
      if (id && !img.getAttribute("src")) img.src = `/api/cameras/${id}/stream`;
    } else {
      img.removeAttribute("src");
    }
  });
}

// Fully release the camtest feeds when leaving the camera-test screen so they
// don't keep polling for the rest of the game.
function teardownCamtestStreams() {
  if (!el.camtestCams || el.camtestCams.childElementCount === 0) return;
  stopCamtestSnapshots();
  el.camtestCams.innerHTML = "";
}

// Camtest live view via latest-frame snapshot polling (no persistent MJPEG, so
// it can never fall behind real time — worst case it skips frames, staying live).
let camtestSnapTimer = null;
function refreshCamtestSnapshots() {
  if (!el.camtestCams) return;
  const stamp = Date.now();
  el.camtestCams.querySelectorAll(".camtest-cam").forEach((cam) => {
    const img = cam.querySelector("img");
    const id = cam.dataset.cameraId;
    if (img && id) img.src = `/api/cameras/${id}/snapshot?t=${stamp}`;
  });
}
function startCamtestSnapshots() {
  if (camtestSnapTimer) return;
  refreshCamtestSnapshots();
  camtestSnapTimer = setInterval(refreshCamtestSnapshots, 100);
}
function stopCamtestSnapshots() {
  if (camtestSnapTimer) {
    clearInterval(camtestSnapTimer);
    camtestSnapTimer = null;
  }
  if (el.camtestCams) {
    el.camtestCams.querySelectorAll(".camtest-cam img").forEach((img) =>
      img.removeAttribute("src")
    );
  }
}

// --- Final telepathy report (best + worst keyword) ---
// BEST  = the highest-scoring CLEARED (통과) round.
// WORST = a FAILED (실패) round (lowest score); if nothing failed but more than
//         one round cleared, the lowest-scoring clear stands in as "아쉬웠던 순간".
// If nothing was cleared at all, only a single worst card is shown (no best).
// Returns 1-based round numbers; best/worst may be null.
function bestWorstRounds(scores, results) {
  const n = scores.length;
  if (!n) return null;
  results = results || [];
  const cleared = [];
  const failed = [];
  for (let i = 0; i < n; i++) {
    (results[i] ? cleared : failed).push(i);
  }
  const best = cleared.length
    ? cleared.reduce((a, b) => (scores[b] > scores[a] ? b : a))
    : null;
  let worst = null;
  if (failed.length) {
    worst = failed.reduce((a, b) => (scores[b] < scores[a] ? b : a));
  } else if (cleared.length > 1) {
    worst = cleared.reduce((a, b) => (scores[b] < scores[a] ? b : a));
  }
  if (best === null && worst === null) return null;
  return {
    best: best === null ? null : best + 1,
    worst: worst === null ? null : worst + 1,
  };
}

function reportCardEl(kind, roundNo, prompts, passed) {
  const cap = roundCaptures[roundNo] || {};
  const word = cap.prompt || prompts[roundNo - 1] || "—";
  const div = document.createElement("div");
  div.className = `report-card report-${kind}`;
  let shots = (cap.images || [])
    .filter(Boolean)
    .map((src) => `<img src="${src}" alt="" />`)
    .join("");
  // Fallback: a round with no client-captured composite (e.g. a timed-out round,
  // which has no result screen) still has the real frames the server stored for
  // it — use those directly. Broken/missing frames remove themselves on error.
  if (!shots) {
    shots = PLAYER_INDICES.map(
      (i) => `<img src="/api/game/result-frame/${roundNo}/${i}.jpg" alt="" onerror="this.remove()" />`
    ).join("");
  }
  div.innerHTML =
    `<div class="report-badge">${
      kind === "best" ? "🏆 베스트 호흡" : "🫣 아쉬웠던 순간"
    }</div>` +
    `<div class="report-shots">${
      shots || '<span class="report-noshot">스냅샷 없음</span>'
    }</div>` +
    `<div class="report-word">'${word}'</div>` +
    `<div class="report-result">${passed ? "✅ 통과" : "❌ 실패"}</div>` +
    `<div class="report-caption">${
      kind === "best"
        ? "이 제시어에서 호흡이 가장 잘 맞았어요!"
        : "이 제시어가 제일 아슬아슬했어요."
    }</div>`;
  return div;
}

function renderReport(state) {
  if (!el.reportCards) return;
  const scores = state.round_scores || [];
  const results = state.round_results || [];
  const prompts = state.prompts || [];
  el.reportCards.innerHTML = "";
  const bw = bestWorstRounds(scores, results);
  if (!bw) return;
  if (bw.best) {
    el.reportCards.appendChild(
      reportCardEl("best", bw.best, prompts, results[bw.best - 1])
    );
  }
  if (bw.worst && bw.worst !== bw.best) {
    el.reportCards.appendChild(
      reportCardEl("worst", bw.worst, prompts, results[bw.worst - 1])
    );
  }
}

function loadImage(src) {
  return new Promise((resolve) => {
    if (!src) {
      resolve(null);
      return;
    }
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => resolve(null);
    img.src = src;
  });
}

// Rasterise the on-screen MC 민수 SVG so it can be drawn onto the report canvas.
// Colours are inline attributes on the SVG, so a static (non-animated) snapshot
// renders correctly; resolves to null if anything goes wrong.
function svgToImage(svgEl, width) {
  return new Promise((resolve) => {
    if (!svgEl) {
      resolve(null);
      return;
    }
    try {
      const clone = svgEl.cloneNode(true);
      clone.setAttribute("width", String(width));
      clone.setAttribute("height", String(Math.round(width * 1.1))); // viewBox 200×220
      const xml = new XMLSerializer().serializeToString(clone);
      const src =
        "data:image/svg+xml;charset=utf-8," + encodeURIComponent(xml);
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = () => resolve(null);
      img.src = src;
    } catch {
      resolve(null);
    }
  });
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

function wrapText(ctx, text, cx, top, maxWidth, lineHeight) {
  const words = (text || "").split(/\s+/);
  let line = "";
  let y = top;
  words.forEach((word) => {
    const test = line ? `${line} ${word}` : word;
    if (ctx.measureText(test).width > maxWidth && line) {
      ctx.fillText(line, cx, y);
      line = word;
      y += lineHeight;
    } else {
      line = test;
    }
  });
  if (line) ctx.fillText(line, cx, y);
  return y;
}

// Same line-break logic as wrapText but WITHOUT drawing — used to size the
// export canvas before anything is painted, so a long report never pushes the
// cards under the footer.
function measureWrapHeight(ctx, text, maxWidth, lineHeight, top) {
  const words = (text || "").split(/\s+/);
  let line = "";
  let y = top;
  words.forEach((word) => {
    const test = line ? `${line} ${word}` : word;
    if (ctx.measureText(test).width > maxWidth && line) {
      line = word;
      y += lineHeight;
    } else {
      line = test;
    }
  });
  return y;
}

async function drawReportSection(ctx, top, accent, label, word, resultText, images) {
  const W = 1080;
  const cardH = 360;
  roundRect(ctx, 80, top, W - 160, cardH, 28);
  ctx.fillStyle = "rgba(255,255,255,0.05)";
  ctx.fill();
  ctx.strokeStyle = accent;
  ctx.lineWidth = 3;
  ctx.stroke();

  // Section label (top-left).
  ctx.textAlign = "left";
  ctx.textBaseline = "alphabetic";
  ctx.fillStyle = accent;
  ctx.font = "bold 32px Inter, 'Noto Sans KR', sans-serif";
  ctx.fillText(label, 120, top + 52);

  // Pass/fail as a pill in the top-RIGHT corner so it can never collide with the
  // keyword (which lives at the bottom-center).
  ctx.font = "900 28px Inter, 'Noto Sans KR', sans-serif";
  const padX = 22;
  const bh = 46;
  const bw = ctx.measureText(resultText).width + padX * 2;
  const bx = W - 120 - bw;
  const by = top + 22;
  ctx.fillStyle = accent;
  roundRect(ctx, bx, by, bw, bh, bh / 2);
  ctx.fill();
  ctx.fillStyle = "#08122b";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(resultText, bx + bw / 2, by + bh / 2 + 1);
  ctx.textBaseline = "alphabetic";

  // Captured shots row.
  const shots = (images || []).filter(Boolean).slice(0, 3);
  const loaded = await Promise.all(shots.map(loadImage));
  const thumbW = 150;
  const thumbH = 186;
  const gap = 24;
  const cards = loaded.length ? loaded : [null];
  const totalW = cards.length * thumbW + (cards.length - 1) * gap;
  let tx = (W - totalW) / 2;
  const ty = top + 92;
  cards.forEach((img) => {
    ctx.save();
    roundRect(ctx, tx, ty, thumbW, thumbH, 16);
    ctx.clip();
    ctx.fillStyle = "#0d1230";
    ctx.fillRect(tx, ty, thumbW, thumbH);
    if (img) ctx.drawImage(img, tx, ty, thumbW, thumbH);
    ctx.restore();
    ctx.strokeStyle = "rgba(108,139,255,0.5)";
    ctx.lineWidth = 2;
    roundRect(ctx, tx, ty, thumbW, thumbH, 16);
    ctx.stroke();
    tx += thumbW + gap;
  });

  // Keyword on its own line at the bottom-center (never overlaps the pill).
  ctx.textAlign = "center";
  ctx.fillStyle = "#ffffff";
  ctx.font = "900 46px 'Black Han Sans', 'Noto Sans KR', Inter, sans-serif";
  ctx.fillText(`'${word}'`, W / 2, top + cardH - 30);
}

// Prefer the client-captured composite (photo + skeleton); fall back to the raw
// server frames so a timed-out round (no result screen) still shows real shots.
function reportSectionImages(cap, roundNo) {
  if (cap.images && cap.images.filter(Boolean).length) return cap.images;
  return PLAYER_INDICES.map((i) => `/api/game/result-frame/${roundNo}/${i}.jpg`);
}

async function buildReportImage() {
  const state = lastFinalState;
  if (!state) return;
  const scores = state.round_scores || [];
  const results = state.round_results || [];
  const prompts = state.prompts || [];
  const bw = bestWorstRounds(scores, results);
  if (!bw) return;

  const W = 1080;
  const cardH = 360;
  const showBest = !!bw.best;
  const showWorst = !!bw.worst && bw.worst !== bw.best;

  // --- Measure pass: figure out where the LLM report text ends (and thus where
  // the cards start) BEFORE creating the canvas, so we can grow the height to
  // fit every card. Otherwise a long report pushes the last card under the
  // footer / MC avatar and they overlap in the saved PNG.
  const team = state.team_name ? `🏷 ${state.team_name}` : "";
  const titleY = team ? 348 : 322;
  const measure = document.createElement("canvas").getContext("2d");
  measure.font = "26px Inter, 'Noto Sans KR', sans-serif";
  const reportEndY = measureWrapHeight(
    measure,
    toCaption(state.final_report) || "",
    W - 200,
    36,
    titleY + 52,
  );
  const firstTop = Math.max(titleY + 96, reportEndY + 40);
  let contentBottom = firstTop;
  if (showBest) contentBottom = firstTop + cardH;
  if (showWorst) {
    const worstTop = showBest ? firstTop + 400 : firstTop;
    contentBottom = worstTop + cardH;
  }
  // Leave room below the last card for the footer line + MC avatar.
  const H = Math.max(1350, Math.round(contentBottom + 260));
  const cv = document.createElement("canvas");
  cv.width = W;
  cv.height = H;
  const ctx = cv.getContext("2d");

  const bg = ctx.createLinearGradient(0, 0, W, H);
  bg.addColorStop(0, "#0b1030");
  bg.addColorStop(1, "#1a1140");
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, W, H);

  ctx.textAlign = "center";
  ctx.textBaseline = "alphabetic";
  ctx.fillStyle = "#00ffc6";
  ctx.font = "bold 36px Inter, 'Noto Sans KR', sans-serif";
  ctx.fillText("이구동성 · 텔레파시 결과", W / 2, 78);

  // Team name up top.
  if (team) {
    ctx.fillStyle = "#ffffff";
    ctx.font = "900 46px Inter, 'Noto Sans KR', sans-serif";
    ctx.fillText(team, W / 2, 138);
  }

  // Headline stat: how many keywords cleared, and in how many seconds
  // (replaces the old raw score number).
  const secs = Number(state.final_seconds || 0).toFixed(1);
  const cleared = state.cleared_count || 0;
  ctx.fillStyle = "#8fe9ff";
  ctx.font = "bold 40px Inter, 'Noto Sans KR', sans-serif";
  ctx.fillText(`⏱ ${secs}초 안에`, W / 2, team ? 202 : 176);
  ctx.fillStyle = "#ffffff";
  ctx.font = "900 88px Inter, 'Noto Sans KR', sans-serif";
  ctx.fillText(`${cleared}개 클리어!`, W / 2, team ? 292 : 266);

  // MC title line.
  ctx.fillStyle = "#cfd8ff";
  ctx.font = "bold 40px Inter, 'Noto Sans KR', sans-serif";
  ctx.fillText(toCaption(state.final_title) || "", W / 2, titleY);

  // LLM telepathy report (wrapped). Drawn from the same start as the measure
  // pass above, so the cards land exactly where the canvas was sized for.
  ctx.fillStyle = "#aab4e0";
  ctx.font = "26px Inter, 'Noto Sans KR', sans-serif";
  wrapText(
    ctx,
    toCaption(state.final_report) || "",
    W / 2,
    titleY + 52,
    W - 200,
    36,
  );

  let sectionTop = firstTop;
  if (showBest) {
    const cap = roundCaptures[bw.best] || {};
    await drawReportSection(
      ctx,
      sectionTop,
      "#00ffc6",
      "🏆 베스트 호흡",
      cap.prompt || prompts[bw.best - 1] || "—",
      results[bw.best - 1] ? "✅ 통과" : "❌ 실패",
      reportSectionImages(cap, bw.best),
    );
    sectionTop += 400;
  }
  if (showWorst) {
    const cap = roundCaptures[bw.worst] || {};
    await drawReportSection(
      ctx,
      sectionTop,
      "#ff6b6b",
      "🫣 아쉬웠던 순간",
      cap.prompt || prompts[bw.worst - 1] || "—",
      results[bw.worst - 1] ? "✅ 통과" : "❌ 실패",
      reportSectionImages(cap, bw.worst),
    );
  }

  ctx.textAlign = "center";
  ctx.fillStyle = "#6c8bff";
  ctx.font = "24px Inter, sans-serif";
  ctx.fillText("ON-DEVICE AI · AI MC 민수", W / 2, H - 40);

  // MC 민수도 결과 사진에 귀엽게 같이 찍히도록 우측 하단에 살짝 얹는다.
  const mcImg = await svgToImage(
    document.querySelector("#mc-avatar svg"),
    400,
  );
  if (mcImg) {
    const mw = 190;
    const mh = mw * 1.1;
    const mx = W - mw - 46;
    const my = H - mh - 64;
    // 말풍선처럼 짧은 한마디를 머리 위에 띄워 함께 등장한 느낌을 준다.
    ctx.save();
    ctx.textAlign = "center";
    const tag = "수고했어요! 🎤";
    ctx.font = "bold 22px Inter, sans-serif";
    const tagW = ctx.measureText(tag).width + 28;
    const tagX = mx + mw / 2 - tagW / 2;
    const tagY = my - 44;
    ctx.fillStyle = "rgba(20, 26, 56, 0.94)";
    roundRect(ctx, tagX, tagY, tagW, 36, 14);
    ctx.fill();
    ctx.fillStyle = "#cfd8ff";
    ctx.fillText(tag, mx + mw / 2, tagY + 24);
    ctx.restore();
    ctx.drawImage(mcImg, mx, my, mw, mh);
  }

  const link = document.createElement("a");
  link.download = `telepathy_${Date.now()}.png`;
  link.href = cv.toDataURL("image/png");
  link.click();
}

// Push the entered team name / category to the server so the T-pose gesture on
// the idle screen can auto-start the game (no button).
let stageTimer = null;
async function stageGame() {
  try {
    await fetch("/api/game/stage", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ theme: selectedTheme, team_name: getTeamName() }),
    });
  } catch {
    /* best effort; will retry on the next edit */
  }
}

function scheduleStage() {
  if (stageTimer) clearTimeout(stageTimer);
  stageTimer = setTimeout(stageGame, 250);
}

async function resetGame() {
  if (!window.confirm("게임을 처음부터 다시 시작할까요?")) return;
  stopSpeaking();
  lastResultRound = 0;
  lastResultPoseRound = 0;
  currentRoundMeta = null;
  Object.keys(roundCaptures).forEach((k) => delete roundCaptures[k]);
  // 처음으로 돌아가면 이전 팀 이름은 비워 placeholder가 다시 보이게 한다.
  if (el.teamName) el.teamName.value = "";
  try {
    await fetch("/api/game/reset", { method: "POST" });
  } catch {
    /* the next websocket snapshot will reflect the state */
  }
  // Clear the staged team name so a stale name can't auto-start the next game.
  stageGame();
}

let selectedTheme = "상황";
if (el.themePicker) {
  const chips = el.themePicker.querySelectorAll(".theme-chip");
  const active = el.themePicker.querySelector(".theme-chip.is-active");
  if (active) selectedTheme = active.dataset.theme || selectedTheme;
  chips.forEach((chip) => {
    chip.addEventListener("click", () => {
      chips.forEach((c) => c.classList.remove("is-active"));
      chip.classList.add("is-active");
      selectedTheme = chip.dataset.theme || "상황";
      stageGame();
    });
  });
}

el.restartBtn.addEventListener("click", resetGame);
if (el.restartGameBtn) el.restartGameBtn.addEventListener("click", resetGame);
if (el.saveReportBtn) el.saveReportBtn.addEventListener("click", buildReportImage);
if (el.leaderboardReset) el.leaderboardReset.addEventListener("click", resetLeaderboard);
if (el.teamName) el.teamName.addEventListener("input", scheduleStage);
// Stage the initial (possibly empty) team name + default category on load.
stageGame();

// --- Team leaderboard (accumulates across games, per team name) ---
function getTeamName() {
  return ((el.teamName && el.teamName.value) || "").trim().slice(0, 40);
}

async function fetchLeaderboard() {
  try {
    const res = await fetch("/api/leaderboard?limit=50");
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

const LB_MEDALS = ["🥇", "🥈", "🥉"];

function renderLeaderboard(data, meId, listEl, emptyEl) {
  const list = listEl || el.leaderboardList;
  const empty = emptyEl || el.leaderboardEmpty;
  if (!list) return;
  const entries = (data && data.entries) || [];
  list.innerHTML = "";
  const hasAny = entries.length > 0;
  list.classList.toggle("is-hidden", !hasAny);
  if (empty) empty.classList.toggle("is-hidden", hasAny);
  entries.slice(0, 10).forEach((e) => {
    const li = document.createElement("li");
    li.className =
      "leaderboard-row" +
      (e.rank <= 3 ? " is-top" : "") +
      (meId && e.id === meId ? " is-me" : "");
    const rank = document.createElement("span");
    rank.className = "lb-rank";
    rank.textContent = e.rank <= 3 ? LB_MEDALS[e.rank - 1] : String(e.rank);
    const team = document.createElement("span");
    team.className = "lb-team";
    team.textContent = e.team_name;
    if (e.title) {
      const sub = document.createElement("small");
      sub.textContent = e.title;
      team.appendChild(sub);
    }
    const score = document.createElement("span");
    score.className = "lb-score";
    score.textContent = String(Math.round(e.score));
    li.append(rank, team, score);
    list.appendChild(li);
  });
}

async function refreshLeaderboardIdle() {
  const data = await fetchLeaderboard();
  // On a transient fetch error keep whatever's on screen instead of flashing the
  // empty "아직 기록이 없습니다" state.
  if (!data) return;
  renderLeaderboard(data, null);
}

async function refreshLeaderboardFinal(state) {
  const meId = state.leaderboard_id || null;
  const data = await fetchLeaderboard();
  if (!data) return;
  renderLeaderboard(data, meId, el.finalLeaderboardList, el.finalLeaderboardEmpty);
  if (el.finalRank) {
    const me = data && (data.entries || []).find((e) => e.id === meId);
    el.finalRank.textContent = me ? `전체 ${data.count}팀 중 ${me.rank}위` : "";
  }
}

async function resetLeaderboard() {
  const answer = window.prompt(
    '리더보드를 정말 초기화할까요? 모든 팀 기록이 삭제됩니다.\n계속하려면 "초기화" 를 입력하세요.'
  );
  if (answer === null) return;
  if (answer.trim() !== "초기화") {
    window.alert("입력이 일치하지 않아 취소되었습니다.");
    return;
  }
  try {
    const res = await fetch("/api/leaderboard/reset", { method: "POST" });
    const data = await res.json();
    window.alert(`리더보드를 초기화했습니다. (기록 ${data.removed || 0}개 삭제)`);
  } catch {
    window.alert("초기화에 실패했습니다.");
  }
  refreshLeaderboardIdle();
}

// --- Skeleton rendering on the game screen ---
const POSE_CONNECTIONS = [
  ["left_shoulder", "right_shoulder"],
  ["left_shoulder", "left_elbow"],
  ["left_elbow", "left_wrist"],
  ["right_shoulder", "right_elbow"],
  ["right_elbow", "right_wrist"],
  ["left_shoulder", "left_hip"],
  ["right_shoulder", "right_hip"],
  ["left_hip", "right_hip"],
  ["left_hip", "left_knee"],
  ["left_knee", "left_ankle"],
  ["right_hip", "right_knee"],
  ["right_knee", "right_ankle"],
  ["nose", "left_shoulder"],
  ["nose", "right_shoulder"],
];
const SKELETON_VISIBILITY = 0.5;
let latestPlayers = [];
let currentPhase = "idle";
let latestGauge = 0;
let skeletonBusy = false;

function drawSkeletonCard(canvas, pose) {
  const fit = fitFrame(canvas, pose && pose.frame_width, pose && pose.frame_height);
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, fit.width, fit.height);
  if (!pose || !pose.person_detected || !Array.isArray(pose.keypoints)) return;
  strokeSkeleton(ctx, pose, fit);
}

// Letterbox the source camera frame (landscape) inside a portrait card and
// return the placement rect, so the real photo and the pose skeleton can be
// drawn with one shared transform — guaranteeing they line up pixel-for-pixel.
function fitFrame(canvas, frameWidth, frameHeight) {
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  if (canvas.width !== width) canvas.width = width;
  if (canvas.height !== height) canvas.height = height;
  const aspect = (frameWidth || 4) / (frameHeight || 3);
  let drawW = width;
  let drawH = width / aspect;
  if (drawH > height) {
    drawH = height;
    drawW = height * aspect;
  }
  return {
    width,
    height,
    offX: (width - drawW) / 2,
    offY: (height - drawH) / 2,
    drawW,
    drawH,
  };
}

function strokeSkeleton(ctx, pose, fit) {
  const px = (kp) => fit.offX + kp.x * fit.drawW;
  const py = (kp) => fit.offY + kp.y * fit.drawH;
  const points = {};
  for (const keypoint of pose.keypoints) points[keypoint.name] = keypoint;
  const visible = (kp) => kp && (kp.visibility == null || kp.visibility >= SKELETON_VISIBILITY);

  ctx.lineWidth = Math.max(1, fit.width * 0.01);
  ctx.lineCap = "round";
  ctx.strokeStyle = "rgba(0, 255, 198, 0.8)";
  ctx.shadowColor = "rgba(0, 255, 198, 0.45)";
  ctx.shadowBlur = 3;
  for (const [a, b] of POSE_CONNECTIONS) {
    const pa = points[a];
    const pb = points[b];
    if (!visible(pa) || !visible(pb)) continue;
    ctx.beginPath();
    ctx.moveTo(px(pa), py(pa));
    ctx.lineTo(px(pb), py(pb));
    ctx.stroke();
  }

  ctx.shadowBlur = 0;
  ctx.fillStyle = "#ffffff";
  const radius = Math.max(1, fit.width * 0.009);
  for (const keypoint of pose.keypoints) {
    if (!visible(keypoint)) continue;
    ctx.beginPath();
    ctx.arc(px(keypoint), py(keypoint), radius, 0, Math.PI * 2);
    ctx.fill();
  }
}

// "AI Vision" reveal: paint the real photo from the scored moment, then overlay
// the on-device pose skeleton in the exact same frame transform. Falls back to a
// dark card (skeleton only) when no photo was captured.
function drawVisionCard(canvas, image, pose) {
  const frameWidth = (pose && pose.frame_width) || (image && image.naturalWidth);
  const frameHeight = (pose && pose.frame_height) || (image && image.naturalHeight);
  const fit = fitFrame(canvas, frameWidth, frameHeight);
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, fit.width, fit.height);

  if (image) {
    ctx.drawImage(image, fit.offX, fit.offY, fit.drawW, fit.drawH);
    // Dim the photo so the neon skeleton reads clearly as an AI overlay.
    ctx.fillStyle = "rgba(7, 11, 32, 0.28)";
    ctx.fillRect(fit.offX, fit.offY, fit.drawW, fit.drawH);
  } else {
    ctx.fillStyle = "#0d1230";
    ctx.fillRect(0, 0, fit.width, fit.height);
  }

  if (pose && pose.person_detected && Array.isArray(pose.keypoints)) {
    strokeSkeleton(ctx, pose, fit);
  }
}

// Reveal every player's real photo + skeleton for the just-scored round, then
// snapshot the composited cards for the final report. Runs once per round.
async function revealResultFrames(round, poses) {
  await Promise.all(
    PLAYER_INDICES.map(async (index) => {
      const canvas = document.getElementById(`result-skel-${index}`);
      const card = document.getElementById(`result-skel-card-${index}`);
      if (!canvas) return;
      const pose = Array.isArray(poses) ? poses[index] : null;
      const image = await loadImage(`/api/game/result-frame/${round}/${index}.jpg`);
      drawVisionCard(canvas, image, pose);
      if (card) {
        const live = Boolean(image) || Boolean(pose && pose.person_detected);
        card.classList.toggle("ready", live);
      }
    }),
  );
  // Canvases now hold the photo+skeleton composite; save it for the report.
  captureRoundSnapshot("result-skel");
}

function skeletonPrefix() {
  return null;
}

async function refreshSkeletons() {
  const prefix = skeletonPrefix();
  if (!prefix) return;
  if (skeletonBusy || latestPlayers.length === 0) return;
  skeletonBusy = true;
  try {
    await Promise.all(
      latestPlayers.map(async (player, index) => {
        const canvas = document.getElementById(`${prefix}-${index}`);
        const card = document.getElementById(`${prefix}-card-${index}`);
        let pose = null;
        if (player && player.camera_id) {
          try {
            const response = await fetch(`/api/cameras/${player.camera_id}/pose`, { cache: "no-store" });
            if (response.ok) pose = await response.json();
          } catch {
            pose = null;
          }
        }
        if (canvas) drawSkeletonCard(canvas, pose);
        if (card) card.classList.toggle("ready", Boolean(pose && pose.person_detected));
        return pose;
      }),
    );
    captureRoundSnapshot(prefix);
  } finally {
    skeletonBusy = false;
  }
}

// Save the result-screen skeletons once per round for the final report image.
function captureRoundSnapshot(prefix) {
  if (prefix !== "result-skel" || !currentRoundMeta) return;
  const roundNo = currentRoundMeta.round;
  if (roundCaptures[roundNo]) return;
  const images = [];
  for (let i = 0; i < playerCount; i += 1) {
    const canvas = document.getElementById(`result-skel-${i}`);
    if (!canvas) continue;
    try {
      images.push(canvas.toDataURL("image/png"));
    } catch {
      images.push(null);
    }
  }
  roundCaptures[roundNo] = { ...currentRoundMeta, images };
}

setInterval(refreshSkeletons, 150);

function connect() {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const socket = new WebSocket(`${protocol}://${window.location.host}/api/game/ws`);

  socket.addEventListener("open", () => {
    el.conn.textContent = "● LIVE";
    el.conn.classList.add("online");
  });

  socket.addEventListener("message", (event) => {
    try {
      render(JSON.parse(event.data));
    } catch {
      /* ignore malformed frames */
    }
  });

  socket.addEventListener("close", () => {
    el.conn.textContent = "재연결 중…";
    el.conn.classList.remove("online");
    setTimeout(connect, 1500);
  });

  socket.addEventListener("error", () => socket.close());
}

setGauge(0);
connect();
