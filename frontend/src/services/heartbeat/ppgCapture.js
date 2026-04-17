/**
 * PPG (photoplethysmography) capture for the rear camera.
 *
 * Opens the camera with ``facingMode: 'environment'`` and — when
 * supported — enables the torch so the user's finger provides a
 * clean red-dominant signal. Each frame we sample the mean red
 * channel over a small ROI in the centre of the frame and push it
 * onto a Float32Array.
 *
 * iOS Safari does NOT expose the ``torch`` constraint, so we fall
 * back to ambient-light capture and let the caller tell the user to
 * pick a brighter environment.
 */

export async function openPpgStream({ facingMode = 'environment' } = {}) {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: false,
    video: {
      facingMode,
      width: { ideal: 320 },
      height: { ideal: 240 },
      frameRate: { ideal: 30 },
    },
  });
  const track = stream.getVideoTracks()[0];
  let torchOn = false;
  try {
    const capabilities = track.getCapabilities ? track.getCapabilities() : {};
    if (capabilities.torch) {
      await track.applyConstraints({ advanced: [{ torch: true }] });
      torchOn = true;
    }
  } catch {
    torchOn = false;
  }
  return { stream, track, torchOn };
}

export function closePpgStream({ stream, track } = {}) {
  try { if (track && track.applyConstraints) track.applyConstraints({ advanced: [{ torch: false }] }); } catch { /* noop */ }
  if (stream) {
    stream.getTracks().forEach((t) => { try { t.stop(); } catch { /* noop */ } });
  }
}

/**
 * Capture ``seconds`` of centre-ROI red-channel means. Resolves to
 * ``{samples: Float32Array, frameRate: number}``.
 */
export async function capturePpg({ seconds = 30, onFrame } = {}) {
  const { stream, track, torchOn } = await openPpgStream();
  const video = document.createElement('video');
  video.srcObject = stream;
  video.playsInline = true;
  await video.play();

  const canvas = document.createElement('canvas');
  const roi = 80;
  canvas.width = roi;
  canvas.height = roi;
  const ctx = canvas.getContext('2d', { willReadFrequently: true });

  const samples = [];
  const timestamps = [];
  const start = performance.now();
  let running = true;

  await new Promise((resolve) => {
    const stopAt = start + seconds * 1000;
    const tick = () => {
      if (!running) return;
      const now = performance.now();
      if (now >= stopAt) {
        running = false;
        resolve();
        return;
      }
      try {
        const vw = video.videoWidth || roi;
        const vh = video.videoHeight || roi;
        const sx = Math.max(0, Math.floor((vw - roi) / 2));
        const sy = Math.max(0, Math.floor((vh - roi) / 2));
        ctx.drawImage(video, sx, sy, roi, roi, 0, 0, roi, roi);
        const img = ctx.getImageData(0, 0, roi, roi).data;
        let redSum = 0;
        let n = 0;
        for (let i = 0; i < img.length; i += 4) {
          redSum += img[i];
          n += 1;
        }
        const meanRed = redSum / Math.max(n, 1);
        samples.push(meanRed);
        timestamps.push(now);
        onFrame?.(meanRed, now - start);
      } catch (err) {
        /* drop the frame on canvas hiccups rather than aborting */
      }
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });

  closePpgStream({ stream, track });

  const durationS = (timestamps[timestamps.length - 1] - timestamps[0]) / 1000 || seconds;
  const frameRate = samples.length / Math.max(durationS, 0.5);
  return {
    samples: Float32Array.from(samples),
    timestamps,
    frameRate,
    torchOn,
    durationS,
  };
}

export default { openPpgStream, closePpgStream, capturePpg };
