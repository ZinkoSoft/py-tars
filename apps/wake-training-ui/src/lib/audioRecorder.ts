export interface AudioRecording {
  blob: Blob;
  url: string;
  sampleRate: number;
  duration: number;
}

export interface AudioRecorderOptions {
  sampleRate?: number;
  onLevel?: (level: number) => void;
}

const DEFAULT_SAMPLE_RATE = 16_000;

function assertMicrophoneSupport(): void {
  if (typeof navigator === "undefined") {
    throw new Error("Microphone capture is only available in a browser context.");
  }

  const mediaDevices = navigator.mediaDevices;
  if (!mediaDevices || typeof mediaDevices.getUserMedia !== "function") {
    if (typeof window !== "undefined" && window.isSecureContext === false) {
      throw new Error(
        "Browser blocked microphone access because the page is not served over HTTPS. Reopen the console with HTTPS (or localhost) and allow microphone permissions.",
      );
    }
    throw new Error(
      "This browser does not expose navigator.mediaDevices.getUserMedia. Update to a modern browser and ensure microphone permissions are allowed.",
    );
  }
}

export class AudioRecorder {
  private mediaStream: MediaStream | null = null;
  private mediaRecorder: MediaRecorder | null = null;
  private chunks: Blob[] = [];
  private analyser: AnalyserNode | null = null;
  private animationFrame: number | null = null;
  private audioContext: AudioContext | null = null;
  private readonly sampleRate: number;
  private readonly onLevel?: (level: number) => void;

  constructor(options: AudioRecorderOptions = {}) {
    this.sampleRate = options.sampleRate ?? DEFAULT_SAMPLE_RATE;
    this.onLevel = options.onLevel;
  }

  async init(): Promise<void> {
    if (this.mediaStream) {
      return;
    }
    assertMicrophoneSupport();
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    this.mediaStream = stream;
    if (this.onLevel) {
      await this.setupAnalyser(stream);
    }
  }

  async start(): Promise<void> {
    if (!this.mediaStream) {
      await this.init();
    }
    if (!this.mediaStream) {
      throw new Error("Unable to acquire audio stream");
    }
    this.chunks = [];
    const mimeTypes = [
      "audio/webm;codecs=opus",
      "audio/webm",
      "audio/ogg;codecs=opus",
    ];
    const mimeType = mimeTypes.find((type) => MediaRecorder.isTypeSupported(type));
    this.mediaRecorder = new MediaRecorder(this.mediaStream, mimeType ? { mimeType } : undefined);
    this.mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        this.chunks.push(event.data);
      }
    };
    this.mediaRecorder.start();
    this.startLevelMonitor();
  }

  async stop(): Promise<AudioRecording> {
    const mediaRecorder = this.mediaRecorder;
    if (!mediaRecorder) {
      throw new Error("Recorder has not been started");
    }

    const stopped = new Promise<Blob>((resolve) => {
      mediaRecorder.onstop = () => {
        const blob = new Blob(this.chunks, { type: mediaRecorder.mimeType || "audio/webm" });
        resolve(blob);
      };
    });

    mediaRecorder.stop();
    this.stopLevelMonitor();
    const rawBlob = await stopped;
    const wavBlob = await convertToWav(rawBlob, this.sampleRate);
    const audioContext = this.audioContext ?? new AudioContext();
    const duration = await getDuration(wavBlob, audioContext);
    const url = URL.createObjectURL(wavBlob);
    return {
      blob: wavBlob,
      url,
      sampleRate: this.sampleRate,
      duration,
    };
  }

  cancel(): void {
    if (this.mediaRecorder && this.mediaRecorder.state !== "inactive") {
      this.mediaRecorder.stop();
    }
    this.stopLevelMonitor();
    this.chunks = [];
  }

  dispose(): void {
    this.cancel();
    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach((track) => track.stop());
      this.mediaStream = null;
    }
    if (this.audioContext) {
      this.audioContext.close().catch(() => undefined);
      this.audioContext = null;
    }
    this.analyser = null;
  }

  private async setupAnalyser(stream: MediaStream): Promise<void> {
    if (this.audioContext) {
      return;
    }
    const audioContext = new AudioContext();
    const source = audioContext.createMediaStreamSource(stream);
    const analyser = audioContext.createAnalyser();
    analyser.fftSize = 256;
    source.connect(analyser);
    this.audioContext = audioContext;
    this.analyser = analyser;
  }

  private startLevelMonitor(): void {
    if (!this.onLevel || !this.analyser) {
      return;
    }
    const bufferLength = this.analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);
    const tick = () => {
      this.analyser!.getByteTimeDomainData(dataArray);
      let sum = 0;
      for (let i = 0; i < bufferLength; i += 1) {
        const value = dataArray[i] - 128;
        sum += value * value;
      }
      const rms = Math.sqrt(sum / bufferLength) / 128;
      this.onLevel!(rms);
      this.animationFrame = requestAnimationFrame(tick);
    };
    tick();
  }

  private stopLevelMonitor(): void {
    if (this.animationFrame) {
      cancelAnimationFrame(this.animationFrame);
      this.animationFrame = null;
    }
    if (this.onLevel) {
      this.onLevel(0);
    }
  }
}

async function convertToWav(blob: Blob, targetSampleRate: number): Promise<Blob> {
  const arrayBuffer = await blob.arrayBuffer();
  const audioContext = new AudioContext();
  const decodedBuffer = await audioContext.decodeAudioData(arrayBuffer.slice(0));
  const offlineContext = new OfflineAudioContext(
    decodedBuffer.numberOfChannels,
    Math.ceil(decodedBuffer.duration * targetSampleRate),
    targetSampleRate,
  );
  const bufferSource = offlineContext.createBufferSource();
  bufferSource.buffer = decodedBuffer;
  bufferSource.connect(offlineContext.destination);
  bufferSource.start(0);
  const renderedBuffer = await offlineContext.startRendering();
  audioContext.close().catch(() => undefined);
  return bufferToWav(renderedBuffer);
}

async function getDuration(blob: Blob, audioContext: AudioContext): Promise<number> {
  const buffer = await blob.arrayBuffer();
  const decoded = await audioContext.decodeAudioData(buffer.slice(0));
  return decoded.duration;
}

function bufferToWav(buffer: AudioBuffer): Blob {
  const numOfChan = buffer.numberOfChannels;
  const length = buffer.length * numOfChan * 2 + 44;
  const arrayBuffer = new ArrayBuffer(length);
  const view = new DataView(arrayBuffer);

  writeString(view, 0, "RIFF");
  view.setUint32(4, 36 + buffer.length * numOfChan * 2, true);
  writeString(view, 8, "WAVE");
  writeString(view, 12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, numOfChan, true);
  view.setUint32(24, buffer.sampleRate, true);
  view.setUint32(28, buffer.sampleRate * numOfChan * 2, true);
  view.setUint16(32, numOfChan * 2, true);
  view.setUint16(34, 16, true);
  writeString(view, 36, "data");
  view.setUint32(40, buffer.length * numOfChan * 2, true);

  let offset = 44;
  const channels: Float32Array[] = [];
  for (let i = 0; i < numOfChan; i += 1) {
    channels.push(buffer.getChannelData(i));
  }

  const interleaved = interleave(channels);
  for (let i = 0; i < interleaved.length; i += 1) {
    const sample = Math.max(-1, Math.min(1, interleaved[i]));
    view.setInt16(offset, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
    offset += 2;
  }

  return new Blob([view], { type: "audio/wav" });
}

function interleave(channels: Float32Array[]): Float32Array {
  if (channels.length === 1) {
    return channels[0];
  }
  const length = channels[0].length;
  const result = new Float32Array(length * channels.length);
  for (let i = 0; i < length; i += 1) {
    for (let j = 0; j < channels.length; j += 1) {
      result[i * channels.length + j] = channels[j][i];
    }
  }
  return result;
}

function writeString(view: DataView, offset: number, text: string): void {
  for (let i = 0; i < text.length; i += 1) {
    view.setUint8(offset + i, text.charCodeAt(i));
  }
}
