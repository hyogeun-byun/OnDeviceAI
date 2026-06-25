async function refreshCameraStatus() {
  const serverStatus = document.querySelector("#server-status");
  const visualizeMetrics = document.body.dataset.visualizeMetrics === "true";

  try {
    const response = await fetch("/api/cameras", { cache: "no-store" });
    const payload = await response.json();

    serverStatus.textContent = "Server Online";
    serverStatus.classList.add("online");

    for (const camera of payload.cameras) {
      const state = document.querySelector(`#${camera.camera_id}-state`);
      if (!state) {
        continue;
      }

      state.textContent = camera.online ? "Online" : "Waiting";
      state.classList.toggle("online", camera.online);

      const poseState = document.querySelector(`#${camera.camera_id}-pose-state`);
      const keypointCount = document.querySelector(`#${camera.camera_id}-keypoint-count`);

      if (poseState) {
        poseState.textContent = camera.person_detected ? "Detected" : "Waiting";
      }

      if (keypointCount) {
        keypointCount.textContent = String(camera.keypoint_count ?? 0);
      }

      if (visualizeMetrics) {
        updateMetrics(camera);
      }
    }
  } catch {
    serverStatus.textContent = "Server Offline";
    serverStatus.classList.remove("online");
  }
}

function updateMetrics(camera) {
  const workerMetrics = camera.worker_metrics || {};
  const serverMetrics = camera.server_metrics || {};
  const cameraId = camera.camera_id;

  setText(`${cameraId}-frame-fps`, formatNumber(workerMetrics.frame_fps, 1));
  setText(`${cameraId}-pose-fps`, formatNumber(workerMetrics.pose_fps, 1));
  setText(`${cameraId}-avg-pose-ms`, `${formatNumber(workerMetrics.avg_pose_ms, 0)} ms`);
  setText(`${cameraId}-avg-upload-ms`, `${formatNumber(workerMetrics.avg_frame_upload_ms, 0)} ms`);
  setText(`${cameraId}-upload-kb-s`, `${formatNumber(workerMetrics.upload_kb_s, 0)} KB/s`);
  setText(`${cameraId}-avg-frame-kb`, `${formatNumber(workerMetrics.avg_frame_kb, 0)} KB`);
  setText(`${cameraId}-server-frame-fps`, formatNumber(serverMetrics.recv_frame_fps, 1));
  setText(
    `${cameraId}-failures`,
    String((workerMetrics.failed_frames ?? 0) + (workerMetrics.failed_poses ?? 0)),
  );

  setBar(`${cameraId}-frame-fps-bar`, workerMetrics.frame_fps, 15);
  setBar(`${cameraId}-pose-fps-bar`, workerMetrics.pose_fps, 5);
}

function setText(id, value) {
  const element = document.getElementById(id);
  if (element) {
    element.textContent = value;
  }
}

function setBar(id, value, maxValue) {
  const element = document.getElementById(id);
  if (!element) {
    return;
  }

  const numberValue = Number(value ?? 0);
  const percent = Math.max(0, Math.min(100, (numberValue / maxValue) * 100));
  element.style.width = `${percent}%`;
}

function formatNumber(value, digits) {
  const numberValue = Number(value ?? 0);
  return numberValue.toFixed(digits);
}

// --- Skeleton overlay ---
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

const VISIBILITY_THRESHOLD = 0.5;

function cameraIds() {
  return Array.from(document.querySelectorAll(".pose-overlay")).map((canvas) =>
    canvas.id.replace(/-overlay$/, ""),
  );
}

function drawSkeleton(canvas, pose) {
  const box = canvas.parentElement;
  const width = box.clientWidth;
  const height = box.clientHeight;
  if (canvas.width !== width) canvas.width = width;
  if (canvas.height !== height) canvas.height = height;

  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, width, height);

  if (!pose || !pose.person_detected || !Array.isArray(pose.keypoints)) {
    return;
  }

  const points = {};
  for (const keypoint of pose.keypoints) {
    points[keypoint.name] = keypoint;
  }

  const visible = (keypoint) =>
    keypoint && (keypoint.visibility == null || keypoint.visibility >= VISIBILITY_THRESHOLD);

  ctx.lineWidth = Math.max(2, width * 0.006);
  ctx.strokeStyle = "rgba(0, 255, 170, 0.9)";
  ctx.lineCap = "round";

  for (const [a, b] of POSE_CONNECTIONS) {
    const pa = points[a];
    const pb = points[b];
    if (!visible(pa) || !visible(pb)) continue;
    ctx.beginPath();
    ctx.moveTo(pa.x * width, pa.y * height);
    ctx.lineTo(pb.x * width, pb.y * height);
    ctx.stroke();
  }

  const radius = Math.max(2.5, width * 0.008);
  ctx.fillStyle = "#ffffff";
  for (const keypoint of pose.keypoints) {
    if (!visible(keypoint)) continue;
    ctx.beginPath();
    ctx.arc(keypoint.x * width, keypoint.y * height, radius, 0, Math.PI * 2);
    ctx.fill();
  }
}

let drawingPoses = false;

async function refreshSkeletons() {
  if (drawingPoses) return;
  drawingPoses = true;
  try {
    await Promise.all(
      cameraIds().map(async (cameraId) => {
        const canvas = document.getElementById(`${cameraId}-overlay`);
        if (!canvas) return;
        try {
          const response = await fetch(`/api/cameras/${cameraId}/pose`, { cache: "no-store" });
          drawSkeleton(canvas, response.ok ? await response.json() : null);
        } catch {
          drawSkeleton(canvas, null);
        }
      }),
    );
  } finally {
    drawingPoses = false;
  }
}

// --- Score-breakdown diagnostics ---
const DIAG_JOINTS = [
  ["left_shoulder", "L sh"],
  ["right_shoulder", "R sh"],
  ["left_elbow", "L elbow"],
  ["right_elbow", "R elbow"],
  ["left_hip", "L hip"],
  ["right_hip", "R hip"],
  ["left_knee", "L knee"],
  ["right_knee", "R knee"],
];

function renderBoardAngles(board) {
  setText(`${board.camera_id}-visible`, `${board.visible_joints}/8`);
  const container = document.getElementById(`${board.camera_id}-angles`);
  if (!container) {
    return;
  }
  const angles = board.angles || {};
  container.innerHTML = DIAG_JOINTS.map(([name, label]) => {
    const has = Object.prototype.hasOwnProperty.call(angles, name);
    const value = has ? `${Math.round(angles[name])}\u00b0` : "\u2014";
    return `<span class="angle-chip${has ? "" : " missing"}">${label}<b>${value}</b></span>`;
  }).join("");
}

function renderPairs(pairs) {
  const element = document.getElementById("diag-pairs");
  if (!element) {
    return;
  }
  if (!pairs || pairs.length === 0) {
    element.innerHTML = `<span class="pair-empty">2명 이상 감지되면 쌍별 유사도가 표시됩니다</span>`;
    return;
  }
  element.innerHTML = pairs
    .map((pair) => {
      const sim = pair.sim == null ? "\u2014" : `${formatNumber(pair.sim, 0)}%`;
      return `<span class="pair-chip">P${pair.a + 1}\u2194P${pair.b + 1}<b>${sim}</b></span>`;
    })
    .join("");
}

async function refreshDiagnostics() {
  let data;
  try {
    const response = await fetch("/api/debug/analysis", { cache: "no-store" });
    if (!response.ok) {
      return;
    }
    data = await response.json();
  } catch {
    return;
  }

  setText("diag-score", formatNumber(data.score, 1));
  setText("diag-similarity", formatNumber(data.similarity, 1));
  setText("diag-activity", `\u00d7${formatNumber(data.activity_factor, 2)}`);
  setText("diag-expressiveness", formatNumber(data.expressiveness, 2));
  setText("diag-ready", String(data.ready_count ?? 0));

  for (const board of data.boards || []) {
    renderBoardAngles(board);
  }
  renderPairs(data.pairs);
}

refreshCameraStatus();
setInterval(refreshCameraStatus, 2000);
refreshSkeletons();
setInterval(refreshSkeletons, 150);
refreshDiagnostics();
setInterval(refreshDiagnostics, 300);
