import os
import shutil
import subprocess
import re

from envsubst import envsubst

def parse_kaldi_wavscp(wavscp):
    # TODO: the reading of wav.scp is a bit crude...
    with open(wavscp) as f:
        wav = {}
        for line in f:
            fields = line.strip().split()
            fields = [f for f in fields if f != "|"]
            wavid = fields[0]
            if line.find("'") >= 0:
                i1 = line.find("'")
                i2 = line.find("'", i1+1)
                path = line[i1+1:i2]
            elif len(fields) > 2:
                # examples:
                # sox file.wav -t wav -r 16000 -b 16 - |
                # flac -c -d -s -f file.flac |
                if os.path.basename(fields[1]) == "sox":
                    path = fields[2]
                elif os.path.basename(fields[1]) == "flac":
                    path = fields[-1]
                else:
                    raise RuntimeError(f"Unknown wav.scp format with {fields[1]}")
            else:
                path = fields[1]
            # Look for environment variables in the path
            if "$" in path:
                path = envsubst(path)
            wav[wavid] = path

    return wav

def parse_line(line):
    id_text = line.strip().split(" ", 1)
    if len(id_text) == 1:
        return id_text[0], ""
    return id_text

SPECIAL_CHARS = {
    "en": "",
    "fr": "".join(func("àâäéèêëîïôöùûüÿç") for func in [str.upper, str.lower]),
    "es": "".join(func("áéíóúüñ") for func in [str.upper, str.lower]),
    "de": "".join(func("äöüß") for func in [str.upper, str.lower]),
    "it": "".join(func("àèéìíîòóùú") for func in [str.upper, str.lower]),
    "pt": "".join(func("áâãàéêíóôõúüç") for func in [str.upper, str.lower]),
    "ru": "".join(func("абвгдеёжзийклмнопрстуфхцчшщъыьэюя") for func in [str.upper, str.lower]),
    "tr": "".join(func("âçğıöşü") for func in [str.upper, str.lower]),
    "ar": "".join(func("ءآأؤإئابةتثجحخدذرزسشصضطظعغفقكلمنهويىي") for func in [str.upper, str.lower]),
}

def check_kaldi_dir(dirname, language=None):

    tool_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))),
        "tools", "kaldi", "utils"
    )

    if os.path.isfile(os.path.join(dirname, "text")):
        with open(os.path.join(dirname, "text")) as f:
            texts = dict(parse_line(line) for line in f)

    p = subprocess.Popen([tool_dir + "/fix_data_dir.sh", dirname])
    p.communicate()
    if p.returncode != 0:
        raise RuntimeError("ERROR when running fix_data_dir.sh")
    
    if not os.path.isfile(os.path.join(dirname, "utt2dur")):
        p = subprocess.Popen([tool_dir + "/get_utt2dur.sh", dirname], stderr=subprocess.PIPE)
        p.communicate()
        if p.returncode != 0:
            raise RuntimeError("ERROR when running get_utt2dur.sh")

    p = subprocess.Popen([tool_dir + "/validate_data_dir.sh", "--no-feats", dirname])
    p.communicate()
    if p.returncode != 0:
        raise RuntimeError("ERROR when running validate_data_dir.sh")
    
    # Report
    # - if some ids were filtered out
    # - if some texts are empty
    # - if there were weird characters in the text
    weird_characters = {}
    with open(os.path.join(dirname, "text"), "r", encoding="utf8") as f:
        ids = [s.split()[0] for s in f.read().splitlines()]
    for id, text in texts.items():
        if id not in ids:
            print("WARNING: Filtered out:", id, text)
        elif not text.strip():
            print("WARNING: Empty text:", id, text)
        else:
            # Filter out usual characters
            if language:
                weirdos = re.sub(r"[a-zA-Z0-9 \.,\?\!\-\'\:\;"+ re.escape(SPECIAL_CHARS.get(language, "")) + r"]", "", text)
            else:
                weirdos = ""
            for c in weirdos:
                if c in weird_characters:continue
                weird_characters[c] = text
    for c, example in weird_characters.items():
        print(f"WARNING: Got character {c} (example: {example})")

    for tmpdir in ".backup", "log", "split4utt":
        tmpdir = os.path.join(dirname, tmpdir)
        if os.path.isdir(tmpdir):
            shutil.rmtree(tmpdir)