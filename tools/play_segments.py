#!/usr/bin/env python3
 
import os

from linastt.utils.player import play_audiofile
from linastt.utils.output_format import to_linstt_transcription


def check_results(audio_file, results, min_sec = 0, play_segment = False):
    for i, segment in enumerate(results["segments"]):
        # print(f'{segment["text"]} : {segment["start"]}-{segment["end"]}')
        # play_audiofile(audio_file, segment["start"], segment["end"], ask_for_replay = True)

        if play_segment:
            segment["words"] = [segment]

        for iw, word in enumerate(segment["words"]):

            start = word["start"]
            end = word["end"]
            if end < min_sec:
                continue

            print(f"Segment {i+1}/{len(results['segments'])}, word {iw+1}/{len(segment['words'])}")
            print(f'{word["word"]} : {start}-{end}')
            
            x = play_audiofile(audio_file, start, end, additional_commands = {"q": "quit", "s": "skip segment", 20.05: "skip to 20.05"})

            if x == "q":
                return
            if x == "s":
                break
            if isinstance(x, float|int):
                min_sec = x

if __name__ == "__main__":

    import argparse

    parser = argparse.ArgumentParser(description='Play audio file using results from a segmentation into words / segments')
    parser.add_argument('audio_file', type=str, help='Audio file')
    parser.add_argument('results_file', type=str, help='Results file')
    parser.add_argument('--segments', default=False, action='store_true', help='Play segments instead of words')
    parser.add_argument('--min_sec', default=0, type=float, help='Minimum second to start playing from (default: 0)')
    args = parser.parse_args()

    audio_file = args.audio_file
    results_file = args.results_file

    assert os.path.isfile(audio_file), f"Cannot find audio file {audio_file}"
    assert os.path.isfile(results_file), f"Cannot find result file {results_file}"

    results = to_linstt_transcription(results_file)

    check_results(audio_file, results, play_segment=args.segments, min_sec=args.min_sec)