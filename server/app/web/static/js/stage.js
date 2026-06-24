// Audience "stage" screen: big camera feeds + telepathy gauge + MC coaching.
// Visual only — audio is read out by the participants' /game screen so the room
// hears a single voice. This page just mirrors the server game state.

const el = {
  conn: document.getElementById("conn"),
  roundPill: document.getElementById("round-pill"),
  prompt: document.getElementById("cast-prompt"),
  gaugeFill: document.getElementById("gauge-fill"),
  gaugeValue: document.getElementById("gauge-value"),
  coach: document.getElementById("cast-coach"),
  coachText: document.getElementById("coach-text"),
  timerFill: document.getElementById("timer-fill"),
  timerText: document.getElementById("timer-text"),
  scores: document.getElementById("cast-scores"),
  overlay: document.getElementById("cast-overlay"),
  overlayKicker: document.getElementById("overlay-kicker"),
  overlayMain: document.getElementById("overlay-main"),
  overlaySub: document.getElementById("overlay-sub"),
};

const PHASE_LABEL = {
  idle: "READY",
  intro: "OPENING",
  countdown: "READY",
  playing: "ACTION!",
  result: "RESULT",
  finished: "FINISH",
};

function setGauge(value) {
  const v = Math.max(0, Math.min(100, Number(value) || 0));
  el.gaugeFill.style.width = `${v}%`;
  el.gaugeValue.textContent = Math.round(v);
  let color = "var(--accent)";
  if (v >= 80) color = "#00ffc6";
  else if (v >= 50) color = "#ffd166";
  else color = "#ff6b9d";
  el.gaugeFill.style.background = color;
}

function renderScores(state) {
  const scores = state.round_scores || [];
  const total = state.total_score || 0;
  const cells = scores
    .map((s, i) => `<div class="cast-score-cell"><span>R${i + 1}</span><strong>${s}</strong></div>`)
    .join("");
  const totalCell = `<div class="cast-score-cell is-total"><span>합계</span><strong>${total}</strong></div>`;
  el.scores.innerHTML = scores.length ? cells + totalCell : "";
}

function showOverlay(kicker, main, sub) {
  el.overlayKicker.textContent = kicker || "";
  el.overlayMain.innerHTML = main || "";
  el.overlaySub.textContent = sub || "";
  el.overlay.hidden = false;
}

function hideOverlay() {
  el.overlay.hidden = true;
}

function render(state) {
  el.roundPill.textContent = PHASE_LABEL[state.phase] || "READY";

  // Prompt banner
  if (state.phase === "idle") el.prompt.textContent = "곧 시작합니다";
  else if (state.phase === "intro") el.prompt.textContent = "민수의 오프닝 🎤";
  else el.prompt.textContent = state.prompt || "";

  // Gauge
  setGauge(state.phase === "playing" || state.phase === "result" ? state.gauge : 0);

  // Coach line
  if (state.phase === "playing" && state.coach) {
    el.coach.classList.add("is-live");
    el.coachText.textContent = state.coach;
  } else {
    el.coach.classList.remove("is-live");
    if (state.phase === "result") el.coachText.textContent = state.mc_comment || "결과 공개!";
    else if (state.phase === "intro") el.coachText.textContent = "잠시 후 시작해요!";
    else if (state.phase === "finished") el.coachText.textContent = "오늘의 텔레파시 최강자는?";
    else el.coachText.textContent = "다 같이 카메라 앞에 서주세요!";
  }

  // Timer
  const duration = state.phase_duration || 1;
  const left = state.time_left == null ? 0 : state.time_left;
  if (state.phase === "countdown" || state.phase === "playing") {
    el.timerFill.style.width = `${Math.max(0, Math.min(100, (left / duration) * 100))}%`;
    el.timerText.textContent = left.toFixed(1);
  } else {
    el.timerFill.style.width = "0%";
    el.timerText.textContent = "0.0";
  }

  renderScores(state);

  // Big overlays
  if (state.phase === "countdown") {
    const n = Math.max(1, Math.ceil(left));
    showOverlay("다 같이!", String(n), state.prompt || "");
  } else if (state.phase === "result") {
    const scores = state.round_scores || [];
    const last = scores.length ? scores[scores.length - 1] : 0;
    showOverlay(`ROUND ${scores.length}`, `${last}<small>점</small>`, state.mc_comment || "");
  } else if (state.phase === "finished") {
    showOverlay("FINAL", `${state.total_score || 0}<small>점</small>`, "수고하셨습니다!");
  } else {
    hideOverlay();
  }
}

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
