class PCMPlayerProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    // A simple FIFO buffer to hold incoming samples.
    this.buffer = new Float32Array(0);
    this.port.onmessage = (event) => {
      // Check if we got a clear command.
      if (event.data && event.data.type === "clearQueue") {
        // Clear the buffer immediately.
        this.buffer = new Float32Array(0);
      } else {
        // Expect event.data to be a Float32Array (or its transferable buffer)
        const newData = new Float32Array(event.data);
        // Append newData to the existing buffer.
        const tmp = new Float32Array(this.buffer.length + newData.length);
        tmp.set(this.buffer);
        tmp.set(newData, this.buffer.length);
        this.buffer = tmp;
      }
    };
  }

  process(inputs, outputs, parameters) {
    const output = outputs[0];
    const channelCount = output.length;
    // We'll try to output as many samples as we have.
    const outputLength = output[0].length;

    // If we have enough samples in our buffer, shift them out.
    if (this.buffer.length >= outputLength) {
      // For each channel, output the same data (mono playback)
      for (let channel = 0; channel < channelCount; channel++) {
        output[channel].set(this.buffer.slice(0, outputLength));
      }
      // Remove the used samples from the buffer.
      this.buffer = this.buffer.slice(outputLength);
    } else {
      // Not enough data, output silence.
      for (let channel = 0; channel < channelCount; channel++) {
        output[channel].fill(0);
      }
    }
    // Keep processing.
    return true;
  }
}

registerProcessor("pcm-player-processor", PCMPlayerProcessor);
