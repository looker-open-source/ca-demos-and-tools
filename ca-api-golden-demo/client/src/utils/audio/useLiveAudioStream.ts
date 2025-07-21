// Copyright 2025 Google LLC
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     https://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

import { useState, useRef } from "react";

export const useLiveAudioStream = (
  onChunk: (base64Chunk: string) => void,
  bufferDuration = 500 // milliseconds between processing accumulated samples
) => {
  const [streaming, setStreaming] = useState<boolean>(false);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const accumulatedSamplesRef = useRef<number[]>([]);
  const intervalRef = useRef<number | null>(null);
  const targetSampleRate = 16000;

  // Downsample a Float32Array from sampleRate to targetRate.
  const downsampleBuffer = (
    buffer: Float32Array,
    sampleRate: number,
    targetRate: number
  ): Float32Array => {
    if (targetRate === sampleRate) return buffer;
    const sampleRateRatio = sampleRate / targetRate;
    const newLength = Math.round(buffer.length / sampleRateRatio);
    const result = new Float32Array(newLength);
    let offsetResult = 0;
    let offsetBuffer = 0;
    while (offsetResult < result.length) {
      const nextOffsetBuffer = Math.round((offsetResult + 1) * sampleRateRatio);
      let accum = 0,
        count = 0;
      for (
        let i = offsetBuffer;
        i < nextOffsetBuffer && i < buffer.length;
        i++
      ) {
        accum += buffer[i];
        count++;
      }
      result[offsetResult] = count ? accum / count : 0;
      offsetResult++;
      offsetBuffer = nextOffsetBuffer;
    }
    return result;
  };

  // Process accumulated samples: downsample, convert to 16-bit PCM, encode as Base64,
  // and call the onChunk callback.
  const processAccumulatedSamples = () => {
    if (
      !audioContextRef.current ||
      accumulatedSamplesRef.current.length === 0
    ) {
      return;
    }
    const sampleRate = audioContextRef.current.sampleRate;
    const samples = new Float32Array(accumulatedSamplesRef.current);
    const downsampled = downsampleBuffer(samples, sampleRate, targetSampleRate);
    // Convert float samples (-1 to 1) to 16-bit PCM.
    const int16Buffer = new Int16Array(downsampled.length);
    for (let i = 0; i < downsampled.length; i++) {
      let s = Math.max(-1, Math.min(1, downsampled[i]));
      int16Buffer[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
    }
    const blob = new Blob([int16Buffer.buffer], {
      type: `audio/pcm;rate=${targetSampleRate}`,
    });
    // Convert blob to Base64.
    const reader = new FileReader();
    reader.onloadend = () => {
      const base64data = reader.result as string;
      const commaIndex = base64data.indexOf(",");
      const base64Chunk =
        commaIndex !== -1 ? base64data.slice(commaIndex + 1) : base64data;
      onChunk(base64Chunk);
    };
    reader.readAsDataURL(blob);
    // Clear the accumulator.
    accumulatedSamplesRef.current = [];
  };

  const startStreaming = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaStreamRef.current = stream;
      const audioContext = new AudioContext();
      audioContextRef.current = audioContext;
      const source = audioContext.createMediaStreamSource(stream);
      // Create a ScriptProcessorNode with a reasonable buffer size.
      const processor = audioContext.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;
      source.connect(processor);
      // We don't need to connect to destination if we don't want to hear the audio.
      processor.connect(audioContext.destination);
      processor.onaudioprocess = (event) => {
        const inputBuffer = event.inputBuffer.getChannelData(0);
        accumulatedSamplesRef.current.push(...Array.from(inputBuffer));
      };
      // Process accumulated samples every bufferDuration ms.
      intervalRef.current = window.setInterval(
        processAccumulatedSamples,
        bufferDuration
      );
      setStreaming(true);
    } catch (err) {
      console.error("Error starting live audio stream:", err);
    }
  };

  const stopStreaming = () => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    if (processorRef.current) {
      processorRef.current.disconnect();
      processorRef.current = null;
    }
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }
    // Process any remaining samples.
    processAccumulatedSamples();
    setStreaming(false);
  };

  return { streaming, startStreaming, stopStreaming };
};
