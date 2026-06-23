const latestPoses = new Map();
let measurementActive = false;

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

      await drawPoseOverlay(camera);

      if (visualizeMetrics) {
        updateMetrics(camera);
      }
    }
  } catch {
    serverStatus.textContent = "Server Offline";
    serverStatus.classList.remove("online");
  }
}

const poseConnections = [
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
  ["nose", "left_eye"],
  ["nose", "right_eye"],
  ["left_eye", "left_ear"],
  ["right_eye", "right_ear"],
];

async function drawPoseOverlay(camera) {
  const canvas = document.getElementById(`${camera.camera_id}-pose-overlay`);
  const image = document.getElementById(`${camera.camera_id}-stream-image`);
  if (!canvas || !image) {
    return;
  }

  const context = canvas.getContext("2d");
  if (!context) {
    return;
  }

  if (measurementActive) {
    clearCanvas(canvas);
    return;
  }

  const pose = await getLatestPose(camera);
  drawPoseOnCanvas(canvas, image, pose);
}

function drawPoseOnCanvas(canvas, image, pose) {
  const context = canvas.getContext("2d");
  if (!context) {
    return;
  }

  const rect = canvas.getBoundingClientRect();
  const pixelRatio = window.devicePixelRatio || 1;
  const canvasWidth = Math.max(1, Math.round(rect.width * pixelRatio));
  const canvasHeight = Math.max(1, Math.round(rect.height * pixelRatio));

  if (canvas.width !== canvasWidth || canvas.height !== canvasHeight) {
    canvas.width = canvasWidth;
    canvas.height = canvasHeight;
  }

  context.clearRect(0, 0, canvas.width, canvas.height);

  const keypoints = pose?.keypoints || [];
  if (keypoints.length === 0) {
    return;
  }

  const imageRect = getRenderedImageRect(image, rect.width, rect.height);
  const keypointsByName = new Map(keypoints.map((keypoint) => [keypoint.name, keypoint]));

  context.save();
  context.scale(pixelRatio, pixelRatio);
  context.lineWidth = 3;
  context.lineCap = "round";

  for (const [fromName, toName] of poseConnections) {
    const from = keypointsByName.get(fromName);
    const to = keypointsByName.get(toName);
    if (!isVisible(from) || !isVisible(to)) {
      continue;
    }

    context.strokeStyle = "rgba(127, 209, 174, 0.9)";
    context.beginPath();
    context.moveTo(imageRect.x + from.x * imageRect.width, imageRect.y + from.y * imageRect.height);
    context.lineTo(imageRect.x + to.x * imageRect.width, imageRect.y + to.y * imageRect.height);
    context.stroke();
  }

  for (const keypoint of keypoints) {
    if (!isVisible(keypoint)) {
      continue;
    }

    const x = imageRect.x + keypoint.x * imageRect.width;
    const y = imageRect.y + keypoint.y * imageRect.height;
    context.fillStyle = "rgba(245, 197, 92, 0.95)";
    context.strokeStyle = "rgba(11, 13, 16, 0.85)";
    context.lineWidth = 2;
    context.beginPath();
    context.arc(x, y, 4, 0, Math.PI * 2);
    context.fill();
    context.stroke();
  }

  context.restore();
}

function clearCanvas(canvas) {
  const context = canvas.getContext("2d");
  if (!context) {
    return;
  }

  context.clearRect(0, 0, canvas.width, canvas.height);
}

function getRenderedImageRect(image, containerWidth, containerHeight) {
  const naturalWidth = image.naturalWidth || 4;
  const naturalHeight = image.naturalHeight || 3;
  const imageRatio = naturalWidth / naturalHeight;
  const containerRatio = containerWidth / containerHeight;

  if (imageRatio > containerRatio) {
    const width = containerWidth;
    const height = width / imageRatio;
    return { x: 0, y: (containerHeight - height) / 2, width, height };
  }

  const height = containerHeight;
  const width = height * imageRatio;
  return { x: (containerWidth - width) / 2, y: 0, width, height };
}

function isVisible(keypoint) {
  return keypoint && (keypoint.visibility ?? 1) >= 0.1;
}

async function getLatestPose(camera) {
  if (camera.latest_pose?.keypoints?.length > 0) {
    latestPoses.set(camera.camera_id, camera.latest_pose);
    return camera.latest_pose;
  }

  if ((camera.keypoint_count ?? 0) <= 0) {
    return latestPoses.get(camera.camera_id);
  }

  try {
    const response = await fetch(`/api/cameras/${camera.camera_id}/pose`, { cache: "no-store" });
    if (!response.ok) {
      return latestPoses.get(camera.camera_id);
    }

    const pose = await response.json();
    latestPoses.set(camera.camera_id, pose);
    return pose;
  } catch {
    return latestPoses.get(camera.camera_id);
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

async function startMeasurement() {
  const button = document.getElementById("measure-button");
  const overlay = document.getElementById("countdown-overlay");
  const countdownNumber = document.getElementById("countdown-number");
  if (!button || !overlay || !countdownNumber) {
    return;
  }

  measurementActive = true;
  button.disabled = true;
  overlay.hidden = false;

  for (const value of [3, 2, 1]) {
    countdownNumber.textContent = String(value);
    await sleep(1000);
  }

  countdownNumber.textContent = "0";
  await sleep(250);
  overlay.hidden = true;

  try {
    const response = await fetch("/api/cameras/capture", {
      method: "POST",
      cache: "no-store",
    });
    if (!response.ok) {
      throw new Error("capture failed");
    }

    const result = await response.json();
    renderCaptureResult(result);
  } finally {
    measurementActive = false;
    button.disabled = false;
  }
}

function renderCaptureResult(result) {
  const results = document.getElementById("measurement-results");
  const grid = document.getElementById("capture-grid");
  const score = document.getElementById("similarity-score");
  if (!results || !grid || !score) {
    return;
  }

  results.hidden = false;
  grid.innerHTML = "";

  const similarityScore = Number(result.similarity?.score ?? 0);
  const pairCount = Number(result.similarity?.pair_count ?? 0);
  score.textContent = pairCount > 0 ? `Similarity ${similarityScore.toFixed(1)}%` : "Similarity -";

  for (const capture of result.captures || []) {
    const card = document.createElement("article");
    card.className = "capture-card";

    const header = document.createElement("div");
    header.className = "capture-card-header";
    header.innerHTML = `<span>${capture.camera_id}</span><span>${capture.keypoint_count ?? 0} keypoints</span>`;

    const stage = document.createElement("div");
    stage.className = "capture-stage";

    const image = document.createElement("img");
    image.src = `${capture.image_url}?v=${Date.now()}`;
    image.alt = `${capture.camera_id} captured pose`;

    const canvas = document.createElement("canvas");
    stage.append(image, canvas);
    card.append(header, stage);
    grid.append(card);

    image.addEventListener("load", () => {
      drawPoseOnCanvas(canvas, image, capture.pose);
    });
  }
}

function sleep(milliseconds) {
  return new Promise((resolve) => {
    setTimeout(resolve, milliseconds);
  });
}

document.getElementById("measure-button")?.addEventListener("click", () => {
  startMeasurement();
});

refreshCameraStatus();
setInterval(refreshCameraStatus, 2000);
