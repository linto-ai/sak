#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import random
import regex as re


from linastt.utils.kaldi import check_kaldi_dir


def create_cut(
    input_folders,
    output_folder,
    maximum,
    regex=None,
    random_seed=None,
    throw_if_output_exists=True,
    ):

    if isinstance(input_folders, str):
        input_folders = [input_folders]

    has_segments = None

    for input_folder in input_folders:

        for file in ["text", "wav.scp", "utt2dur", "spk2utt", "utt2spk", "spk2gender"]:
            assert os.path.isfile(input_folder + "/" + file), f"Missing file: {input_folder}/{file}"

        if os.path.isfile(input_folder + "/segments"):
            _has_segments = True
        else:
            _has_segments = False
            print(f"WARNING: {input_folder} has no segments file")
        if has_segments is None:
            has_segments = _has_segments
        else:
            assert has_segments == _has_segments, f"Some folders have segments files and not others: {input_folder}"

        if throw_if_output_exists and os.path.isdir(output_folder):
            raise RuntimeError(f"Output folder already exists. Please remove it first if you want to regenerate it:\n#\trm -R {output_folder}")

    os.makedirs(output_folder, exist_ok=True)

    utt_ids = []
    wav_ids = []
    spk_ids = []

    if os.path.exists(output_folder + "/segments"):
        os.remove(output_folder + "/segments")

    with open(output_folder + "/text", 'w') as text_file, \
        open(output_folder + "/wav.scp", 'w') as wavscp_file, \
        open(output_folder + "/utt2dur", 'w') as utt2dur, \
        open(output_folder + "/utt2spk", 'w') as utt2spk, \
        open(output_folder + "/spk2utt", 'w') as spk2utt, \
        open(output_folder + "/spk2gender", 'w') as spk2gender:

        for input_folder in input_folders:

            with open(input_folder + "/text", 'r') as f:
                if random_seed is not None:
                    random.seed(random_seed)
                    lines = f.readlines()
                    random.shuffle(lines)
                    num_dones = 0
                    for i, line in enumerate(lines):
                        if maximum and num_dones == maximum:
                            break
                        id = _get_first_field(line)
                        if regex and not re.search(regex + r"$", id):
                            continue
                        assert id not in utt_ids, f"Utterance {id} already exists"
                        utt_ids.append(id)
                        text_file.write(line)
                        num_dones += 1
                else:
                    num_dones = 0
                    for i, line in enumerate(f):
                        if maximum and num_dones == maximum:
                            break
                        id = _get_first_field(line)
                        if regex and not re.search(regex + r"$", id):
                            continue
                        assert id not in utt_ids, f"Utterance {id} already exists"
                        utt_ids.append(id)
                        text_file.write(line)
                        num_dones += 1

            if len(utt_ids) == 0:
                raise RuntimeError("No utterances found")

            if os.path.isfile(input_folder + "/segments"):
                with open(input_folder + "/segments", 'r') as f, \
                    open(output_folder + "/segments", 'a') as segments:
                    for line in f:
                        id = _get_first_field(line)
                        if id in utt_ids:
                            wav_id = line.split(" ")[1]
                            if wav_id not in wav_ids:
                                wav_ids.append(wav_id)
                            segments.write(line)
            else:
                wav_ids = utt_ids

            with open(input_folder + "/wav.scp", 'r') as f:
                for line in f:
                    id = _get_first_field(line)
                    if id in wav_ids:
                        wavscp_file.write(line)

            with open(input_folder + "/utt2dur", 'r') as f:
                for line in f:
                    id = _get_first_field(line)
                    if id in utt_ids:
                        utt2dur.write(line)

            with open(input_folder + "/utt2spk", 'r') as f:
                for line in f:
                    id = _get_first_field(line)
                    if id in utt_ids:
                        utt2spk.write(line)
                        spk = line.strip().split(" ")[1]
                        if spk not in spk_ids:
                            spk_ids.append(spk)

            with open(input_folder + "/spk2utt", 'r') as f:
                for line in f:
                    spk = _get_first_field(line)
                    if spk in spk_ids:
                        utt_s = line.strip().split(" ")[1:]
                        new_utt_s = [u for u in utt_s if u in utt_ids]
                        if not len(new_utt_s):
                            continue
                        new_utt_s = " ".join(new_utt_s)
                        spk2utt.write(f"{spk}\t{new_utt_s}\n")
                        spk_ids.append(spk)

            with open(input_folder + "/spk2gender", 'r') as f:
                for line in f:
                    spk = _get_first_field(line)
                    if spk in spk_ids:
                        spk2gender.write(line)

    return check_kaldi_dir(output_folder, language=None)


def _get_first_field(line):
    f = line.split(" ", 1)
    assert len(f), "Got an empty line"
    return f[0]


if __name__ == '__main__':

    import argparse
    parser = argparse.ArgumentParser(description="Create a kaldi folder with only a subset of utterances from a kaldi folder")
    parser.add_argument("input_folder", type=str, help="Input folder(s) with kaldi files", nargs='+')
    parser.add_argument("output_folder", type=str, help="Output folder")
    parser.add_argument("--maximum", type=int, help="Number of lines to keep (maximum)", default=None)
    parser.add_argument("--regex", default=None, type=str, help="A regular expression to select an id")
    parser.add_argument("--random_seed", default=None, type=int, help="Random seed to choose randomly the utterances (if not specified, the first utterances will be taken)")
    args = parser.parse_args()

    create_cut(
        args.input_folder, args.output_folder,
        maximum=args.maximum,
        random_seed=args.random_seed,
        regex=args.regex,
    )
