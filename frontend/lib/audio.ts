export type RecState = "idle" | "recording" | "paused";

/** Minimal MediaRecorder wrapper producing a single audio Blob. */
export class Recorder {
  private mr: MediaRecorder | null = null;
  private chunks: Blob[] = [];
  private stream: MediaStream | null = null;
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
        this.state = "idle";
        resolve(new Blob(this.chunks, { type: this.mr?.mimeType || "audio/webm" }));
      };
      this.mr.stop();
    });
  }
}
