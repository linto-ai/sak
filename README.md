# Speech-To-Text End2End

This repository contains helpers and tools to train end-to-end ASR, and do inference with ASR.

It is based on SpeechBrain and HuggingFace's Transformers packages, which are both based on PyTorch.
It also includes inference with Vosk for (baseline) kaldi models.

The main data format is the one of Kaldi, i.e. folders with files:
```
├── [segments]   : utterance -> file id, start, end
├── text         : utterance -> annotation
├── utt2dur      : utterance -> duration (use tools/kaldi/utils/get_utt2dur.sh if you are missing this file)
└── wav.scp      : file id (or utterance if no segments) -> audio file [with sox/flac conversion]
```
and also optionally (not exploited in most cases):
```
├── spk2gender   : speaker -> gender
├── spk2utt      : speaker -> list of utterances
└── utt2spk      : utterance -> speaker
```


## Structure

```
├── audiotrain/      : Main python library
│   ├── infer/          : Functions and scripts to run inference and evaluate models
│   ├── train/          : Scripts to train models (transformers, speechbrain, ...)
│   └── utils/          : Helpers
├── tools/           : Scripts to cope with audio data (data curation, ...)
│   └── kaldi/utils/    : Scripts to check and complete kaldi's data folders (.sh and .pl scripts)
├── docker/          : Docker environment
└── tests/           : Unittest suite
    ├── data/           : Data to run the tests
    ├── expected/       : Expected outputs for some non-regression tests
    ├── unittests/      : Code of the tests
    └── run_tests.py    : Entrypoint to run tests
```

## Docker

If not done, pull the docker image:
```
docker login registry.linto.ai
docker pull registry.linto.ai/training/jlouradour_wav2vec:latest
```
or build it:
```
cd docker/
docker build -t jlouradour_wav2vec:latest .
```

Run it, with advised options:
```
docker run -it --rm \
    --shm-size=4g \
    --user $(id -u):$(id -g) \
    --env HOME=~ --workdir ~ \
    -v /home:/home \
    --name XXX_wav2vec_workspace \
    registry.linto.ai/training/jlouradour_wav2vec:latest
```
(also add `--gpus all` to use GPU).

If you plan to use `vosk` (kaldi models) with GPU, there is also a (heavier) image:
```
docker login registry.linto.ai
docker pull registry.linto.ai/training/jlouradour_wav2vec_voskgpu:latest
```
that can be built with:
```
cd docker/
docker build -f Dockerfile.vosk_gpu -t jlouradour_wav2vec_voskgpu:latest .
```