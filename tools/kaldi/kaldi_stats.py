#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import warnings

from linastt.utils.misc import commonprefix
from linastt.utils.kaldi import parse_kaldi_wavscp
from linastt.utils.audio import get_audio_duration

UNK = "_"

def get_utt2dur_duration(
    utt2dur_file,
    check_wav_duration=False,
    warn_if_longer_than=3600,
    warn_if_shorter_than=0.005,
    ):

    if os.path.isdir(utt2dur_file):
        utt2dur_file += "/utt2dur"
    assert os.path.isfile(utt2dur_file), f"Missing file: {utt2dur_file}"

    min_duration = float("inf")
    max_duration = 0
    total_duration = 0
    number = 0

    line = None
    try:
        with open(utt2dur_file, 'r') as f:
            for line in f:
                id, duration = line.strip().split(" ")
                duration = float(duration)
                if duration < min_duration:
                    min_duration = duration
                    if warn_if_shorter_than and duration < warn_if_shorter_than:
                        warnings.warn(f"Duration of {id} in {utt2dur_file} is short: {duration}")
                if duration > max_duration:
                    max_duration = duration
                    if warn_if_longer_than and duration > warn_if_longer_than:
                        warnings.warn(f"Duration of {id} in {utt2dur_file} is long: {duration}")
                total_duration += duration
                number += 1

    except Exception as e:
        raise RuntimeError(f"Error while reading {utt2dur_file} (line: {line})") from e

    number_wav = UNK
    duration_wav = UNK
    wavscp = os.path.join(os.path.dirname(os.path.realpath(utt2dur_file)), "wav.scp")
    segments = os.path.join(os.path.dirname(os.path.realpath(utt2dur_file)), "segments")
    if os.path.isfile(wavscp):
        with open(wavscp, 'r') as f:
            number_wav = len([l for l in f.readlines() if l.strip()])
        if check_wav_duration:
            wav = parse_kaldi_wavscp(wavscp)
            if not os.path.isfile(segments):
                duration_wav = total_duration
            else:
                duration_wav = 0
                for _, path in wav.items():
                    if os.path.isfile(path):
                        duration_wav += get_audio_duration(path)
                    else:
                        print(f"WARNING: missing file {path}")
                        duration_wav = UNK
                        break

    res = {
        "name": os.path.dirname(utt2dur_file),
        "# wav": number_wav
    }
    if check_wav_duration:
        res.update({
            "wav duration": duration_wav,
        })
    res.update({
        "# segments": number,
        "total duration": total_duration,
        "min duration": min_duration,
        "max duration": max_duration,
    })
    return res

def second2time(val):
    if val == float("inf"):
        return "_"
    # Convert seconds to time
    hours = int(val // 3600)
    minutes = int((val % 3600) // 60)
    seconds = int(val % 60)
    milliseconds = int((val % 1) * 1000)
    s = f"{seconds:02d}.{milliseconds:03d}"
    if hours > 0 or minutes > 0:
        s = f"{minutes:02d}:{s}"
    if hours > 0:
        s = f"{hours:02d}:{s}"
    return s

def print_stats(stats):
    assert len(stats) > 0, "No stats to print."

    commonroot = commonprefix([s["name"] for s in stats], end="/")

    def to_string(val, use_common_root=True):
        if isinstance(val, float):
            return second2time(val)
        if isinstance(val, int):
            return str(val)
        if use_common_root:
            return str(val)[len(commonroot):]
        return str(val)
    
    total_stats = accu_stats(stats)

    keys = stats[0].keys()
    max_len = dict(
        (k, max([len(to_string(d[k])) for d in stats + [total_stats]] + [len(k)])) for k in keys
    )

    def align(k):
        return "<" if k == "name" else ">"

    stats = sorted(stats, key=lambda s: s["name"])
    for i, s in enumerate(stats):
        s = {k: to_string(v) for k, v in s.items()}
        fstring = "| " + " | ".join(f"{{{k}:{align(k)}{max_len[k]}}}" for k in keys) + " |"
        if i == 0:
            # Print header
            print(fstring.format(**dict((k, "-"*max_len[k]) for k in keys)))
            print(fstring.format(**dict((k, k) for k in keys)))
            print(fstring.format(**dict((k, "-"*max_len[k]) for k in keys)))
        print(fstring.format(**s))

    if len(stats) > 1:
        print(fstring.format(**dict((k, "-"*max_len[k]) for k in keys)))
        s = {k: to_string(v, use_common_root=False) for k, v in total_stats.items()}
        print(fstring.format(**s))

def accu_stats(stats, default="TOTAL"):
    assert len(stats) > 0, "No stats to print."
    res = {}
    for s in stats:
        for k, v in s.items():
            if k not in res:
                res[k] = v
            elif isinstance(v, (float,int)):
                if "min" in k:
                    res[k] = min(res[k], v)
                elif "max" in k:
                    res[k] = max(res[k], v)
                else:
                    if res[k] == UNK:
                        res[k] = 0
                    res[k] += v
            else:
                if res[k] != v:
                    res[k] = default
    return res

if __name__ == "__main__":

    import argparse
    parser = argparse.ArgumentParser(description="Get duration of a dataset in kaldi format.")
    parser.add_argument("input", type=str, help="Path to utt2dur file or folder containing it.", nargs='+')
    parser.add_argument("--check-wav-duration", action='store_true', help="Check total duration of wav files as well (might be long to compute).")
    parser.add_argument("--warn-if-longer-than", default=3600, type=float, help="Warn if duration is longer than this value (in seconds).")
    parser.add_argument("--warn-if-shorter-than", default=0.005, type=float, help="Warn if duration is shorter than this value (in seconds).")
    args = parser.parse_args()

    all_stats = []
    for file_or_folder in args.input:
        if os.path.isfile(file_or_folder) or os.path.isdir(file_or_folder+"/utt2dur"):
            all_files = [file_or_folder]
        else:
            all_files = []
            for root, dirs, files in os.walk(file_or_folder):
                if "utt2dur" in files:
                    all_files.append(os.path.join(root, "utt2dur"))
        for filename in all_files:
            all_stats.append(
                get_utt2dur_duration(
                    filename,
                    check_wav_duration=args.check_wav_duration,
                    warn_if_longer_than=args.warn_if_longer_than,
                    warn_if_shorter_than=args.warn_if_shorter_than,
                )
            )

    print_stats(all_stats)