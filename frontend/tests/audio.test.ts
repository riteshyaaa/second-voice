import { describe, expect, it } from "vitest";
import { encodeWavPCM, TARGET_RATE } from "../lib/audio";

async function bytes(b: Blob): Promise<DataView> {
  return new DataView(await b.arrayBuffer());
}

describe("encodeWavPCM", () => {
  it("writes a valid 16 kHz mono PCM16 header", async () => {
    const v = await bytes(encodeWavPCM(new Float32Array([0, 0.5, -0.5])));
    const tag = (o: number, n = 4) =>
      Array.from(new Uint8Array(v.buffer.slice(o, o + n)), (c) => String.fromCharCode(c)).join("");
    expect(tag(0)).toBe("RIFF");
    expect(tag(8)).toBe("WAVE");
    expect(tag(12)).toBe("fmt ");
    expect(tag(36)).toBe("data");
    expect(v.getUint16(20, true)).toBe(1); // PCM
    expect(v.getUint16(22, true)).toBe(1); // mono
    expect(v.getUint32(24, true)).toBe(TARGET_RATE);
    expect(v.getUint16(34, true)).toBe(16);
    expect(v.getUint32(40, true)).toBe(3 * 2);
  });

  it("round-trips sample values with clamping", async () => {
    const v = await bytes(encodeWavPCM(new Float32Array([0, 1, -1, 2, -2])));
    expect(v.getInt16(44, true)).toBe(0);
    expect(v.getInt16(46, true)).toBe(0x7fff);
    expect(v.getInt16(48, true)).toBe(-0x8000);
    expect(v.getInt16(50, true)).toBe(0x7fff); // clamped, not wrapped
    expect(v.getInt16(52, true)).toBe(-0x8000);
  });

  it("produces an audio/wav blob sized 44 + 2/frame", async () => {
    const b = encodeWavPCM(new Float32Array(16000));
    expect(b.type).toBe("audio/wav");
    expect(b.size).toBe(44 + 16000 * 2);
  });
});
