#!/usr/bin/env python3

import jiwer
import re
import os

def normalize_line(line):
    return re.sub("\s+" , " ", line).strip()

def parse_text_with_ids(file_name):
    with open(file_name, 'r', encoding='utf-8') as f:
        res_dict = {}
        for line in f:
            line = normalize_line(line).split(maxsplit=1)
            id = line[0]
            text = line[1] if len(line) > 1 else ""
            if id in res_dict and res_dict[id] != text:
                raise ValueError(f"Id {id} is not unique in {file_name}")
            res_dict[id] = text
    return res_dict

def parse_text_without_ids(file_name):
    return dict(enumerate([normalize_line(l) for l in open(file_name,'r',encoding='utf-8').readlines()]))

def compute_wer(refs, preds, use_ids=True, debug=False):
    """
    Compute WER between two files.
    :param refs: path to the reference file, or dictionary {"id": "text..."}, or list of texts
    :param preds: path to the prediction file, or dictionary {"id": "text..."}, or list of texts.
                  Must be of the same type as refs.
    :param use_ids: (for files) whether reference and prediction files includes id as a first field
    :param debug: if True, print debug information. If string, write debug information to the file.
    """
    # Open the test dataset human translation file
    if isinstance(refs, str):
        assert os.path.isfile(refs), f"Reference file {refs} doesn't exist"
        assert isinstance(preds, str) and os.path.isfile(preds)
        if use_ids:
            refs = parse_text_with_ids(refs)
            preds = parse_text_with_ids(preds)
        else:
            refs = parse_text_without_ids(refs)
            preds = parse_text_without_ids(preds)

    if isinstance(refs, dict):
        assert isinstance(preds, dict)

        # Reconstruct two lists of pred/ref with the intersection of ids
        ids = [id for id in refs.keys() if id in preds]

        if len(ids) == 0:
            if len(refs) == 0:
                raise ValueError("Reference file is empty")
            if len(preds) == 0:
                raise ValueError("Prediction file is empty")
            raise ValueError(
                "No common ids between reference and prediction files")
        if len(ids) != len(refs) or len(ids) != len(preds):
            print("WARNING: ids in reference and/or prediction files are missing or different.")

        refs = [refs[id] for id in ids]
        preds = [preds[id] for id in ids]

    assert isinstance(refs, list)
    assert isinstance(preds, list)
    assert len(refs) == len(preds)

    if debug:
        with open(debug, 'w+') if isinstance(debug, str) else open("/dev/stdout", "w") as f:
            for i in range(len(refs)):
                if refs[i] != preds[i]:
                    f.write(f"Line {i} with id [ {ids[i]} ] doesn't match.\n")
                    f.write("---\n")
                    f.write("ref.: " + refs[i] + "\n")
                    f.write("pred: " + preds[i] + "\n")
                    f.write(
                        "------------------------------------------------------------------------\n")

    # Calculate WER for the whole corpus

    measures = jiwer.compute_measures(refs, preds)

    wer_score = measures['wer']
    sub_score = measures['substitutions']
    del_score = measures['deletions']
    hits_score = measures['hits']
    ins_score = measures['insertions']
    count = hits_score + del_score + sub_score

    score_details = {
        'wer': wer_score,
        'del': (float(del_score) / count),
        'ins': (float(ins_score) / count),
        'sub': (float(sub_score) / count),
        'count': count,
    }

    return score_details


def str2bool(string):
    str2val = {"true": True, "false": False}
    string = string.lower()
    if string in str2val:
        return str2val[string]
    else:
        raise ValueError(f"Expected True or False")


if __name__ == "__main__":

    import argparse

    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('references', help="File with reference text lines (ground-truth)", type=str)
    parser.add_argument('predictions', help="File with predicted text lines (by an ASR system)", type=str)
    parser.add_argument('--use_ids', help="Whether reference and prediction files includes id as a first field", default=True, type=str2bool, metavar="True/False")
    parser.add_argument('--debug', help="Output file to save debug information, or True / False", type=str, default=False, metavar="FILENAME/True/False")
    parser.add_argument('--normalization', help="Language to use for text normalization", default=None)
    args = parser.parse_args()

    target_test = args.references
    target_pred = args.predictions

    assert os.path.isfile(target_test), f"File {target_test} doesn't exist"
    assert os.path.isfile(target_pred), f"File {target_pred} doesn't exist"

    debug = args.debug
    if debug and debug.lower() in ["true", "false"]:
        debug = eval(debug.title())
    use_ids = args.use_ids

    result = compute_wer(target_test, target_pred, use_ids=use_ids, debug=debug)
    print(' ------------------------------------------------------------------------------------------------------- ')
    print(' WER: {:.2f} % [ deletions: {:.2f} % | insertions: {:.2f} % | substitutions: {:.2f} % ](count: {})'.format(
        result['wer'] * 100, result['del'] * 100, result['ins'] * 100, result['sub'] * 100, result['count']))
    print(' ------------------------------------------------------------------------------------------------------- ')
