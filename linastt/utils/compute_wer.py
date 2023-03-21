#!/usr/bin/env python3

import jiwer
import sys

def parse_text_with_ids(file_name):
    with open(file_name, 'r') as f:
        res_dict = {}
        for line in f:
            line = line.strip().split(maxsplit=1)
            id = line[0]
            text = line[1] if len(line)>1 else ""
            if id in res_dict and res_dict[id] != text:
               raise ValueError(f"Id {id} is not unique in {file_name}")
            res_dict[id] = text
    return res_dict

def compute_wer(filename_ref ,filename_pred , debug=False, use_ids=True):
    # Open the test dataset human translation file
    if use_ids: 
        refs_dict = parse_text_with_ids(filename_ref)
        preds_dict = parse_text_with_ids(filename_pred)
    else:
        refs_dict = dict(enumerate([l.strip() for l in open(filename_ref).readlines()]))
        preds_dict = dict(enumerate([l.strip() for l in open(filename_pred).readlines()]))
        
    # Get the intersection of the ids (dictionary keys)
    common_ids = set(refs_dict.keys()) & set(preds_dict.keys())
    union_ids = set(refs_dict.keys()) | set(preds_dict.keys())

    # Print a warning if intersection is not the same as the union
    if common_ids != union_ids and common_ids:
        print("Warning: ids in reference and/or prediction files are missing or different.")
    
    # Fail if intersection is empty
    if not common_ids and common_ids != union_ids:
        raise ValueError("No common ids between reference and prediction files")
    
    # Reconstruct two lists of pred/ref with the intersection of ids
    ids = [id for id in refs_dict.keys() if id in preds_dict]
    refs = [refs_dict[id] for id in ids]
    preds = [preds_dict[id] for id in ids]

    if debug:
        with open(debug, 'w+') if isinstance(debug, str) else open("/dev/stdout", "w") as f:
            for i in range(len(refs)):
                if refs[i] != preds[i]:
                    f.write(f"Line {i} with id [ {ids[i]} ] doesn't match.\n")
                    f.write("---\n")
                    f.write("ref: " + refs[i] + "\n")
                    f.write("pred: " + preds[i] + "\n")
                    f.write("------------------------------------------------------------------------\n")
    
    # Calculate WER for the whole corpus
    
    measures = jiwer.compute_measures(refs, preds)
    
    wer_score = measures['wer']
    sub_score = measures['substitutions']
    del_score = measures['deletions']
    hits_score = measures['hits']
    ins_score = measures['insertions']   
    count = hits_score + del_score + sub_score 
    
    score_details = {
        'wer'  : wer_score,
        'del' : (float(del_score) / count),
        'ins'  : (float(ins_score) / count),
        'sub'  : (float(sub_score) / count),
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
    parser.add_argument('references', help= " Input the Reference text ", type=str)
    parser.add_argument('predictions', help= " Predicted text (by an ASR system)", type=str)
    parser.add_argument('--use_ids', help= " If uses ids in computing wer ", default=True, type=str2bool)
    parser.add_argument('--debug', help="Output file to save debug information, or True / False", type=str, default=False)
    args = parser.parse_args()

    target_test = args.references
    target_pred = args.predictions
    debug = args.debug
    if debug and debug.lower() in ["true", "false"]:
        debug = eval(debug.title())
    use_ids = args.use_ids

    result = compute_wer(target_test ,target_pred , debug=debug ,use_ids=use_ids)
    print(' ------------------------------------------------------------------------------------------------------- ')
    print(' WER_score : {:.2f} % | [ deletions : {:.2f} % | insertions {:.2f} % | substitutions {:.2f} % ](count : {})'.format(
        result['wer'] * 100, result['del'] * 100, result['ins'] * 100, result['sub'] * 100, result['count']))
    print(' ------------------------------------------------------------------------------------------------------- ')