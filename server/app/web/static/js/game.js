const GAUGE_CIRCUMFERENCE = 2 * Math.PI * 104;

const screens = {
  idle: document.getElementById("screen-idle"),
  category: document.getElementById("screen-category"),
  intro: document.getElementById("screen-intro"),
  countdown: document.getElementById("screen-countdown"),
  playing: document.getElementById("screen-playing"),
  result: document.getElementById("screen-result"),
  finished: document.getElementById("screen-final"),
};

const el = {
  conn: document.getElementById("conn"),
  roundPill: document.getElementById("round-pill"),
  restartBtn: document.getElementById("restart-btn"),
  idlePlayers: document.getElementById("idle-players"),
  cdPrompt: document.getElementById("cd-prompt"),
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
  finalTeam: document.getElementById("final-team"),
  finalRank: document.getElementById("final-rank"),
  tposeCue: document.getElementById("tpose-cue"),
  tposeProgressFill: document.getElementById("tpose-progress-fill"),
  catCards: document.getElementById("cat-cards"),
  catConfirmFill: document.getElementById("cat-confirm-fill"),
  mergedSkel: document.getElementById("merged-skel-canvas"),
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

function setMcTalking(on, text) {
  if (el.mcStage) el.mcStage.classList.toggle("is-talking", Boolean(on));
  // 인트로·결산 화면에선 같은 멘트가 이미 화면 가운데에 떠 있으므로 말풍선은 띄우지 않는다.
  // (민수는 입만 움직이며 읽어주는 듯한 연출)
  const suppressBubble = currentPhase === "intro" || currentPhase === "finished";
  if (on && text && !suppressBubble && el.mcLiveText && el.mcLiveBubble) {
    el.mcLiveText.textContent = text;
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
    utter.onend = () => { setMcTalking(false); if (currentPhase === "intro") sendIntroDone(); };
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
        if (currentPhase === "intro") sendIntroDone();
      };
      audio.onerror = () => {
        setMcTalking(false);
        speakLine(text);
      };
      audio.play().catch(() => speakLine(text));
    })
    .catch(() => {
      // edge-tts generation takes ~1s; retry a few times then fall back.
      if (attempt < 10 && !tts.muted && id === tts.lastSpokenId) {
        setTimeout(() => playServerAudio(id, text, attempt + 1), 400);
      } else if (!tts.muted && id === tts.lastSpokenId) {
        speakLine(text);
      }
    });
}

function maybeSpeak(state) {
  const id = state.speech_id || 0;
  if (id <= tts.lastSpokenId) return;
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
let lastFinalState = null;

function updatePlayerDots(dots, players) {
  dots.forEach((dot, index) => {
    const player = players && players[index];
    dot.classList.toggle("ready", Boolean(player && player.ready));
  });
}

function showScreen(phase) {
  Object.entries(screens).forEach(([name, node]) => {
    node.classList.toggle("is-active", name === phase);
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
    el.roundPill.textContent = `ROUND ${state.round_number} / ${state.total_rounds}`;
  }

  updatePlayerDots(idleDots, state.players);
  updatePlayerDots(introDots, state.players);
  if (el.mcStage) {
    // MC 민수 무대 위치를 단계별로 정한다:
    //  - intro: 코너에 머문 채 살짝 커져 인사 멘트를 한다 (is-center)
    //  - finished: 중앙의 최종 리포트 옆으로 날아가 그 문구를 읽어주는 자리 (is-final)
    //  - 그 외 진행 중: 옆에서 귀신처럼 둥둥 떠다닌다 (is-side)
    const mcHidden = state.phase === "idle";
    const mcCenter = state.phase === "intro";
    const mcFinal = state.phase === "finished";
    el.mcStage.classList.toggle("is-hidden", mcHidden);
    el.mcStage.classList.toggle("is-center", !mcHidden && mcCenter);
    el.mcStage.classList.toggle("is-final", !mcHidden && mcFinal);
    el.mcStage.classList.toggle("is-side", !mcHidden && !mcCenter && !mcFinal);
  }
  // The "start over" button only makes sense once a game is under way.
  if (el.restartGameBtn) el.restartGameBtn.classList.toggle("is-hidden", state.phase === "idle");

  latestPlayers = Array.isArray(state.players) ? state.players : [];
  currentPhase = state.phase;

  if (state.phase === "intro") {
    el.introSpeech.textContent = state.speech || "민수가 인사 중…";
  }

  if (state.phase === "category" && prevPhase !== "category") lastCatIndex = -1;
  if (state.phase === "category") renderCategory(state);

  if (state.phase === "countdown") {
    el.cdPrompt.textContent = state.prompt || "";
    const left = state.time_left == null ? 0 : state.time_left;
    el.cdNumber.textContent = String(Math.max(1, Math.ceil(left)));
  }

  if (state.phase === "playing") {
    el.playPrompt.textContent = state.prompt || "";
    setGauge(state.gauge);
    el.playTagline.textContent = taglineFor(state.gauge, state.ready_count);
    if (el.coachText && state.coach) el.coachText.textContent = state.coach;
    // Coaching is voiced by the server in the same MC voice (edge-tts) via the
    // shared speech pipeline, so we no longer speak it with the browser voice.

    const duration = state.phase_duration || 1;
    const left = state.time_left == null ? 0 : state.time_left;
    el.timerFill.style.width = `${Math.max(0, Math.min(100, (left / duration) * 100))}%`;
    el.timerText.textContent = left.toFixed(1);
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
      el.mcText.textContent = state.mc_comment;
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
    if (el.finalTeam) {
      el.finalTeam.textContent = state.team_name ? `🏷 ${state.team_name}` : "";
    }
    if (state.final_status === "pending") {
      el.finalReport.textContent = "📜 AI가 텔레파시 궤합을 분석 중…";
      el.finalReport.classList.add("is-pending");
    } else if (state.final_report) {
      el.finalReport.textContent = state.final_report;
      el.finalReport.classList.remove("is-pending");
    } else {
      el.finalReport.textContent = "";
      el.finalReport.classList.remove("is-pending");
    }
    el.finalBreakdown.innerHTML = "";
    (state.round_scores || []).forEach((score, index) => {
      const li = document.createElement("li");
      li.innerHTML = `<span class="fb-round">R${index + 1}</span><span class="fb-score">${Math.round(
        score,
      )}</span>`;
      el.finalBreakdown.appendChild(li);
    });
    renderReport(state);
  }
}

// --- Body-controlled category picker ---
let lastCatIndex = -1;
function renderCategory(state) {
  const options = state.category_options || [];
  const index = state.category_index || 0;
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
}

// --- Final telepathy report (best / worst rounds) ---
function bestWorstRounds(scores) {
  if (!scores.length) return null;
  let best = 0;
  let worst = 0;
  scores.forEach((s, i) => {
    if (s > scores[best]) best = i;
    if (s < scores[worst]) worst = i;
  });
  return { best: best + 1, worst: worst + 1 };
}

function reportCardEl(kind, roundNo, scores, prompts) {
  const cap = roundCaptures[roundNo] || {};
  const word = cap.prompt || prompts[roundNo - 1] || "—";
  const score = Math.round(scores[roundNo - 1] || 0);
  const div = document.createElement("div");
  div.className = `report-card report-${kind}`;
  const shots = (cap.images || [])
    .filter(Boolean)
    .map((src) => `<img src="${src}" alt="" />`)
    .join("");
  div.innerHTML =
    `<div class="report-badge">${
      kind === "best" ? "🏆 베스트 호흡" : "💥 텔레파시 대참사"
    }</div>` +
    `<div class="report-shots">${
      shots || '<span class="report-noshot">스냅샷 없음</span>'
    }</div>` +
    `<div class="report-word">'${word}'</div>` +
    `<div class="report-score">${score}점</div>` +
    `<div class="report-caption">${
      kind === "best"
        ? "이 단어에서 모두 같은 동작! 환상의 호흡이었어요."
        : "이 단어에선 제각각… 서로 다른 우주에 다녀왔네요 ㅋㅋ"
    }</div>`;
  return div;
}

function renderReport(state) {
  if (!el.reportCards) return;
  const scores = state.round_scores || [];
  const prompts = state.prompts || [];
  el.reportCards.innerHTML = "";
  const bw = bestWorstRounds(scores);
  if (!bw) return;
  el.reportCards.appendChild(reportCardEl("best", bw.best, scores, prompts));
  if (bw.worst !== bw.best) {
    el.reportCards.appendChild(reportCardEl("worst", bw.worst, scores, prompts));
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

async function drawReportSection(ctx, top, accent, label, word, score, images) {
  const W = 1080;
  roundRect(ctx, 80, top, W - 160, 360, 28);
  ctx.fillStyle = "rgba(255,255,255,0.05)";
  ctx.fill();
  ctx.strokeStyle = accent;
  ctx.lineWidth = 3;
  ctx.stroke();

  ctx.textAlign = "left";
  ctx.fillStyle = accent;
  ctx.font = "bold 34px Inter, sans-serif";
  ctx.fillText(label, 120, top + 56);

  const shots = (images || []).filter(Boolean).slice(0, 3);
  const loaded = await Promise.all(shots.map(loadImage));
  const thumbW = 150;
  const thumbH = 190;
  const gap = 24;
  const cards = loaded.length ? loaded : [null];
  const totalW = cards.length * thumbW + (cards.length - 1) * gap;
  let tx = (W - totalW) / 2;
  const ty = top + 80;
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

  ctx.textAlign = "center";
  ctx.fillStyle = "#ffffff";
  ctx.font = "900 52px 'Black Han Sans', Inter, sans-serif";
  ctx.fillText(`'${word}'`, W / 2 - 70, top + 330);
  ctx.fillStyle = accent;
  ctx.font = "bold 40px Inter, sans-serif";
  ctx.fillText(`${score}점`, W / 2 + 130, top + 330);
}

async function buildReportImage() {
  const state = lastFinalState;
  if (!state) return;
  const scores = state.round_scores || [];
  const prompts = state.prompts || [];
  const bw = bestWorstRounds(scores);
  if (!bw) return;

  const W = 1080;
  const H = 1350;
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
  ctx.fillStyle = "#00ffc6";
  ctx.font = "bold 38px Inter, sans-serif";
  ctx.fillText("이구동성 · 텔레파시 결과", W / 2, 84);

  ctx.fillStyle = "#ffffff";
  ctx.font = "900 130px Inter, sans-serif";
  ctx.fillText(String(Math.round(state.total_score || 0)), W / 2, 230);
  ctx.fillStyle = "#cfd8ff";
  ctx.font = "bold 44px Inter, sans-serif";
  ctx.fillText(state.final_title || "", W / 2, 296);

  ctx.fillStyle = "#aab4e0";
  ctx.font = "26px Inter, sans-serif";
  wrapText(ctx, state.final_report || "", W / 2, 356, W - 200, 36);

  const bestCap = roundCaptures[bw.best] || {};
  const worstCap = roundCaptures[bw.worst] || {};
  await drawReportSection(
    ctx,
    450,
    "#00ffc6",
    "🏆 베스트 호흡",
    bestCap.prompt || prompts[bw.best - 1] || "—",
    Math.round(scores[bw.best - 1] || 0),
    bestCap.images,
  );
  if (bw.worst !== bw.best) {
    await drawReportSection(
      ctx,
      850,
      "#ff6b6b",
      "💥 텔레파시 대참사",
      worstCap.prompt || prompts[bw.worst - 1] || "—",
      Math.round(scores[bw.worst - 1] || 0),
      worstCap.images,
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

function renderLeaderboard(data, meId) {
  if (!el.leaderboardList) return;
  const entries = (data && data.entries) || [];
  el.leaderboardList.innerHTML = "";
  const hasAny = entries.length > 0;
  el.leaderboardList.classList.toggle("is-hidden", !hasAny);
  if (el.leaderboardEmpty) el.leaderboardEmpty.classList.toggle("is-hidden", hasAny);
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
    el.leaderboardList.appendChild(li);
  });
}

async function refreshLeaderboardIdle() {
  renderLeaderboard(await fetchLeaderboard(), null);
}

async function refreshLeaderboardFinal(state) {
  const meId = state.leaderboard_id || null;
  const data = await fetchLeaderboard();
  renderLeaderboard(data, meId);
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

// --- Merged skeleton: torso-normalised overlay of all players ---
// Bones shown in the merged view (face + upper-body, matches scoring bones).
const MERGED_CONNECTIONS = [
  ["left_ear", "nose"],
  ["right_ear", "nose"],
  ["nose", "left_shoulder"],
  ["nose", "right_shoulder"],
  ["left_shoulder", "right_shoulder"],
  ["left_shoulder", "left_elbow"],
  ["left_elbow", "left_wrist"],
  ["right_shoulder", "right_elbow"],
  ["right_elbow", "right_wrist"],
  ["left_shoulder", "left_hip"],
  ["right_shoulder", "right_hip"],
  ["left_hip", "right_hip"],
];
const MERGED_COLORS = ["#00ffc6", "#ff4d8d", "#7c5cff", "#ffd166"];
const MERGED_VIS = 0.3;

// Normalize all keypoints into torso space:
//   origin = torso centre, unit = torso height, y-up.
// Returns {name -> {nx, ny, visibility}} or null when torso anchors are missing.
function normalizePoseToTorso(pose) {
  if (!pose || !pose.person_detected || !Array.isArray(pose.keypoints)) return null;
  const kps = {};
  pose.keypoints.forEach((kp) => { if (kp && kp.name) kps[kp.name] = kp; });
  const aspect = pose.frame_width && pose.frame_height
    ? pose.frame_width / pose.frame_height : 1.0;
  for (const name of ["left_shoulder", "right_shoulder", "left_hip", "right_hip"]) {
    const kp = kps[name];
    if (!kp || (kp.visibility != null && kp.visibility < MERGED_VIS)) return null;
  }
  const ax = (n) => kps[n].x * aspect;
  const ay = (n) => kps[n].y;
  const smx = (ax("left_shoulder") + ax("right_shoulder")) / 2;
  const smy = (ay("left_shoulder") + ay("right_shoulder")) / 2;
  const hmx = (ax("left_hip") + ax("right_hip")) / 2;
  const hmy = (ay("left_hip") + ay("right_hip")) / 2;
  const torsoH = Math.hypot(smx - hmx, smy - hmy);
  if (torsoH < 0.02) return null;
  const cx = (ax("left_shoulder") + ax("right_shoulder") + ax("left_hip") + ax("right_hip")) / 4;
  const cy = (ay("left_shoulder") + ay("right_shoulder") + ay("left_hip") + ay("right_hip")) / 4;
  const result = {};
  pose.keypoints.forEach((kp) => {
    if (!kp || !kp.name) return;
    result[kp.name] = {
      nx: (kp.x * aspect - cx) / torsoH,
      ny: -((kp.y - cy) / torsoH), // flip y so up = positive
      visibility: kp.visibility,
    };
  });
  return result;
}

function drawMergedSkeletons(canvas, poses) {
  const W = canvas.width, H = canvas.height;
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = "rgba(6,7,13,0.7)";
  ctx.fillRect(0, 0, W, H);
  // torso height maps to 38% of canvas height; origin slightly below centre
  const scale = H * 0.38;
  const originX = W / 2;
  const originY = H * 0.56;
  let anyDrawn = false;
  poses.forEach((pose, i) => {
    const norm = normalizePoseToTorso(pose);
    if (!norm) return;
    anyDrawn = true;
    const color = MERGED_COLORS[i % MERGED_COLORS.length];
    ctx.strokeStyle = color;
    ctx.fillStyle = color;
    ctx.lineWidth = 2;
    ctx.globalAlpha = 0.9;
    MERGED_CONNECTIONS.forEach(([a, b]) => {
      const ka = norm[a], kb = norm[b];
      if (!ka || !kb) return;
      if ((ka.visibility ?? 1) < MERGED_VIS || (kb.visibility ?? 1) < MERGED_VIS) return;
      ctx.beginPath();
      ctx.moveTo(originX + ka.nx * scale, originY - ka.ny * scale);
      ctx.lineTo(originX + kb.nx * scale, originY - kb.ny * scale);
      ctx.stroke();
    });
    Object.values(norm).forEach((kp) => {
      if ((kp.visibility ?? 1) < MERGED_VIS) return;
      ctx.beginPath();
      ctx.arc(originX + kp.nx * scale, originY - kp.ny * scale, 2.5, 0, Math.PI * 2);
      ctx.fill();
    });
  });
  ctx.globalAlpha = 1.0;
  if (!anyDrawn) {
    ctx.fillStyle = "rgba(139,147,180,0.4)";
    ctx.font = "11px Inter, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("대기 중…", W / 2, H / 2);
  }
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

  ctx.lineWidth = Math.max(2, fit.width * 0.03);
  ctx.lineCap = "round";
  ctx.strokeStyle = "rgba(0, 255, 198, 0.95)";
  ctx.shadowColor = "rgba(0, 255, 198, 0.8)";
  ctx.shadowBlur = 8;
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
  const radius = Math.max(2, fit.width * 0.025);
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
  if (!prefix || skeletonBusy || latestPlayers.length === 0) return;
  skeletonBusy = true;
  try {
    const poses = await Promise.all(
      latestPlayers.map(async (player, index) => {
        const canvas = document.getElementById(`${prefix}-${index}`);
        const card = document.getElementById(`${prefix}-card-${index}`);
        let pose = null;
        try {
          const response = await fetch(`/api/cameras/${player.camera_id}/pose`, { cache: "no-store" });
          if (response.ok) pose = await response.json();
        } catch {
          pose = null;
        }
        if (canvas) drawSkeletonCard(canvas, pose);
        if (card) card.classList.toggle("ready", Boolean(pose && pose.person_detected));
        return pose;
      }),
    );
    captureRoundSnapshot(prefix);
    // Draw merged (torso-normalised) skeleton overlay during playing phase.
    if (currentPhase === "playing" && el.mergedSkel) {
      drawMergedSkeletons(el.mergedSkel, poses);
    }
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
