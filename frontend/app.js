const profiles = {
  reliable: { f0: 10000, f1: 12000, sync: 11000, tolerance: 700, bitDuration: 0.1, repeat: 1 },
  reliable_slow: { f0: 10000, f1: 12000, sync: 11000, tolerance: 700, bitDuration: 0.15, repeat: 3 },
  near_ultra: { f0: 17000, f1: 18000, sync: 16500, tolerance: 700, bitDuration: 0.1, repeat: 1 },
  proposal: { f0: 18000, f1: 19000, sync: 17500, tolerance: 700, bitDuration: 0.1, repeat: 1 },
};

const $ = (id) => document.getElementById(id);
let audioContext;
let sourceNode;
let micStream;
let processor;
let analyser;
let spectrogramRunning = false;
let receiveState = resetReceiveState();

function getAudioContext() {
  audioContext ||= new AudioContext();
  return audioContext;
}

function currentConfig() {
  return {
    f0: Number($("freqZero").value),
    f1: Number($("freqOne").value),
    sync: Number($("syncFreq").value),
    tolerance: Number($("tolerance").value),
    bitDuration: Number($("bitDuration").value),
    repeat: Math.max(1, Number($("repeatBits").value)),
  };
}

function applyProfile(name) {
  if (name === "custom") return;
  const p = profiles[name];
  $("freqZero").value = p.f0;
  $("freqOne").value = p.f1;
  $("syncFreq").value = p.sync;
  $("tolerance").value = p.tolerance;
  $("bitDuration").value = p.bitDuration;
  $("repeatBits").value = p.repeat;
  updateSummary();
}

function textToBits(text) {
  return Array.from(new TextEncoder().encode(text))
    .map((byte) => byte.toString(2).padStart(8, "0"))
    .join("");
}

function bitsToText(bits) {
  const bytes = [];
  const usable = bits.length - (bits.length % 8);
  for (let i = 0; i < usable; i += 8) bytes.push(parseInt(bits.slice(i, i + 8), 2));
  return new TextDecoder("utf-8", { fatal: false }).decode(new Uint8Array(bytes));
}

function majorityVote(bits, repeat) {
  if (repeat <= 1) return bits.join("");
  const out = [];
  for (let i = 0; i + repeat <= bits.length; i += repeat) {
    const group = bits.slice(i, i + repeat);
    out.push(group.filter((b) => b === "1").length > repeat / 2 ? "1" : "0");
  }
  return out.join("");
}

function tone(buffer, offset, freq, samples, sampleRate) {
  const fadeSamples = Math.min(Math.floor(sampleRate * 0.005), Math.floor(samples / 2));
  for (let i = 0; i < samples; i += 1) {
    let amp = 0.35;
    if (i < fadeSamples) amp *= i / fadeSamples;
    if (i >= samples - fadeSamples) amp *= (samples - i) / fadeSamples;
    buffer[offset + i] = amp * Math.sin((2 * Math.PI * freq * i) / sampleRate);
  }
}

function buildWave(message, config, sampleRate) {
  const bits = textToBits(message);
  const repeated = bits.split("").flatMap((bit) => Array(config.repeat).fill(bit));
  const freqs = [
    ...Array(8).fill(config.sync),
    ...repeated.map((bit) => (bit === "1" ? config.f1 : config.f0)),
    ...Array(8).fill(config.sync),
  ];
  const samples = Math.floor(sampleRate * config.bitDuration);
  const data = new Float32Array(samples * freqs.length);
  freqs.forEach((freq, index) => tone(data, index * samples, freq, samples, sampleRate));
  return { data, bits: bits.length, seconds: data.length / sampleRate };
}

function updateSummary() {
  const cfg = currentConfig();
  const chars = $("message").value.length;
  const bits = textToBits($("message").value).length;
  const seconds = (16 + bits * cfg.repeat) * cfg.bitDuration;
  $("txSummary").textContent = `${chars} chars / ${bits} bits. Estimated transmission: ${seconds.toFixed(1)}s.`;
}

async function playTransmission() {
  const ctx = getAudioContext();
  await ctx.resume();
  const cfg = currentConfig();
  const { data, seconds } = buildWave($("message").value, cfg, ctx.sampleRate);
  const buffer = ctx.createBuffer(1, data.length, ctx.sampleRate);
  buffer.copyToChannel(data, 0);
  sourceNode?.stop();
  sourceNode = ctx.createBufferSource();
  sourceNode.buffer = buffer;
  sourceNode.connect(ctx.destination);
  sourceNode.onended = () => setStatus("Transmission complete");
  setStatus(`Transmitting ${seconds.toFixed(1)}s`);
  sourceNode.start();
}

function stopTransmission() {
  sourceNode?.stop();
  setStatus("Audio idle");
}

function goertzelPower(samples, sampleRate, freq) {
  const omega = (2 * Math.PI * freq) / sampleRate;
  const coeff = 2 * Math.cos(omega);
  let q0 = 0;
  let q1 = 0;
  let q2 = 0;
  for (const sample of samples) {
    q0 = coeff * q1 - q2 + sample;
    q2 = q1;
    q1 = q0;
  }
  return q1 * q1 + q2 * q2 - coeff * q1 * q2;
}

function classify(samples, sampleRate, cfg, floor = null) {
  const powers = {
    S: goertzelPower(samples, sampleRate, cfg.sync),
    0: goertzelPower(samples, sampleRate, cfg.f0),
    1: goertzelPower(samples, sampleRate, cfg.f1),
  };
  const ordered = Object.entries(powers).sort((a, b) => b[1] - a[1]);
  const [symbol, power] = ordered[0];
  const second = ordered[1][1];
  const floorPower = floor ? floor[symbol] || 0 : 0;
  const accepted = power > Math.max(1e-3, floorPower * 8) && power > second * 1.18;
  return { symbol: accepted ? symbol : null, powers };
}

function resetReceiveState() {
  return {
    receiving: false,
    syncCount: 0,
    endSync: 0,
    bits: [],
    calibrated: false,
    calibrationFrames: 0,
    floor: { S: 0, 0: 0, 1: 0 },
  };
}

function processSymbol(symbol) {
  if (symbol === "S") {
    if (receiveState.receiving) {
      receiveState.endSync += 1;
      if (receiveState.endSync >= 8) return "done";
    } else {
      receiveState.syncCount += 1;
      if (receiveState.syncCount >= 8) receiveState.receiving = true;
    }
    return "sync";
  }
  if (!receiveState.receiving) {
    receiveState.syncCount = 0;
    return "waiting";
  }
  receiveState.endSync = 0;
  if (symbol === "0" || symbol === "1") receiveState.bits.push(symbol);
  return "data";
}

async function startListening() {
  const ctx = getAudioContext();
  await ctx.resume();
  micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const input = ctx.createMediaStreamSource(micStream);
  analyser = ctx.createAnalyser();
  analyser.fftSize = 2048;
  processor = ctx.createScriptProcessor(4096, 1, 1);
  input.connect(analyser);
  input.connect(processor);
  processor.connect(ctx.destination);

  receiveState = resetReceiveState();
  let pending = [];
  processor.onaudioprocess = (event) => {
    const cfg = currentConfig();
    const samplesPerSymbol = Math.floor(ctx.sampleRate * cfg.bitDuration);
    pending.push(...event.inputBuffer.getChannelData(0));
    while (pending.length >= samplesPerSymbol) {
      const chunk = pending.slice(0, samplesPerSymbol);
      pending = pending.slice(samplesPerSymbol);
      if (!receiveState.calibrated) {
        const calibration = classify(chunk, ctx.sampleRate, cfg);
        receiveState.floor.S += calibration.powers.S;
        receiveState.floor[0] += calibration.powers[0];
        receiveState.floor[1] += calibration.powers[1];
        receiveState.calibrationFrames += 1;
        updateMeters(calibration.powers);
        $("rxState").textContent = "calibrating";
        if (receiveState.calibrationFrames >= 8) {
          receiveState.floor.S /= receiveState.calibrationFrames;
          receiveState.floor[0] /= receiveState.calibrationFrames;
          receiveState.floor[1] /= receiveState.calibrationFrames;
          receiveState.calibrated = true;
          $("rxState").textContent = "waiting";
        }
        continue;
      }

      const result = classify(chunk, ctx.sampleRate, cfg, receiveState.floor);
      updateMeters(result.powers);
      const status = processSymbol(result.symbol);
      $("lastSymbol").textContent = result.symbol || "-";
      $("bitCount").textContent = receiveState.bits.length;
      $("rxState").textContent = receiveState.receiving ? "receiving" : "waiting";
      const voted = majorityVote(receiveState.bits, cfg.repeat);
      $("decoded").value = bitsToText(voted);
      if (status === "done") stopListening();
    }
  };
  spectrogramRunning = true;
  drawSpectrogram();
  setStatus("Listening");
}

function stopListening() {
  processor?.disconnect();
  micStream?.getTracks().forEach((track) => track.stop());
  processor = null;
  micStream = null;
  spectrogramRunning = false;
  setStatus("Audio idle");
}

function updateMeters(powers) {
  const max = Math.max(1e-9, powers.S, powers[0], powers[1]);
  $("syncMeter").value = powers.S / max;
  $("zeroMeter").value = powers[0] / max;
  $("oneMeter").value = powers[1] / max;
}

function drawSpectrogram() {
  const canvas = $("spectrogram");
  const g = canvas.getContext("2d");
  const data = new Uint8Array(analyser?.frequencyBinCount || 0);
  const step = () => {
    if (!spectrogramRunning || !analyser) return;
    analyser.getByteFrequencyData(data);
    const cfg = currentConfig();
    const nyquist = getAudioContext().sampleRate / 2;
    const low = Math.max(0, Math.min(cfg.f0, cfg.f1, cfg.sync) - 1500);
    const high = Math.min(nyquist, Math.max(cfg.f0, cfg.f1, cfg.sync) + 1500);
    const start = Math.floor((low / nyquist) * data.length);
    const end = Math.max(start + 1, Math.floor((high / nyquist) * data.length));

    const old = g.getImageData(1, 0, canvas.width - 1, canvas.height);
    g.putImageData(old, 0, 0);
    for (let y = 0; y < canvas.height; y += 1) {
      const index = start + Math.floor(((canvas.height - y) / canvas.height) * (end - start));
      const v = data[index] || 0;
      g.fillStyle = `rgb(${Math.min(255, v * 1.4)}, ${Math.min(255, v * 0.55)}, ${Math.min(255, 50 + v * 0.9)})`;
      g.fillRect(canvas.width - 1, y, 1, 1);
    }
    requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

function clearDecoded() {
  receiveState = resetReceiveState();
  $("decoded").value = "";
  $("bitCount").textContent = "0";
  $("lastSymbol").textContent = "-";
  $("rxState").textContent = "waiting";
}

function setStatus(text) {
  $("audioStatus").textContent = text;
}

document.querySelectorAll(".tab").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((tab) => tab.classList.remove("active"));
    document.querySelectorAll(".tab-pane").forEach((pane) => pane.classList.remove("active"));
    button.classList.add("active");
    $(button.dataset.tab).classList.add("active");
  });
});

$("profile").addEventListener("change", (event) => applyProfile(event.target.value));
["freqZero", "freqOne", "syncFreq", "tolerance", "bitDuration", "repeatBits", "message"].forEach((id) => {
  $(id).addEventListener("input", updateSummary);
});
$("playBtn").addEventListener("click", playTransmission);
$("stopToneBtn").addEventListener("click", stopTransmission);
$("listenBtn").addEventListener("click", startListening);
$("stopListenBtn").addEventListener("click", stopListening);
$("clearBtn").addEventListener("click", clearDecoded);
$("fileInput").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  $("message").value = await file.text();
  updateSummary();
});

applyProfile("reliable_slow");
