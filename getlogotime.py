#!/usr/bin/env python3

import sys
import os
import glob
import subprocess
import numpy as np
import scipy
import scipy.signal
import datetime

def pcm_data(path, sample_rate):
    devnull = open(os.devnull)
    proc = subprocess.Popen(['ffmpeg', '-i', path, '-f', 's16le', '-ac', '1', '-ar', str(sample_rate), '-'], stdout=subprocess.PIPE, stderr=devnull)
    devnull.close()
    scale = 1./float(1 << ((8 * 2) - 1))
    y = scale * np.frombuffer(proc.stdout.read(), '<i2').astype(np.float32)
    return y

def stft_raw(series, sample_rate, win_length, hop_length, hz_count, dtype):
    window = 'hann'
    pad_mode='reflect'
    fft_window = scipy.signal.get_window(window, win_length, fftbins=True)
    axis = -1
    n = fft_window.shape[axis]
    lpad = int((n_fft - n) // 2)
    lengths = [(0, 0)] * fft_window.ndim
    lengths[axis] = (lpad, int(n_fft - n - lpad))
    fft_window = np.pad(fft_window, lengths, mode='constant')
    fft_window = fft_window.reshape((-1, 1))
    series = np.pad(series, int(n_fft // 2), mode=pad_mode)
    frame_count = 1 + int((len(series) - n_fft) / hop_length) # Where n_fft = frame_length
    frames_data = np.lib.stride_tricks.as_strided(series, shape=(n_fft, frame_count), strides=(series.itemsize, hop_length * series.itemsize))
    MAX_MEM_BLOCK = 2**8 * 2**10
    n_columns = int(MAX_MEM_BLOCK / (hz_count * (dtype(0).itemsize)))
    return (frames_data, fft_window, n_columns)

config = {
        'source_frame_start': 0,    # (x * sample_rate) / hop_length)
        'source_frame_end':   None, # (x * sample_rate) / hop_length)
        'matching_min_score': 0.15,
        'matching_skip':      0,    # Jump forward X seconds after a match.
        'matching_ignore':    0,    # Ignore additional matches X seconds after the last one.
        'output_title':       None, # Set a title to create ".meta" file, and "X-chapters.mp3"
    }

config['source_path'] = sys.argv[1]
config['matching_samples'] = sys.argv[2]

dtype = np.complex64
n_fft=2048
hz_count = int(1 + n_fft // 2) # 1025 (Hz buckets)
win_length = n_fft
hop_length = int(win_length // 4)
sample_rate = 22050
sample_crop_start = 5 # The first 4 seem to get damaged
sample_crop_end = 2
sample_warn_allowance = 3
match_any_sample = True

source_series = pcm_data(config['source_path'], sample_rate)
source_time_total = (float(len(source_series)) / sample_rate)

samples = []

if not os.path.exists(config['matching_samples']):
    print('Missing samples folder: ' + config['matching_samples'])
    sys.exit()

if os.path.isdir(config['matching_samples']):
    files = sorted(glob.glob(config['matching_samples'] + '/*'))
else:
    files = [config['matching_samples']]

for sample_path in files:
    if os.path.isfile(sample_path):
        sample_series = pcm_data(sample_path, sample_rate)
        sample_frames, fft_window, n_columns = stft_raw(sample_series, sample_rate, win_length, hop_length, hz_count, dtype)
        sample_data = np.empty((int(1 + n_fft // 2), sample_frames.shape[1]), dtype=dtype, order='F')

        for bl_s in range(0, sample_data.shape[1], n_columns):
            bl_t = min(bl_s + n_columns, sample_data.shape[1])
            sample_data[:, bl_s:bl_t] = scipy.fft.fft(fft_window * sample_frames[:, bl_s:bl_t], axis=0)[:sample_data.shape[0]]

        sample_data = abs(sample_data)
        sample_height = sample_data.shape[0]
        sample_length = sample_data.shape[1]
        x = 0
        sample_start = 0

        while x < sample_length:
            total = 0
            for y in range(0, sample_height):
                total += sample_data[y][x]
            if total >= 1:
                sample_start = x
                break
            x += 1

        sample_start += sample_crop_start # The first few frames seem to get modified, perhaps due to compression?
        sample_end = (sample_length - sample_crop_end)
        samples.append([
                sample_start,
                sample_end,
                os.path.basename(sample_path),
                sample_data
            ])

source_frames, fft_window, n_columns = stft_raw(source_series, sample_rate, win_length, hop_length, hz_count, dtype)

if config['source_frame_end'] == None:
   config['source_frame_end'] = source_frames.shape[1]

matching = {}
match_count = 0
match_last_time = None
match_last_ignored = False
match_skipping = 0
matches = []
results_end = {}
results_dupe = {}

for sample_id, sample_info in enumerate(samples):
    results_end[sample_id] = {}
    results_dupe[sample_id] = {}

    for k in range(0, (sample_info[1] + 1)):
        results_end[sample_id][k] = 0
        results_dupe[sample_id][k] = 0

for block_start in range(config['source_frame_start'], config['source_frame_end'], n_columns): # Time in 31 blocks
    block_end = min(block_start + n_columns, config['source_frame_end'])
    set_data = abs((scipy.fft.fft(fft_window * source_frames[:, block_start:block_end], axis=0)).astype(dtype))
    print('\r{}'.format(str(datetime.timedelta(seconds=((float(block_start) * hop_length) / sample_rate)))), end="")
    x = 0
    x_max = (block_end - block_start)
    while x < x_max:
        if match_skipping > 0:
            if x == 0:
                print('    Skipping {}'.format(match_skipping))
            match_skipping -= 1
            x += 1
            continue

        matching_complete = []

        for matching_id in list(matching):
            sample_id = matching[matching_id][0]
            sample_x = (matching[matching_id][1] + 1)

            if sample_id in matching_complete:
                continue

            hz_score = abs(set_data[0:hz_count,x] - samples[sample_id][3][0:hz_count,sample_x])
            hz_score = sum(hz_score)/float(len(hz_score))

            if hz_score < config['matching_min_score']:
                if sample_x >= samples[sample_id][1]:
                    match_start_time = ((float(x + block_start - samples[sample_id][1]) * hop_length) / sample_rate)
                    results_end[sample_id][sample_x] += 1

                    if (config['matching_skip']) or (match_last_time == None) or ((match_start_time - match_last_time) > config['matching_ignore']):
                        match_last_ignored = False
                    else:
                        match_last_ignored = True

                    matches.append([sample_id, match_start_time, match_last_ignored])
                    match_last_time = match_start_time

                    if config['matching_skip']:
                        match_skipping = ((config['matching_skip'] * sample_rate) / hop_length)
                        print('    Skipping {}'.format(match_skipping))
                        matching = {}
                        break # No more 'matching' entires
                    else:
                        del matching[matching_id]
                        matching_complete.append(sample_id)
                else:
                    matching[matching_id][1] = sample_x

            elif matching[matching_id][2] < sample_warn_allowance and sample_x > 10:
                matching[matching_id][2] += 1
            else:
                results_end[sample_id][sample_x] += 1
                del matching[matching_id]

        if match_skipping > 0:
            continue

        for matching_sample_id in matching_complete:
            for matching_id in list(matching):
                if match_any_sample or matching[matching_id][0] == matching_sample_id:
                    sample_id = matching[matching_id][0]
                    sample_x = matching[matching_id][1]
                    results_dupe[sample_id][sample_x] += 1
                    del matching[matching_id] # Cannot be done in the first loop (next to continue), as the order in a dictionary is undefined, so you could have a match that started later, getting tested first.

        for sample_id, sample_info in enumerate(samples):
            sample_start = sample_info[0]
            hz_score = abs(set_data[0:hz_count,x] - sample_info[3][0:hz_count,sample_start])
            hz_score = sum(hz_score)/float(len(hz_score))

            if hz_score < config['matching_min_score']:
                match_count += 1
                print('')
                exit()
        x += 1

print('\nno match found. reset timestamp.\n\r0:00:00.000000')
