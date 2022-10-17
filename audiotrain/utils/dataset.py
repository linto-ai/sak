import os
import pathlib
from operator import itemgetter
import logging
import random
import math

from .audio import load_audio
from .text import remove_special_words

import datasets
import transformers

import numpy as np
np.warnings.filterwarnings('ignore', category=np.VisibleDeprecationWarning) # VisibleDeprecationWarning: Creating an ndarray from ragged nested sequences (which is a list-or-tuple of lists-or-tuples-or ndarrays with different lengths or shapes) is deprecated. If you meant to do this, you must specify 'dtype=object' when creating the ndarray.


def kaldi_folder_to_dataset(kaldi_path,
    online = False,
    shuffle = False,
    max_data = None,
    min_len = None,
    max_len = None,
    choose_data_with_max_len = False,
    sort_by_len = 0,
    weights = 1,
    split = None,
    return_csv = False,
    include_duration = False,
    verbose = True,
    logstream = None,
    do_cache = True,
    ):
    """
    Take a kaldi folder and returns a tuple (metadata dict, HuggingFace dataset)

    Parameters
    ----------
    kaldi_path : str
        Path to kaldi folder, or list of paths to kaldi folders
    online : bool
        If True, audio files will be loaded and processed on-the-fly (out of core).
        If False, audio files will be loaded and processed at first, and *cached* (typically in ~/.cache/huggingface/datasets/mydataset).
    shuffle : bool
        If True, the dataset will be shuffled.
    max_data : int
        Maximum number of data to use. If None, use all files in the kaldi folder
    min_len : int
        Minimum length in seconds of audio. If None, no limit.
    max_len : int
        Maximum length in seconds of audio. If None, no limit.
    weights : float
        Weight of this dataset. Has an interest if several datasets are specified.
        Data will be duplicated (upsampled when weights > 1).
    choose_data_with_max_len : bool
        If True and max_data is not None, the longest utterances will be chosen (good for testing if everything fits in memory).
    return_csv : bool
        If True, return the CSV file instead of the dataset.
    include_duration : bool
        If True, include the duration of the audio in the dataset.
        Only has an effect if return_csv is True.
    split : str
        Split to use ("train", "dev", "test"). If None, unspecified.
    verbose : bool
        Whether to print some steps
    logstream : file
        Stream to print some logs to
    do_cache : bool
        Internal. Do not use
    
    Returns
    -------
    dataset : datasets.Dataset
    """

    # Logging business (start)
    ds_progress_bar = datasets.utils.is_progress_bar_enabled()
    loggers = [datasets.builder.logger, datasets.info.logger, datasets.arrow_dataset.logger]
    ds_log_level = [l.getEffectiveLevel() for l in loggers]
    if verbose:
        datasets.utils.enable_progress_bar()
        for l in loggers:
            l.setLevel(logging.WARNING)
    else:
        datasets.utils.disable_progress_bar()
        for l in loggers:
            l.setLevel(logging.ERROR)

    empty_dataset = (
        {"samples": 0, "h duration": 0, "samples (with duplicates)": 0, "h duration (with duplicates)":0, "weight": weights},
        datasets.Dataset.from_dict({})
    )

    if not isinstance(kaldi_path, str):
        if not isinstance(weights, list):
            weights = [weights] * len(kaldi_path)
        ds = [kaldi_folder_to_dataset(p, split = split,
            online = False, shuffle = False,
            max_data = max_data,
            min_len = min_len,
            max_len = max_len,
            choose_data_with_max_len = choose_data_with_max_len,
            sort_by_len = sort_by_len,
            weights = w,
            include_duration = include_duration,
            verbose = verbose,
            logstream = logstream,
            do_cache = False) for p,w in zip(kaldi_path, weights)]

        dataset = datasets.concatenate_datasets([d[1] for d in ds])
        if do_cache:
            dataset = make_cachable(dataset, online = online, shuffle = shuffle, verbose = verbose, logstream = logstream, return_csv = return_csv)

        meta = {
            "samples": sum([d[0]["samples"] for d in ds]),
            "h duration": sum([d[0]["h duration"] for d in ds]),
            "samples (with duplicates)": sum([d[0]["samples (with duplicates)"] for d in ds]),
            "h duration (with duplicates)": sum([d[0]["h duration (with duplicates)"] for d in ds]),
        }

        return meta, dataset

    if not os.path.isdir(kaldi_path):
        raise RuntimeError("Could not find folder %s" % kaldi_path)
    for fname in "text", "wav.scp":
        if not os.path.isfile(kaldi_path +"/" + fname):
            raise RuntimeError("Could not find file %s in folder %s" % (fname, kaldi_path))

    has_segment = os.path.isfile(kaldi_path + "/segments")
    if verbose:
        print("Parsing", kaldi_path, "(no segments)" if not has_segment else "")

    with open(kaldi_path + "/text") as f:
        def split_line(line):
            res = line.strip().split(" ", 1)
            if len(res) == 1:
                res = [res[0], ""]
            return res
        uttids, annots = zip(*map(split_line, f))
        uttids = list(uttids)
        annots = list(annots)

    if not choose_data_with_max_len and max_data and max_data < len(uttids):
        random.seed(69)
        random.shuffle(uttids)
        random.seed(69)
        random.shuffle(annots)
        uttids = uttids[:max_data]
        annots = annots[:max_data]

    # TODO: the reading of wav.scp is a bit crude...
    wav = {}
    with open(kaldi_path + "/wav.scp") as f:
        for line in f:
            fields = line.strip().split()
            wavid = fields[0]
            if line.find("'") >= 0:
                i1 = line.find("'")
                i2 = line.find("'", i1+1)
                path = line[i1+1:i2]
            elif len(fields) > 2:
                path = fields[2]
            else:
                path = fields[1]
            # Look for environment variables in the path
            if "$" in path:
                for var in sorted(os.environ, key = len):
                    path = path.replace("$" + var, os.environ[var])
            wav[wavid] = path


    total_duration = None
    if has_segment:
        segments = {}
        with open(kaldi_path + "/segments") as f:
            for line in f:
                fields = line.strip().split()
                uttid = fields[0]
                wavid = fields[1]
                start = float(fields[2])
                end = float(fields[3])
                duration = end - start
                assert duration > 0
                if max_len and duration > max_len:
                    try:
                        i = uttids.index(uttid)
                    except ValueError: continue
                    uttids.pop(i)
                    annots.pop(i)
                    continue
                elif min_len and duration < min_len:
                    try:
                        i = uttids.index(uttid)
                    except ValueError: continue
                    uttids.pop(i)
                    annots.pop(i)
                    continue
                segments[uttid] = [wavid, start, end]

        if (choose_data_with_max_len and max_data and max_data < len(uttids)) or sort_by_len not in [0, None]:
            # We select the longest utterances
            uttids, annots = zip(*sorted(zip(uttids, annots), key= lambda i:(segments[i[0]][2]-segments[i[0]][1], len(i[1]))))
            if max_data and max_data < len(uttids):
                uttids = uttids[-max_data:]
                annots = annots[-max_data:]
            uttids = list(uttids)
            annots = list(annots)
            # Longest utterances first
            if sort_by_len < 0:
                uttids = list(uttids)
                annots = list(annots)
                uttids.reverse()
                annots.reverse()
        
        if len(uttids) == 0:
            print("WARNING: No data selected! (with min-max duration: {}-{})".format(min_len, max_len))
            return empty_dataset
        wavids, starts, ends = zip(*map(lambda id:segments[id], uttids))
        paths = list(map(lambda id:wav[id], wavids))

        dataset = {
            "ID": uttids,
            "path": paths,
            "start": starts,
            "end": ends,
            "text": annots,
        }
        durations = [end - start for start, end in zip(starts, ends)]

    else: # No segments (take full audio)

        for fname in "utt2dur",:
            if not os.path.isfile(kaldi_path +"/" + fname):
                raise RuntimeError("Could not find file %s in folder %s" % (fname, kaldi_path))
        def parse_line(line):
            f = line.strip().split()
            f[1] = float(f[1])
            return f
        with open(kaldi_path + "/utt2dur") as f:
            durations = dict([parse_line(line) for line in f if line.strip()])

        uttids, annots = zip(*sorted(zip(uttids, annots), key= lambda i:(durations[i[0]], len(i[1]))))
        durations = list(itemgetter(*uttids)(durations))
        if max_len or min_len:
            a = 0
            b = 0
            for d in durations:
                if min_len and d < min_len:
                    a += 1
                if max_len and d > max_len:
                    break
                b += 1
            if b <= a:
                print("WARNING: No data selected! (with min-max duration: {}-{})".format(min_len, max_len))
                return empty_dataset
            uttids = uttids[a:b]
            annots = annots[a:b]
            durations = durations[a:b]
        if choose_data_with_max_len and max_data and max_data < len(uttids):
            uttids = uttids[-max_data:]
            annots = annots[-max_data:]
            durations = durations[-max_data:]

        # Longest utterances first
        if sort_by_len != None and sort_by_len < 0:
            uttids = list(uttids)
            annots = list(annots)
            durations = list(durations)
            uttids.reverse()
            annots.reverse()
            durations.reverse()

        paths = list(map(lambda id:wav[id], uttids))
        dataset = {
            "ID": uttids,
            "path": paths,
            "text": annots,
        }

    total_duration = sum(durations)
    if include_duration:
        dataset["duration"] = durations
    if verbose:
        print("    minmax(duration) = {}-{}".format(min(durations), max(durations)))

    if weights != 1:
        # Duplicate all entries of the dictionary
        #print("Duplicating dataset with weights", weights)
        l = len(dataset["ID"])
        dataset = {k: list(v) * int(weights) + random.Random(45).sample(v, int(len(v) * (weights%1))) for k, v in dataset.items()}
        if weights > 1:
            for i in range(1, math.ceil(weights)+1):
                a = i*l
                b = min((i+1)*l, len(dataset["ID"]))
                dataset["ID"][a:b] = [id + "_%d" % i for id in dataset["ID"][a:b]]

    nsamples_dup = len(dataset["ID"])
    if include_duration:
        total_duration_dup = sum(dataset["duration"])
    else:
        total_duration_dup = total_duration * weights

    dataset = datasets.Dataset.from_dict(dataset,
        split= {
            "train": datasets.Split.TRAIN,
            "dev": datasets.Split.VALIDATION,
            "valid": datasets.Split.VALIDATION,
            "validation": datasets.Split.VALIDATION,
            "test": datasets.Split.TEST,
        }.get(split, split),
    )

    if do_cache:
        dataset = make_cachable(dataset, online = online, shuffle = shuffle, verbose = verbose, logstream = logstream, return_csv = return_csv)

    meta = {
        "samples": len(uttids),
        "h duration": total_duration/3600,
        "samples (with duplicates)" : nsamples_dup,
        "h duration (with duplicates)": total_duration_dup/3600,
        "weight": weights
    }

    metastr = ", ".join("{} {}".format(v,k) for k,v in meta.items())
    if verbose:
        print("   ", metastr)
    if logstream:
        print(kaldi_path, ":", metastr, file= logstream)

    # Logging business (end)    
    if ds_progress_bar:
        datasets.utils.enable_progress_bar()
    else:
        datasets.utils.disable_progress_bar()
    for l, ll in zip(loggers, ds_log_level):
        l.setLevel(ll)

    return meta, dataset

def make_cachable(dataset, online = False, shuffle = False, return_csv = False, verbose = True, logstream = None):
    # - cachable
    # - online streaming
    if shuffle:
        if verbose:
            print("Shuffling dataset")
        dataset = dataset.shuffle(69)
    cache_file_dir = os.path.join(datasets.config.HF_DATASETS_CACHE, "mydataset", dataset._fingerprint)
    if not os.path.isdir(cache_file_dir):
        os.makedirs(cache_file_dir)
    cache_filename = os.path.join(cache_file_dir, "orig.csv")
    if verbose:
        print("Caching CSV dataset in ", cache_filename)
    if logstream:
        logstream.write("- We cached CSV in %s\n" % cache_filename)
    if not os.path.isfile(cache_filename):
        dataset.to_csv(cache_filename)
    if return_csv:
        return cache_filename
    # Use this to pass "origin_metadata = None" so that the caching mechanism will be OK
    data_files = datasets.data_files.DataFilesDict({"train":datasets.data_files.DataFilesList([pathlib.PosixPath(cache_filename)], origin_metadata = None)})
    res = datasets.load_dataset("csv", data_files= data_files,
        streaming = online,
        split= dataset.split, # TODO WTF This fails if split is not "train"...
        cache_dir = cache_file_dir,
        keep_default_na=False, # This is important to avoid pandas to convert "nan" to NaN
    )
    if not online and logstream:
        logstream.write("- Huggingface cached CVS in {}\n".format(format_cache_files(res.cache_files)))
    if isinstance(res, dict) and len(res) == 1:
        res = list(res.values())[0]
    return res

def format_cache_files(cache_files):
    if isinstance(cache_files, list):
        res = list(set([format_cache_files(f) for f in cache_files]))
        pref = commonprefix(res)
        return pref + " | ".join(sorted([f[len(pref):] for f in res if f != pref]))
    elif isinstance(cache_files, dict):
        if "filename" in cache_files:
            return cache_files["filename"]
        elif len(cache_files) == 1:
            return format_cache_files(list(cache_files.values())[0])
        else:
            return str(cache_files)
    else:
        return str(cache_files)
# Return the longest prefix of all list elements.
def commonprefix(m):
    "Given a list of pathnames, returns the longest common leading component"
    if not m: return ''
    s1 = min(m)
    s2 = max(m)
    for i, c in enumerate(s1):
        if c != s2[i]:
            return s1[:i]
    return s1


def process_dataset(processor, dataset,
    batch_size = 32, num_proc = 1,
    data_augmenter = None,
    verbose = True, force_cache = True, logstream = None):
    """
    Process a dataset with a HuggingFace processor.

    Parameters
    ----------
    processor : HuggingFace.Preprocessor
        Processor to use
    dataset : datasets.Dataset
        Dataset to process
    batch_size : int (default: 32)
        Batch size to use
    num_proc : int (default: 1)
        Number of processes to use (not: may be disabled in online mode).
        WARNING: using more than 1 process may lead to hang
    verbose : bool
        Whether to print some steps
    force_cache : bool
        Whether to force the use of the cache (except in the case of online, where it will be disabled)
        Tricky things in HuggingFace's datasets cache mechanism... 
        Maybe this is not needed anymore
    logstream : file
        Stream to print some logs to
    """

    sampling_rate = processor.feature_extractor.sampling_rate
    is_iterable = isinstance(dataset, datasets.IterableDataset) # or not hasattr(dataset, "_fingerprint")
    force_cache = force_cache and not is_iterable
    if force_cache:
        datasets.enable_caching()
        cache_file_dir = os.path.join(datasets.config.HF_DATASETS_CACHE, "mydataset", dataset._fingerprint)
        if not os.path.isdir(cache_file_dir):
            os.makedirs(cache_file_dir)
    if is_iterable:
        for e in dataset:
            column_names = list(e.keys())
            break
        map_kwargs = {}
    else:
        column_names = dataset.column_names
        map_kwargs = {
            "num_proc": num_proc,
        }
        if force_cache:
            map_kwargs.update({
                "cache_file_name" : os.path.join(cache_file_dir, "loaded.arrow"),
                "load_from_cache_file" : True,
            })
    has_segment = "start" in column_names
    if verbose and hasattr(dataset, "_fingerprint"):
        print("Loading audios", dataset._fingerprint)

    if data_augmenter:
        processed = dataset.map(
            lambda row: {"input_values":np.array([1.], dtype=np.float32), "labels":"e"} if (hasattr(transformers.trainer, "SKIPPING") and transformers.trainer.SKIPPING) else {
                "input_values" : data_augmenter(load_audio(row["path"], start = row["start"] if has_segment else None, end = row["end"] if has_segment else None, sampling_rate = sampling_rate)),
                "labels": remove_special_words(row["text"])
            },
            remove_columns = column_names,
            **map_kwargs
        )
    else:
        processed = dataset.map(
            lambda row: {"input_values":np.array([1.], dtype=np.float32), "labels":"e"} if (hasattr(transformers.trainer, "SKIPPING") and transformers.trainer.SKIPPING) else {
                "input_values" : load_audio(row["path"], start = row["start"] if has_segment else None, end = row["end"] if has_segment else None, sampling_rate = sampling_rate),
                "labels": remove_special_words(row["text"])
            },
            remove_columns = column_names,
            **map_kwargs
        )
        
    if logstream and hasattr(processed, "cache_files"):
        logstream.write("- Huggingface cached dataset with loaded audio in {}\n".format(format_cache_files(processed.cache_files)))
    
    # Check characters
    def extract_all_chars(batch):
        all_text = " ".join(batch)
        vocab = sorted(list(set(all_text)))
        return {"vocab": vocab}
    subset = processed
    if hasattr(subset, "__len__"):
        if len(subset) > 100:
            subset = processed.select(random.sample(range(min(len(processed), 100000)),100))
        chars = subset.map(lambda batch:extract_all_chars(batch["labels"]), batched=True, batch_size=-1, remove_columns= processed.column_names)["vocab"]
    else:
        subset = processed.take(100)
        text = [sample["labels"] for sample in subset]
        chars = extract_all_chars(text)["vocab"]
    vocab = processor.tokenizer.get_vocab()
    no_warning = True
    for char in chars:
        if char not in vocab and char != " ":
            if verbose:
                print("WARNING: character {} not in vocabulary".format(char))
            no_warning = False
    if no_warning and verbose:
        print("GOOD: All characters seem to be in vocabulary")
    
    if not is_iterable:
        if "cache_file_name" in map_kwargs:
            map_kwargs.pop("cache_file_name") # Will be done automatically at this point
        map_kwargs.update({"num_proc": num_proc}) # Batch size is used
    if verbose and hasattr(dataset, "_fingerprint"):
        print("Processing audios", processed._fingerprint)
    processed = processed.map(lambda batch: apply_processor(processor, batch, sampling_rate),
        batch_size = batch_size, batched=True,
        **map_kwargs
    )
    if logstream and hasattr(processed, "cache_files"):
        logstream.write("- Huggingface cached pre-processed dataset in {}\n".format(format_cache_files(processed.cache_files)))

    if verbose and hasattr(processor, "_fingerprint"):
        print("Audio processed", processed._fingerprint)

    return processed

def apply_processor(processor, batch, sampling_rate):
    processed = processor(batch["input_values"], sampling_rate= sampling_rate)
    batch["input_values"] = processed.input_values
    with processor.as_target_processor():
        batch["labels"] = processor(batch["labels"]).input_ids
    return batch

def to_audio_batches(
    input,
    batch_size = 0,
    sampling_rate = 16_000,
    mono = True,
    return_format = 'array',
    sort_by_len = False,
    ):
    """ 
    Convert a filename, a kaldi folder, or a list of those into batches of audio
    """
    if isinstance(input, str):
        
        if os.path.isfile(input):
            audio = load_audio(input, sampling_rate = sampling_rate, mono = mono, return_format = return_format)
            if batch_size == 0:
                yield audio
            else:
                yield [audio]
        
        elif os.path.isdir(input):
            _, dataset = kaldi_folder_to_dataset(input, sort_by_len = -1 if sort_by_len else 0)
            batch = []
            for data in dataset:
                audio = load_audio(data["path"], data.get("start"), data.get("end"), sampling_rate = sampling_rate, mono = mono, return_format = return_format)
                if batch_size == 0:
                    yield audio
                else:
                    batch.append(audio)
                    if len(batch) == batch_size:
                        yield batch
                        batch = []
            if len(batch) > 0:
                yield batch

        else:
            raise ValueError(f"Cannot interpret {input} as a file or a directory")

    elif isinstance(input, list):
        batch = []
        for data in input:
            batches = to_audio_batches(data, batch_size = batch_size, sampling_rate = sampling_rate, mono = mono, return_format = return_format, sort_by_len = sort_by_len)
            for b in batches:
                if batch_size == 0 or len(b) == batch_size:
                    yield b
                    continue
                for sample in b:
                    if batch_size == 0:
                        yield sample
                    else:
                        batch.append(sample)
                        if len(batch) == batch_size:
                            yield batch
                            batch = []
        if len(batch) > 0:
            yield batch

    else:
        raise NotImplementedError("Unsupported type: %s" % type(input))