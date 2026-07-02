// ===========================================================================
//  DEMO-ONLY camera + skeleton overlay for the /game screen.
//
//  Purpose: while screen-recording a demo, show the 3 live camera feeds with
//  the pose skeleton drawn on top (same look as the operator dashboard `/`)
//  pinned small in the TOP-RIGHT corner of the game page.
//
//  HOW TO ENABLE : open the game page with  ?demo=1   e.g.  /game?demo=1
//  HOW TO DISABLE: just open  /game  (no query) — nothing renders.
//  HOW TO REMOVE : delete the <script ... demo-overlay.js> tag in game.html
//                  (look for the "DEMO OVERLAY" marker) and this file.
//
//  This is intentionally fully self-contained (own styles + DOM, no edits to
//  game.js) so it can be ripped out without touching the real game code.
//
//  NOTE: this polls single-frame JPEG snapshots (NOT the persistent MJPEG
//  /stream endpoint) so it does NOT hold camera connections open and will
//  not exhaust the per-host HTTP connection limit / freeze the camtest page.
// ===========================================================================
(function () {
  "use strict";

  const enabled = /(?:[?&]demo(?:=1)?\b)|(?:#demo\b)/.test(
    window.location.search + window.location.hash
  );
  if (!enabled) return;

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

  function drawSkeleton(canvas, pose) {
    const box = canvas.parentElement;
    const width = box.clientWidth;
    const height = box.clientHeight;
    if (!width || !height) return;
    if (canvas.width !== width) canvas.width = width;
    if (canvas.height !== height) canvas.height = height;

    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, width, height);
    if (!pose || !pose.person_detected || !Array.isArray(pose.keypoints)) return;

    const points = {};
    for (const kp of pose.keypoints) points[kp.name] = kp;
    const visible = (kp) =>
      kp && (kp.visibility == null || kp.visibility >= VISIBILITY_THRESHOLD);

    ctx.lineWidth = Math.max(2, width * 0.008);
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

    const radius = Math.max(2.5, width * 0.011);
    ctx.fillStyle = "#ffffff";
    for (const kp of pose.keypoints) {
      if (!visible(kp)) continue;
      ctx.beginPath();
      ctx.arc(kp.x * width, kp.y * height, radius, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  const style = document.createElement("style");
  style.textContent = `
    #demo-overlay {
      position: fixed; top: 12px; right: 12px; z-index: 99999;
      display: flex; gap: 8px; pointer-events: none;
    }
    #demo-overlay .demo-cam {
      position: relative; width: clamp(120px, 12vw, 180px); aspect-ratio: 3 / 4;
      border-radius: 10px; overflow: hidden; border: 2px solid #00ffaa;
      background: #0d1230; box-shadow: 0 6px 20px rgba(0, 0, 0, 0.55);
    }
    #demo-overlay .demo-cam img,
    #demo-overlay .demo-cam canvas {
      position: absolute; inset: 0; width: 100%; height: 100%;
    }
    #demo-overlay .demo-cam img { object-fit: cover; }
    #demo-overlay .demo-tag {
      position: absolute; top: 4px; left: 6px; z-index: 2;
      font: 800 12px "Inter", sans-serif; color: #00ffaa;
      text-shadow: 0 1px 3px rgba(0, 0, 0, 0.9);
    }
  `;
  document.head.appendChild(style);

  const container = document.createElement("div");
  container.id = "demo-overlay";
  document.body.appendChild(container);

  const canvases = {};
  const images = {};
  let cameraIds = [];

  async function init() {
    try {
      const res = await fetch("/api/cameras", { cache: "no-store" });
      const payload = await res.json();
      cameraIds = (payload.cameras || [])
        .map((c) => c.camera_id)
        .filter(Boolean)
        .slice(0, 3);
    } catch {
      cameraIds = [];
    }
    container.innerHTML = "";
    cameraIds.forEach((id, idx) => {
      const cell = document.createElement("div");
      cell.className = "demo-cam";

      const img = document.createElement("img");
      img.alt = "";

      const canvas = document.createElement("canvas");

      const tag = document.createElement("span");
      tag.className = "demo-tag";
      tag.textContent = `P${idx + 1}`;

      cell.appendChild(img);
      cell.appendChild(canvas);
      cell.appendChild(tag);
      container.appendChild(cell);
      canvases[id] = canvas;
      images[id] = img;
    });
    if (cameraIds.length) tick();
  }

  let busy = false;
  async function tick() {
    if (busy) return;
    busy = true;
    try {
      const stamp = Date.now();
      await Promise.all(
        cameraIds.map(async (id) => {
          // Refresh the still frame via the single-shot snapshot endpoint
          // (cache-busted). This completes each request instead of holding a
          // persistent MJPEG connection open.
          const img = images[id];
          if (img) img.src = `/api/cameras/${id}/snapshot?t=${stamp}`;
          const canvas = canvases[id];
          if (!canvas) return;
          try {
            const r = await fetch(`/api/cameras/${id}/pose`, { cache: "no-store" });
            drawSkeleton(canvas, r.ok ? await r.json() : null);
          } catch {
            drawSkeleton(canvas, null);
          }
        })
      );
    } finally {
      busy = false;
    }
  }

  init();
  setInterval(tick, 120);
})();
