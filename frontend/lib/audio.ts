export type RecState = "idle" | "recording" | "paused";

export const TARGET_RATE = 16000;

/** Encode mono float samples as 16-bit PCM WAV. Pure — unit-tested. */
export function encodeWavPCM(samples: Float32Array, sampleRate = TARGET_RATE): Blob {
  const n = samples.length;
  const buf = new ArrayBuffer(44 + n * 2);
  const v = new DataView(buf);
  const ascii = (o: number, s: string) => {
    for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i));
  };
  ascii(0, "RIFF");
  v.setUint32(4, 36 + n * 2, true);
  ascii(8, "WAVE");
  ascii(12, "fmt ");
  v.setUint32(16, 16, true);
  v.setUint16(20, 1, true);
  v.setUint16(22, 1, true);
  v.setUint32(24, sampleRate, true);
  v.setUint32(28, sampleRate * 2, true);
  v.setUint16(32, 2, true);
  v.setUint16(34, 16, true);
  ascii(36, "data");
  v.setUint32(40, n * 2, true);
  for (let i = 0; i < n; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    v.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return new Blob([buf], { type: "audio/wav" });
}

/**
 * Convert a browser recording (webm/opus, mp4/aac — codecs the server
 * cannot decode) to 16 kHz mono WAV in-browser. The server only ever
 * receives WAV, so its decoder path stays exact.
 */
export async function toWav16kBlob(blob: Blob): Promise<Blob> {
  const raw = await blob.arrayBuffer();
  const AC = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
  const ctx = new AC();
  let decoded;
  try {
    decoded = await ctx.decodeAudioData(raw.slice(0));
  } finally {
    await ctx.close().catch(() => {});
  }
  const src = decoded.getChannelData(0);
  const channels = decoded.numberOfChannels;
  let mono: Float32Array;
  if (channels > 1) {
    mono = new Float32Array(src.length);
    for (let c = 0; c < channels; c++) {
      const d = decoded.getChannelData(c);
      for (let i = 0; i < src.length; i++) mono[i] += d[i] / channels;
    }
  } else {
    mono = src;
  }
  if (decoded.sampleRate === TARGET_RATE) return encodeWavPCM(mono);
  const off = new OfflineAudioContext(1, Math.ceil(mono.length * (TARGET_RATE / decoded.sampleRate)), TARGET_RATE);
  const srcNode = off.createBufferSource();
  const tmp = off.createBuffer(1, mono.length, decoded.sampleRate);
  tmp.getChannelData(0).set(mono);
  srcNode.buffer = tmp;
  srcNode.connect(off.destination);
  srcNode.start();
  const rendered = await off.startRendering();
  return encodeWavPCM(rendered.getChannelData(0));
}

export type MeterHandle = { analyser: AnalyserNode; dispose: () => void };

/** Minimal MediaRecorder wrapper producing a single audio Blob. */
export class Recorder {
  private mr: MediaRecorder | null = null;
  private chunks: Blob[] = [];
  private stream: MediaStream | null = null;
  private meterCtx: AudioContext | null = null;
  state: RecState = "idle";

  async start(): Promise<void> {
    this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const mime = MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "";
    this.mr = mime ? new MediaRecorder(this.stream, { mimeType: mime }) : new MediaRecorder(this.stream);
    this.chunks = [];
    this.mr.ondataavailable = (e) => {
      if (e.data.size > 0) this.chunks.push(e.data);
    };
    this.mr.start(250);
    this.state = "recording";
  }

  pause() {
    if (this.mr?.state === "recording") {
      this.mr.pause();
      this.state = "paused";
    }
  }

  resume() {
    if (this.mr?.state === "paused") {
      this.mr.resume();
      this.state = "recording";
    }
  }

  stop(): Promise<Blob> {
    return new Promise((resolve, reject) => {
      if (!this.mr) return reject(new Error("Not recording"));
      this.mr.onstop = () => {
        this.stream?.getTracks().forEach((t) => t.stop());
        this.disposeMeter();
        this.state = "idle";
        resolve(new Blob(this.chunks, { type: this.mr?.mimeType || "audio/webm" }));
      };
      this.mr.stop();
    });
  }

  /**
   * Live level meter for the active mic stream (powers the recording
   * waveform). Returns null when idle. Dispose on stop/unmount; `stop()`
   * also disposes automatically. Never affects the recorded Blob.
   */
  attachMeter(): MeterHandle | null {
    if (!this.stream || typeof window === "undefined") return null;
    try {
      const AC = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      this.disposeMeter();
      const ctx = new AC();
      const src = ctx.createMediaStreamSource(this.stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      analyser.smoothingTimeConstant = 0.75;
      src.connect(analyser);
      this.meterCtx = ctx;
      return { analyser, dispose: () => this.disposeMeter() };
    } catch {
      return null;
    }
  }

  private disposeMeter() {
    if (this.meterCtx) {
      this.meterCtx.close().catch(() => {});
      this.meterCtx = null;
    }
  }
}
