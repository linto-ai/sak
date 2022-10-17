from audiotrain.utils.env import auto_device
from audiotrain.utils.dataset import to_audio_batches
from audiotrain.utils.misc import flatten
from audiotrain.utils.logs import tic, toc, gpu_mempeak

import speechbrain as sb
import torch
import torch.nn.utils.rnn as rnn_utils

import transformers
import pyctcdecode

import os
import tempfile
import json


def speechbrain_infer(
    model,
    audios,
    batch_size = 1,
    device = None,
    arpa_path = None, alpha = 0.5, beta = 1.0,
    sort_by_len = False,
    log_memtime = False,
    ):
    """
    Transcribe audio(s) with speechbrain model

    Args:
        model: SpeechBrain model or a path to the model
        audios:
            Audio file path(s) or Audio waveform(s) or Audio tensor(s)
        batch_size: int
            Batch size (default 1).
        device: str
            Device to use (default "cuda:0" if GPU available else "cpu").
            Can be: "cpu", "cuda:0", "cuda:1", etc.
        arpa_path: str
            Path to arpa file for decoding with Language Model.
        alpha: float
            Language Model weight.
        beta: float
            Word insertion penalty.
        sort_by_len: bool
            Sort audio by length before batching (longest audio first).
        log_memtime: bool
            If True, print timing and memory usage information.
    """
    if isinstance(model, str):
        model = speechbrain_load_model(model, device = device)

    assert isinstance(model, sb.pretrained.interfaces.EncoderASR), f"model must be a SpeechBrain model or a path to the model (got {type(model)})"

    sampling_rate = model.audio_normalizer.sample_rate

    batches = to_audio_batches(audios, return_format = 'torch',
        sampling_rate = sampling_rate,
        batch_size = batch_size,
        sort_by_len = sort_by_len,
    )

    if arpa_path is None:

        # Compute best predictions
        tic()
        predictions = []
        for batch in batches:
            pred = speechbrain_transcribe_batch(model, batch)
            predictions.extend(pred)
            if log_memtime: gpu_mempeak()
        if log_memtime: toc("apply network", log_mem_usage = True)

    else:
        assert os.path.isfile(arpa_path), f"Arpa file {arpa_path} not found"

        # Compute framewise log probas
        tic()
        logits = []
        for batch in batches:
            pred, log_probas = speechbrain_compute_logits(model, batch)
            logits.append(log_probas)
            if log_memtime: gpu_mempeak()
        if log_memtime: toc("apply network", log_mem_usage = True)
   
        tokenizer = model.tokenizer
        processor = speechbrain_decoder_with_lm(tokenizer, arpa_path, alpha = alpha, beta = beta)

        # Apply language model
        tic()
        num_outputs = tokenizer.get_piece_size() + 2
        predictions = [processor.batch_decode(l.numpy()[:,:,:num_outputs]).text for l in logits]
        predictions = flatten(predictions)
        if log_memtime: toc("apply language model", log_mem_usage = True)

    return predictions


def pack_sequences(tensors, device = "cpu"):
    if len(tensors) == 1:
        return tensors[0].unsqueeze(0), torch.Tensor([1.])
    tensor = rnn_utils.pad_sequence(tensors, batch_first=True)
    wav_lens = [len(x) for x in tensors]
    maxwav_lens = max(wav_lens)
    wav_lens = torch.Tensor([l/maxwav_lens for l in wav_lens])
    return tensor.to(device), wav_lens.to(device)

def speechbrain_load_model(path, device = None):
    if device is None:
        device = auto_device()
    model = sb.pretrained.EncoderASR.from_hparams(source = path, run_opts= {"device": device})
    model.train(False)
    model.requires_grad_(False)
    return model

def speechbrain_transcribe_batch(model, audios):
    batch, wav_lens = pack_sequences(audios, device = model.device)
    reco = model.transcribe_batch(batch, wav_lens)[0]
    reco = [s.lower() for s in reco]
    return reco

def speechbrain_compute_logits(model, audios):
    batch, wav_lens = pack_sequences(audios, device = model.device)
    log_probas = model.forward(batch, wav_lens)
    indices = sb.decoders.ctc_greedy_decode(log_probas, wav_lens, blank_id = 0)
    reco = model.tokenizer.decode(indices)
    reco = [s.lower() for s in reco]
    return reco, log_probas

def speechbrain_decoder_with_lm(tokenizer, arpa_file, alpha = 0.5, beta = 1.0):
    """
    tokenizer: tokenizer from speechbrain
    arpa_file: path to arpa file
    alpha: language model weight
    beta: word insertion penalty

    return a processor of type Wav2Vec2ProcessorWithLM to be used as "processor.batch_decode(log_probas.numpy()).text"
    """
    labels = [{'':" ", ' ⁇ ':"<pad>"}.get(i,i).lower() for i in tokenizer.decode([[i] for i in range(tokenizer.get_piece_size())])] + ["<s>", "</s>"]
    vocab = dict((c,i) for i,c in enumerate(labels))
    vocab_file = os.path.join(tempfile.gettempdir(), "vocab.json")
    json.dump(vocab, open(vocab_file, "w"), ensure_ascii = False)
    tokenizer_hf = transformers.Wav2Vec2CTCTokenizer(
        vocab_file,
        bos_token='<s>', eos_token='</s>', unk_token='<unk>', pad_token='<pad>',
        word_delimiter_token=' ', replace_word_delimiter_char=' ', do_lower_case=False
    )
    decoder = pyctcdecode.build_ctcdecoder(
        labels =  labels,
        kenlm_model_path = arpa_file,
        alpha = alpha,
        beta = beta,
    )
    processor = transformers.Wav2Vec2ProcessorWithLM(
        feature_extractor = transformers.Wav2Vec2FeatureExtractor(),
        tokenizer = tokenizer_hf,
        decoder = decoder
    )
    return processor

if __name__ == "__main__":

    import sys
    import argparse

    parser = argparse.ArgumentParser(description='Train wav2vec2 on a given dataset',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('data', help="Path to data (file(s) or kaldi folder(s))", nargs='+')
    parser.add_argument('--model', help="Path to trained folder, or name of a pretrained model", default = "speechbrain/asr-wav2vec2-commonvoice-fr")
    parser.add_argument('--arpa', help="Path to a n-gram language model", default = None)
    parser.add_argument('--output', help="Output path (will print on stdout by default)", default = None)
    parser.add_argument('--batch_size', help="Maximum batch size", type=int, default=32)
    parser.add_argument('--sort_by_len', help="Sort by (decreasing) length", default=False, action="store_true")
    parser.add_argument('--disable_logs', help="Disable logs (on stderr)", default=False, action="store_true")
    args = parser.parse_args()


    if not args.output:
        args.output = sys.stdout
    elif args.output == "/dev/null":
        # output nothing
        args.output = open(os.devnull,"w")
    else:
        args.output = open(args.output, "w")

    for reco in speechbrain_infer(
        args.model, args.data,
        batch_size = args.batch_size,
        sort_by_len = args.sort_by_len,
        arpa_path = args.arpa,
        log_memtime = not args.disable_logs,
    ):
        print(reco, file = args.output)
