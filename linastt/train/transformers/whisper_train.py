#!/usr/bin/env python3

import os
import sys
import datetime
import shutil

from linastt.utils.env import use_gpu # handle option --gpus (and set environment variables at the beginning)
from linastt.utils.text import format_text
from linastt.utils.logs import gpu_usage, get_num_gpus, gpu_free_memory, tic, toc
from linastt.utils.dataset import kaldi_folder_to_dataset, process_dataset
from linastt.utils.augment import SpeechAugment
from linastt.utils.misc import remove_commonprefix
from linastt.utils.wer import compute_wer

import logging
import json

from transformers.trainer_utils import PREFIX_CHECKPOINT_DIR , get_last_checkpoint

import transformers
import torch
import random

from transformers import (
    WhisperFeatureExtractor,
    WhisperForConditionalGeneration,
    WhisperProcessor,
    Seq2SeqTrainer,
    Seq2SeqTrainingArguments,
    TrainerCallback, 
    TrainerState, 
    TrainerControl,
)

from dataclasses import dataclass
from typing import Any, Dict, List, Union

import warnings
warnings.simplefilter(action='ignore', category=FutureWarning) # remove warning : the 'mangle_dupe_cols' keyword is deprecated and will be removed in a future version. Please take steps to stop the use of 'mangle_dupe_cols'
logger = logging.getLogger(__name__)

# data Collator
@dataclass
class DataCollatorSpeechSeq2SeqWithPadding:
    processor: Any

    def __call__(self, features: List[Dict[str, Union[List[int], torch.Tensor]]]) -> Dict[str, torch.Tensor]:
        # split inputs and labels since they have to be of different lengths and need different padding methods
        # first treat the audio inputs by simply returning torch tensors
        input_features = [{"input_features": feature["input_features"]} for feature in features]
        batch = self.processor.feature_extractor.pad(input_features, return_tensors="pt")

        # get the tokenized label sequences
        label_features = [{"input_ids": feature["labels"]} for feature in features]
        # pad the labels to max length
        labels_batch = self.processor.tokenizer.pad(label_features, return_tensors="pt")

        # replace padding with -100 to ignore loss correctly
        labels = labels_batch["input_ids"].masked_fill(labels_batch.attention_mask.ne(1), -100)

        # if bos token is appended in previous tokenization step,
        # cut bos token here as it's append later anyways
        if (labels[:, 0] == self.processor.tokenizer.bos_token_id).all().cpu().item():
            labels = labels[:, 1:]

        batch["labels"] = labels

        return batch

# WER Computer    
def compute_metrics(pred, language):
    pred_ids = pred.predictions
    label_ids = pred.label_ids

    # replace -100 with the pad_token_id
    label_ids[label_ids == -100] = processor.tokenizer.pad_token_id
    
    # we do not want to group tokens when computing the metrics
    pred_str = processor.tokenizer.batch_decode(pred_ids, skip_special_tokens=True)
    label_str = processor.tokenizer.batch_decode(label_ids, skip_special_tokens=True)

    return compute_wer(label_str, pred_str, normalization=language, use_percents=True)

class SavePeftModelCallback(TrainerCallback):
    def on_save(
        self,
        args: Seq2SeqTrainingArguments,
        state: TrainerState,
        control: TrainerControl,
        **kwargs,
    ):
        checkpoint_folder = os.path.join(args.output_dir, f"{PREFIX_CHECKPOINT_DIR}-{state.global_step}")

        peft_model_path = os.path.join(checkpoint_folder, "adapter_model")
        # pytorch_model_path = os.path.join(checkpoint_folder, "pytorch_model.bin")
        kwargs["model"].save_pretrained(peft_model_path)
        # pytorch_model_path = os.path.join(checkpoint_folder, "pytorch_model.bin")
        # if os.path.exists(pytorch_model_path):
        #     os.remove(pytorch_model_path)
        return control


def args_to_str(args, ignore = [
        # Taken into account somewhere else
        "train",
        "valid",
        # Too much...
        "data_augment_rir",
        "data_augment_noise",
        # Should not have an influence on the result
        "output_dir",
        "overwrite_output_dir",
        "disable_first_eval",
        "gpus",
        "batch_size_eval",
        "online", "offline", "offline_dev",
        ]):
    if not isinstance(args, dict):
        args = args.__dict__

    s = "_".join(("{}-{}".format("".join([a[0] for a in k.replace("-","_").split("_")]),
            {True: 1, False: 0}.get(v, str(v).replace("/","_"))
        )) for k,v in sorted(args.items())
        if k not in ignore
    )
    while "__" in s:
        s = s.replace("__","_")
    return s

def dataset_pseudos(trainset, validset):
    train_folders = sorted(trainset.split(","))
    valid_folders = sorted(validset.split(","))
    all_folders = train_folders + valid_folders
    all_folders = remove_commonprefix(all_folders, "/")
    train_folders = all_folders[:len(train_folders)]
    valid_folders = all_folders[len(train_folders):]
    def base_folder(f):
        f = f.split("/")[0].split("\\")[0]
        if len(f.split("-")) > 1:
            f = "".join([s[0] for s in f.split("-")])
        return f
    train_base_folders = set(base_folder(f) for f in train_folders)
    valid_base_folders = set(base_folder(f) for f in valid_folders)
    train_folders = sorted(list(set([
        base_folder(f.replace("/","_")) if base_folder(f) in valid_base_folders else base_folder(f)
        for f in train_folders
    ])))
    valid_folders = sorted(list(set([
        base_folder(f.replace("/","_")) if base_folder(f) in train_base_folders else base_folder(f)
        for f in valid_folders
    ])))
    return "t-"+"-".join(train_folders), "v-"+"-".join(valid_folders)
    

# Main()
if __name__ == "__main__":

    from transformers.models.whisper.tokenization_whisper import TO_LANGUAGE_CODE

    import argparse
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('train', help="A kaldi folder, or a file containing a list of kaldi folders, with training data")
    parser.add_argument('valid', help="A kaldi folder, or a file containing a list of kaldi folders, with validation data")
    parser.add_argument('--max_duration', help="maximum signal length for training data", default=30, type=int)
    parser.add_argument('--min_duration', help="minimum signal length for training data", default=0.1, type=int)
    parser.add_argument('--debug', help="to perform small experiment, check if things are running", default=False, action="store_true")
    parser.add_argument('--base_model', help='Whisper model to tune',default="openai/whisper-small", type=str) #  MohammedNasri/whisper-small-AR
    parser.add_argument('--lang', help='Language to tune',default="fr", type=str, choices=TO_LANGUAGE_CODE.values())
    parser.add_argument('--task', help='Task to tune',default="transcribe", type=str)
    parser.add_argument('--use_peft', help='To use PEFT method', default=False, action = "store_true")
    parser.add_argument('--gpus', help="List of GPU index to use (starting from 0)", default= None)
    parser.add_argument('--offline', help="do not load and process training audio files on the fly (precompute all MFCC)", default=False, action="store_true")
    parser.add_argument('--offline_dev', help="do not load and process validation audio files on the fly (precompute all MFCC)", default=False, action="store_true")
    # Data augmentation
    parser.add_argument('--data_augmentation', help='To use data augmentation on audio', default=False, action = "store_true")
    parser.add_argument('--text_augmentation', help='To use data augmentation on text', default=False, action = "store_true")
    parser.add_argument('--data_augment_noise', help="Folder with audio files to simulate noises (used only with --data_augment)",
        default="/media/nas/CORPUS_FINAL/Corpus_audio/Corpus_noise/distant_noises", type=str
    )
    parser.add_argument('--data_augment_rir', help="Folder with audio files to simulate reverberation (used only with --data_augment)",
        default="/media/nas/CORPUS_FINAL/Corpus_audio/Corpus_noise/[simulated_rirs_16k/smallroom/rir_list,simulated_rirs_16k/mediumroom/rir_list,simulated_rirs_16k/largeroom/rir_list]", type=str
    )
    # hyparams :
    parser.add_argument('--batch_size', help='Batch size', default=8, type=int)
    parser.add_argument('--batch_size_eval', help='Batch size for validation (by default same as for training)', default=None, type=int)
    parser.add_argument('--learning_rate', help='Learning rate',default=1e-03, type=float)
    parser.add_argument('--seed', help='seed',default=42, type=int)
    parser.add_argument('--gradient_accumulation_steps', help='Gradient accumulation steps',default=16, type=int)
    parser.add_argument('--num_epochs', help='Num of Epochs',default=3, type=int)
    parser.add_argument('--eval_steps', help="Validation and checkpoint model every n steps (advised: 400)", default=None, type=int)
    parser.add_argument('--max_text_length', help='text max length of each sentence in label',default=448, type=int)
    parser.add_argument('--weight_decay', help='weight decay',default=0.01, type=float)
    parser.add_argument('--overwrite_output_dir', help='overwrite outpu dir',default=False, action = "store_true")
    parser.add_argument('--disable_first_eval', help="to disable the evaluation of the init model", default=False, action="store_true")
    # parser.add_argument('--warmup_steps', help='warmup steps',default=500, type=int)
    parser.add_argument('--output_dir', help='Output trained model', default="./Model")
    args = parser.parse_args()
    

    if not args.batch_size_eval:
        args.batch_size_eval = args.batch_size
    
    # HyperParams 
    SAMPLE_RATE = 16000
    BATCH_SIZE = args.batch_size
    BATCH_SIZE_EVAL = args.batch_size_eval
    WEIGHT_DECAY= args.weight_decay
    GRADIENT_ACCUMULATION_STEPS=args.gradient_accumulation_steps
    LR = args.learning_rate
    NUM_EPOCH = args.num_epochs
    AUDIO_MAX_LENGTH = 480000
    MAX_TEXT_LENGTH = args.max_text_length
    PEFT = args.use_peft
    SEED = args.seed
    warmup_ratio = 0.1
    # warmup_steps = args.warmup_steps
    
    USE_MIXED_PRECISION = False # use_gpu()
    USE_MIXED_PRECISION_CPU = False # Too many problems
    args.online = (not args.offline or args.data_augmentation or args.text_augmentation)
    online_dev = not args.offline_dev
    
    base_model = args.base_model
    task = args.task
    data_augmentation = args.data_augmentation

    train_pseudo, valid_pseudo = dataset_pseudos(args.train, args.valid)
    output_folder = f"{args.output_dir}/{train_pseudo}_{valid_pseudo}_{args_to_str(args)}"
    output_untrained_folder = f"{args.output_dir}/{valid_pseudo}_{args_to_str({'base_model': args.base_model})}"
    
    # Detecting last checkpoint.
    resume_from_checkpoint = None
    if os.path.isdir(output_folder):
        if args.overwrite_output_dir:
            shutil.rmtree(output_folder)
        else:
            resume_from_checkpoint = transformers.trainer_utils.get_last_checkpoint(output_folder)
            if resume_from_checkpoint:
                print("Resuming from checkpoint:", resume_from_checkpoint)
    
    if os.path.isdir(os.path.join(output_folder, 'finals')):
        print(f"Output folder{output_folder} already exists: skipping it.")
        sys.exit(0)
    os.makedirs(output_folder, exist_ok=True)
    shutil.copy2(__file__, os.path.join(output_folder, os.path.basename(__file__)))

    readme = open(output_folder+"/README.txt", "a")

    # Print the date and time
    print(datetime.datetime.now(), file=readme)
    print(" ".join(sys.argv), file = readme)
    print(sys.argv[0]+ " --"+ " --".join([k if v is True else k+"="+str(v) for k,v in args.__dict__.items() if v is not False]), file = readme)
    print("", file = readme)

    task = args.task  
    language = args.lang.lower()
    
    feature_extractor = WhisperFeatureExtractor.from_pretrained(base_model)
    
    # Create the processor
    processor = WhisperProcessor.from_pretrained(base_model, language=language, task=task)

    tokenizer_func = lambda x: processor.tokenizer(x).input_ids
    
    data_train = args.train
    data_val = args.valid
    trainsetmeta, train_dataset = kaldi_folder_to_dataset(
        data_train,
        shuffle = True,
        online = args.online,
        max_data = (2 * args.batch_size) if args.debug else None,
        choose_data_with_max_duration = args.debug,
        min_duration = args.min_duration,
        max_duration = args.max_duration,
        max_text_length = (tokenizer_func, MAX_TEXT_LENGTH),
        logstream = readme,
    )
    testsetmeta, eval_dataset = kaldi_folder_to_dataset(
        data_val,
        shuffle = False,
        online = online_dev,
        max_data = (2 * args.batch_size) if args.debug else None,
        choose_data_with_max_duration = args.debug,
        # min_duration = args.min_duration,
        # max_duration = args.max_duration,
        max_text_length = (tokenizer_func, MAX_TEXT_LENGTH),
        logstream = readme,
    )
    train_dataset = train_dataset.shuffle(seed = SEED)

    trainset_len = trainsetmeta["samples"]
    testset_len = testsetmeta["samples"]
    BATCH_SIZE = min(trainset_len, BATCH_SIZE)
    max_steps = round(NUM_EPOCH * trainset_len / BATCH_SIZE)
    if args.eval_steps:
        eval_steps = args.eval_steps
    else:
        eval_steps = round(max_steps / NUM_EPOCH)
    warmup_steps = round(max_steps * warmup_ratio)

    trainsetmeta = ", ".join("{} {}".format(v,k) for k,v in trainsetmeta.items())
    testsetmeta = ", ".join("{} {}".format(v,k) for k,v in testsetmeta.items())
    print("Training set:", trainsetmeta)
    print("Test set:", testsetmeta)
    if readme:
        print("", file = readme)
        print("Training set:", trainsetmeta, file = readme)
        print("Test set:", testsetmeta, file = readme)
        print("", file = readme)
        readme.flush()

    data_augmenter = None
    if data_augmentation :
        if "[" not in args.data_augment_rir:
            raise RuntimeError("--data_augment_rir syntax must be /root/folder/[rir/file1,rir/file2,...]")
        rir_dir = args.data_augment_rir.split("[")[0].rstrip("/")
        rir_lists = args.data_augment_rir.split("[")[1].split("]")[0].split(",")
        for f in rir_lists:
            if not os.path.isfile(os.path.join(rir_dir, f)):
                raise RuntimeError("RIR list file {} does not exist".format(os.path.join(rir_dir, f)))
        data_augmenter = SpeechAugment(
            noise_dir = args.data_augment_noise,
            rir_dir = rir_dir,
            rir_lists = rir_lists,
            apply_prob =1,
            sample_rate =16000,
        )
    text_augmenter = None
    if args.text_augmentation:
        if language == "ar":
            import random
            from linastt.utils.text_ar import \
                symbols_to_letters, \
                normalize_arabic_currencies, \
                digit2word, \
                remove_arabic_diacritics, \
                normalize_punct, \
                get_arabic_only
            from linastt.utils.text_utils import remove_punctuations
            def text_augmenter(text):
                input_tokens_before = tokenizer_func(text)
                
                assert len(input_tokens_before) <= MAX_TEXT_LENGTH, "Input text length exceeds MAX_TEXT_LENGTH."
    
                text = remove_arabic_diacritics(text)
                if random.random() < 0.5:
                    text = symbols_to_letters(text, language, lower_case=False)
                    text = normalize_arabic_currencies(text)
                if random.random() < 0.5:
                    text = digit2word(text)
                if random.random() < 0.5:
                    text = remove_punctuations(text)
                else:
                    # Keep punctuations / add terminal dot if not there
                    text = normalize_punct(text)
                    if text[-1] not in ',-:!;.؛؟،?_':
                        text += "."

                output_tokens = tokenizer_func(text)
                if len(output_tokens) > MAX_TEXT_LENGTH:
                    print("Warning: Output text length exceeds MAX_TEXT_LENGTH. Performing text augmentation.")
                    return text_augmenter(text)

                return text
        else:
            raise NotImplementedError(f"Text augmentation is not implemented for language {language}")
        
    train_dataset = process_dataset(processor, train_dataset, data_augmenter = data_augmenter, text_augmenter = text_augmenter, batch_size = BATCH_SIZE, logstream = readme)
    eval_dataset = process_dataset(processor, eval_dataset, batch_size = BATCH_SIZE_EVAL, logstream = readme)
    if readme is not None:
        readme.flush()
          
    data_collator = DataCollatorSpeechSeq2SeqWithPadding(processor=processor)
        
    if PEFT: 

        from transformers import BitsAndBytesConfig
        from peft import LoraConfig, PeftModel, LoraModel, get_peft_model, prepare_model_for_int8_training , TaskType

        quantization_config = BitsAndBytesConfig(llm_int8_enable_fp32_cpu_offload=True)

        model = WhisperForConditionalGeneration.from_pretrained(
            base_model, 
            load_in_8bit=True,
            device_map="auto" if use_gpu() else None, 
            quantization_config=quantization_config
            ) 
        
        model = prepare_model_for_int8_training(model)

        # Apply LoRA :load a PeftModel and specify that we are going to use low-rank adapters (LoRA) using get_peft_model utility function from peft
        config = LoraConfig(r=32, 
                        lora_alpha=64, 
                        target_modules=".*decoder.*(self_attn|encoder_attn).*(q_proj|v_proj)$",
                        lora_dropout=0.05, 
                        bias="none",
                    )

        model = get_peft_model(model, config)
        model.print_trainable_parameters()
    else :
        model = WhisperForConditionalGeneration.from_pretrained(base_model)
        model.gradient_checkpointing_enable()
    
    # Note: we do not train language identification, but rather focus on the target language
    special_tokens_ids = processor.tokenizer.additional_special_tokens_ids
    special_tokens = processor.tokenizer.additional_special_tokens
    model.config.forced_decoder_ids =  [
        [1, special_tokens_ids[special_tokens.index(f"<|{language}|>")]],
        [2, special_tokens_ids[special_tokens.index("<|transcribe|>")]],
        [3, special_tokens_ids[special_tokens.index("<|notimestamps|>")]],
    ]
    model.config.suppress_tokens = []
    model.train(True)
       
    gpu_log = open(os.path.join(output_folder, "gpu_log.txt"), "a") if use_gpu() else None
    gpu_usage("START", stream = gpu_log)
    
    if use_gpu():
        # Set the device to run on (GPU if available, otherwise CPU)
        model = model.to(torch.device("cuda"))
        mem = gpu_usage("Model loaded", stream = gpu_log)
        min_mem = + mem + (0.5 * mem if USE_MIXED_PRECISION else 0) + 2 * mem + mem
        print("Estimation of minimal GPU memory:", min_mem)
    
    random.seed(SEED)
    transformers.set_seed(SEED)
    training_args = Seq2SeqTrainingArguments(
        output_dir=output_folder, # change to a repo name of your choice
        label_names = ['labels'],
        evaluation_strategy="steps",
        max_steps = max_steps,
        eval_steps = eval_steps,
        logging_steps = eval_steps,
        save_steps = eval_steps,
        save_total_limit=2,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        load_best_model_at_end=True,
        num_train_epochs=NUM_EPOCH,
        per_device_train_batch_size=BATCH_SIZE,
        per_device_eval_batch_size=BATCH_SIZE_EVAL,
        gradient_accumulation_steps=GRADIENT_ACCUMULATION_STEPS,
        learning_rate=LR,
        optim="adamw_torch",
        weight_decay=WEIGHT_DECAY,
        warmup_steps=warmup_steps,
        lr_scheduler_type="linear",
        predict_with_generate=True,
        fp16 = use_gpu(),
        generation_max_length=MAX_TEXT_LENGTH,
        logging_dir=f'{output_folder}/logs',
        remove_unused_columns=not PEFT,
        resume_from_checkpoint=resume_from_checkpoint,
        data_seed=SEED,
        seed=SEED,
        no_cuda = not use_gpu(),
        overwrite_output_dir=args.overwrite_output_dir,
        dataloader_num_workers=4,
    )

    trainer = Seq2SeqTrainer(
        args=training_args,
        model=model,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        data_collator=data_collator,
        tokenizer=processor.feature_extractor,
        compute_metrics = lambda x: compute_metrics(x, language),
        callbacks=[transformers.EarlyStoppingCallback(early_stopping_patience= 15)] + ([SavePeftModelCallback] if PEFT else []),
    )
    model.config.use_cache = False 

    # Evaluate initial model
    if not args.disable_first_eval:
        init_results = output_folder + "/init_eval.json"
        if not os.path.isfile(init_results):
            print(f"Evaluating model in folder: {output_untrained_folder}")
            init_results0 = output_untrained_folder + "/init_eval.json"
            if not os.path.exists(init_results0):
                print("Evaluating initial model", init_results0)
                if not os.path.exists(output_untrained_folder):
                    os.makedirs(output_untrained_folder)
                
                res = trainer.evaluate()
                json.dump(res, open(init_results0, "w"), indent = 2)

            if init_results != init_results0:
                shutil.copy(init_results0, init_results)

    # training
    tic()
    print(f"Training model in folder: {output_folder}")
    trainer.train(resume_from_checkpoint=resume_from_checkpoint)
    toc("Training", stream = readme)
    
    # Save model
    processor.save_pretrained(output_folder+"/finals")
    model.save_pretrained(output_folder+"/finals")