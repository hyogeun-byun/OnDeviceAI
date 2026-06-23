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

refreshCameraStatus();
setInterval(refreshCameraStatus, 2000);
