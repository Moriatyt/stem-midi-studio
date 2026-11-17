"""Run in the isolated CPU model environment, not the Gradio environment."""
import argparse
import numpy as np
import soundfile as sf
import torch
from piano_transcription_inference import PianoTranscription
import librosa


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('audio')
    parser.add_argument('output')
    parser.add_argument('checkpoint')
    args = parser.parse_args()
    torch.set_num_threads(4)
    audio, rate = sf.read(args.audio, always_2d=True, dtype='float32')
    audio = audio.mean(axis=1)
    if rate != 16000:
        audio = librosa.resample(audio, orig_sr=rate, target_sr=16000)
    if not np.isfinite(audio).all():
        raise ValueError('Audio contains invalid samples')
    model = PianoTranscription(device='cpu', checkpoint_path=args.checkpoint)
    model.transcribe(audio, args.output)


if __name__ == '__main__':
    main()
