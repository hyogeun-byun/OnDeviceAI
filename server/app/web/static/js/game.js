const GAUGE_CIRCUMFERENCE = 2 * Math.PI * 104;

const screens = {
  idle: document.getElementById("screen-idle"),
  countdown: document.getElementById("screen-countdown"),
  playing: document.getElementById("screen-playing"),
  result: document.getElementById("screen-result"),
  finished: document.getElementById("screen-final"),
};

const el = {
  conn: document.getElementById("conn"),
  roundPill: document.getElementById("round-pill"),
  startBtn: document.getElementById("start-btn"),
  restartBtn: document.getElementById("restart-btn"),
  idlePlayers: document.getElementById("idle-players"),
  cdPrompt: document.getElementById("cd-prompt"),
  cdNumber: document.getElementById("cd-number"),
  playPrompt: document.getElementById("play-prompt"),
  playPlayers: document.getElementById("play-players"),
  playTagline: document.getElementById("play-tagline"),
  gaugeFill: document.getElementById("gauge-fill"),
  gaugeValue: document.getElementById("gauge-value"),
  timerFill: document.getElementById("timer-fill"),
  timerText: document.getElementById("timer-text"),
  resultRound: document.getElementById("result-round"),
  resultPrompt: document.getElementById("result-prompt"),
  resultScore: document.getElementById("result-score"),
  resultComment: document.getElementById("result-comment"),
  finalScore: document.getElementById("final-score"),
  finalTitle: document.getElementById("final-title"),
  finalBreakdown: document.getElementById("final-breakdown"),
};

const playerCount = Number(document.body.dataset.playerCount || "3");
let lastResultRound = 0;

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
const playDots = buildPlayerDots(el.playPlayers);

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
  showScreen(state.phase);

  if (state.phase === "idle") {
    el.roundPill.textContent = "READY";
  } else if (state.phase === "finished") {
    el.roundPill.textContent = "FINAL";
  } else {
    el.roundPill.textContent = `ROUND ${state.round_number} / ${state.total_rounds}`;
  }

  updatePlayerDots(idleDots, state.players);
  updatePlayerDots(playDots, state.players);

  if (state.phase === "countdown") {
    el.cdPrompt.textContent = state.prompt || "";
    const left = state.time_left == null ? 0 : state.time_left;
    el.cdNumber.textContent = String(Math.max(1, Math.ceil(left)));
  }

  if (state.phase === "playing") {
    el.playPrompt.textContent = state.prompt || "";
    setGauge(state.gauge);
    el.playTagline.textContent = taglineFor(state.gauge, state.ready_count);

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
    el.resultComment.textContent = taglineFor(roundScore, 2);
  }

  if (state.phase === "finished") {
    el.finalScore.textContent = String(Math.round(state.total_score || 0));
    el.finalTitle.textContent = state.final_title || "";
    el.finalBreakdown.innerHTML = "";
    (state.round_scores || []).forEach((score, index) => {
      const li = document.createElement("li");
      li.innerHTML = `<span class="fb-round">R${index + 1}</span><span class="fb-score">${Math.round(
        score,
      )}</span>`;
      el.finalBreakdown.appendChild(li);
    });
  }
}

async function startGame() {
  lastResultRound = 0;
  try {
    await fetch("/api/game/start", { method: "POST" });
  } catch {
    /* the next websocket snapshot will reflect the state */
  }
}

el.startBtn.addEventListener("click", startGame);
el.restartBtn.addEventListener("click", startGame);

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
