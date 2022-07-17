"""Add random reverb to the audio stems based on DDSP library."""

import os
import numpy as np
import glob
import argparse
import librosa
import ddsp
from tqdm import tqdm
from utils.file_utils import get_config
from utils.file_utils import pickle_load, pickle_dump
from midi_ddsp.utils.audio_io import save_wav
from midi_ddsp.utils.inference_utils import ensure_same_length

# Reverb IR from: https://www.housecallfm.com/download-gns-personal-lexicon-480l, saved in ./ir
REVERB_TYPES = {'small': 'Small Hall.aif', 'medium': 'Medium Hall.aif', 'large': 'Large Hall.aif'}


def add_reverb(wav, reverb_type, sample_rate):
    reverb_ir, _ = librosa.load(os.path.join(os.path.abspath(__file__), REVERB_TYPES[reverb_type]), sr=sample_rate,
                                mono=True)
    reverb_length = len(reverb_ir)
    reverb = ddsp.effects.Reverb(trainable=False, reverb_length=reverb_length)
    wav = reverb(wav[np.newaxis], reverb_ir)
    return wav


def audio_augmentation(data_dir, output_dir, sample_rate):
    # if output_dir is provided, then save to the output_dir.
    if output_dir:
        output_dir = os.path.join(output_dir, os.path.basename(data_dir))
        os.makedirs(output_dir, exist_ok=True)
    else:  # else, change in place
        output_dir = data_dir

    # load metadata
    pickle_path = os.path.join(data_dir, 'metadata.pickle')
    metadata = pickle_load(pickle_path)

    # sample a reverb type for all stems
    reverb_type = np.random.choice(REVERB_TYPES)

    wav_files = glob.glob(f'{data_dir}/*.wav')
    stem_wav_files = [f for f in wav_files if 'mix.wav' not in f]  # exclude mix wav
    wavs_after_reverb = []
    for wav_file in stem_wav_files:
        wav, _ = librosa.load(wav_file, sr=sample_rate, mono=True)
        wav = add_reverb(wav, reverb_type, sample_rate)
        save_wav(wav[0].numpy(), os.path.join(output_dir, os.path.basename(wav_file)), sample_rate=sample_rate)
        wavs_after_reverb.append(wav[0].numpy())

    midi_audio_mix = np.sum(
        np.stack(ensure_same_length(
            [wavs_after_reverb[i].astype(np.float64) for i in range(len(wavs_after_reverb))], axis=0),
            axis=-1),
        axis=-1)

    save_wav(midi_audio_mix, os.path.join(output_dir, 'mix.wav'), sample_rate=sample_rate)

    # add metadata and save
    metadata['audio_augmentation'] = f'reverb_{reverb_type}'
    pickle_dump(metadata, os.path.join(output_dir, 'metadata.pickle'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Audio augmentation')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--synthesis_dir', type=str, default=None, metavar='N',
                       help='the directory generated by MIDI-DDSP synthesis.')
    group.add_argument('--multi_synthesis_dir', type=str, default=None, metavar='N',
                       help='the directory containing multiple folders generated by MIDI-DDSP synthesis.')
    parser.add_argument('--output_dir', type=str, default=None, metavar='N',
                        help='the directory for output.')
    args = parser.parse_args()

    config = get_config()

    if args.synthesis_dir:
        synth_dir_list = [args.synthesis_dir]
    elif args.multi_synthesis_dir:
        synth_dir_list = glob.glob(f'{args.multi_synthesis_dir}/*/')

    for synth_dir in tqdm(synth_dir_list):
        audio_augmentation(synth_dir, args.output_dir, config['sample_rate'])
