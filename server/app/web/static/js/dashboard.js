async function refreshCameraStatus() {
  const serverStatus = document.querySelector("#server-status");

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
    }
  } catch {
    serverStatus.textContent = "Server Offline";
    serverStatus.classList.remove("online");
  }
}

refreshCameraStatus();
setInterval(refreshCameraStatus, 2000);
