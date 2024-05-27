import json
import re
import os
from linastt.utils.text_utils import (
    cardinal_numbers_to_letters,
    regex_escape,
    symbols_to_letters,
    normalize_arabic_currencies,
    remove_special_characters,
    collapse_whitespace,
    remove_punctuations,
)
from lang_trans.arabic import buckwalter as bw
import string
_regex_arabic_chars = "\u0621-\u063A\u0640-\u064A"
_regex_latin_chars = "a-zA-ZÀ-ÖØ-öø-ÿĀ-ž'"  # Latin characters with common diacritics and '
_arabic_punctuation = "؟!،.؛\"'-_:"
_latin_punctuation = string.punctuation + "。，！？：”、…" + '؟،؛' + '—'
_all_punctuation = "".join(list(set(_latin_punctuation + _arabic_punctuation)))
# Need unescape for regex
_regex_arabic_punctuation = regex_escape(_arabic_punctuation)
_regex_latin_punctuation = regex_escape(_latin_punctuation)
_regex_all_punctuation = regex_escape(_all_punctuation)

script_dir = os.path.dirname(os.path.realpath(__file__))
assets_path = os.path.join(script_dir, "../../assets")

def load_json_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data
    except Exception as err:
        raise RuntimeError(f"Error loading JSON file '{filepath}'") from err

normalization_rules = None

def normalize_chars(text):
    global normalization_rules
    if normalization_rules is None:
        normalization_rules = load_json_file(f'{assets_path}/Arabic_normalization_chars.json')
    regex = re.compile("[" + "".join(map(re.escape, normalization_rules.keys())) + "]")
    text = regex.sub(lambda match: normalization_rules[match.group(0)], text)
    return text

normalization_words = None

def normalize_tunisan_words(text):
    global normalization_words
    if normalization_words is None:
        normalization_words = load_json_file(f'{assets_path}/Tunisian_normalization_words.json')
    for key, value in normalization_words.items():
        text = re.sub(r"\b" + re.escape(key) + r"\b", value, text)
    return text

def bw_transliterate(text):
    return bw.transliterate(text)

arabic_diacritics = re.compile("""
                             ّ    | # Tashdid
                             َ    | # Fatha
                             ً    | # Tanwin Fath
                             ُ    | # Damma
                             ٌ    | # Tanwin Damm
                             ِ    | # Kasra
                             ٍ    | # Tanwin Kasr
                             ْ    | # Sukun
                             ـ     # Tatwil/Kashida
                         """, re.VERBOSE)

def remove_arabic_diacritics(text):
    text = re.sub(arabic_diacritics, '', text)
    return text

def convert_hindi_numbers(text):
    text = text.replace('۰', '0')
    text = text.replace('۱', '1')
    text = text.replace('۲', '2')
    text = text.replace('۳', '3')
    text = text.replace('٤', '4')
    text = text.replace('۵', '5')
    text = text.replace('٦', '6')
    text = text.replace('۶', '6')
    text = text.replace('۷', '7')
    text = text.replace('۸', '8')
    text = text.replace('۹', '9')
    return text

# Convert digit to chars
def digit2word(text, lang):
    text = convert_hindi_numbers(text)
    text = cardinal_numbers_to_letters(text, lang=lang)
    return text

def convert_punct_to_arabic(text):
    text = re.sub(";", "؛", text)
    text = re.sub(",", "،", text)
    return text

def remove_url(text):
    return re.sub('http://\S+|https://\S+', " ", text)

# this function can get only the arabic chars with/without punctuation.
def get_arabic_only(text, keep_punc=False, keep_latin_chars=False):
    what_to_keep = _regex_arabic_chars

    if keep_punc:
        if keep_latin_chars:
            what_to_keep += _regex_all_punctuation + _regex_latin_punctuation
        else:
            what_to_keep += _regex_arabic_punctuation

    if keep_latin_chars:
        what_to_keep += _regex_latin_chars

    return re.sub(r"[^" + what_to_keep + "]+", " ", text)

_regex_not_arabic_neither_punctuation = r"(?![" + _regex_arabic_chars + "])\w"
_regex_arabic = r"[" + _regex_arabic_chars + "]"

def unglue_arabic_and_latin_chars(line):
    line = re.sub(r"(" + _regex_arabic + ")(" + _regex_not_arabic_neither_punctuation + ")", r"\1 \2", line)
    line = re.sub(r"(" + _regex_not_arabic_neither_punctuation + ")(" + _regex_arabic + ")", r"\1 \2", line)
    line = re.sub(" {2,}", " ", line)
    return line

def remove_repeated_ar_chars(word, maximum=2):
    pattern = '(' + _regex_arabic + r')\1{' + str(maximum) + ',}'
    return re.sub(pattern, r'\1' * maximum, word)


def remove_long_words(text, threshold=15):
    return " ".join(word for word in text.split(" ") if len(word) < threshold)

def format_text_ar(line, keep_punc=False, keep_latin_chars=True, bw=False, lang="ar", normalize_dialect_words=False):
    input_line = line
    try:
        if normalize_dialect_words:
            if lang == "ar_tn":
                line = normalize_tunisan_words(line)
            else:
                raise NotImplementedError(f"Normalization of words is not implemented for dialect {lang}")
        line = remove_url(line)
        line = symbols_to_letters(line, lang=lang, lower_case=False)
        line = normalize_arabic_currencies(line, lang=lang)
        line = digit2word(line, lang=lang)
        line = remove_arabic_diacritics(line)
        line = normalize_chars(line)
        line = convert_punct_to_arabic(line)
        line = remove_repeated_ar_chars(line)
        line = remove_long_words(line)
        if not keep_latin_chars:
            line = get_arabic_only(line, keep_punc=keep_punc, keep_latin_chars=keep_latin_chars)
        else:
            line = unglue_arabic_and_latin_chars(line)
            line = get_arabic_only(line, keep_punc=keep_punc, keep_latin_chars=keep_latin_chars)
            line = remove_special_characters(line)
            if not keep_punc:
                line = remove_punctuations(line, " ")
        if bw:
            line = bw_transliterate(line)
    except Exception as err:
        print(f"Error when processing line: \"{input_line}\"")
        raise err
    return collapse_whitespace(line)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('input', help="An input file, or an input string", type=str, nargs="+")
    parser.add_argument('--language', help="Whether to use 'ar or ar_tn'", type=str, default="ar")
    parser.add_argument('--normalize_dialect_words', help="Whether to Normalize Tunisian words", default=False, action="store_true")
    parser.add_argument('--keep_punc', help="Whether to keep punctuations", default=False, action="store_true")
    parser.add_argument('--keep_latin_chars', help="Whether to keep latin characters (otherwise, only arabic characters)", default=False, action="store_true")
    parser.add_argument('--bw', help="Whether to transliterate text into buckwalter encoding.", default=False, action="store_true")
    args = parser.parse_args()

    print(args.normalize_dialect_words)

    if args.language == "tn":
        args.language = "ar_tn"
    
    normalize_dialect_words = args.normalize_dialect_words


    input_data = args.input
    kwargs = {
        "keep_punc": args.keep_punc,
        "keep_latin_chars": args.keep_latin_chars,
        "bw": args.bw,
        "lang": args.language,
        "normalize_dialect_words": normalize_dialect_words,
    }

    if len(input_data) == 1 and os.path.isfile(input_data[0]):
        with open(input_data[0], "r") as f:
            text = f.read()
            for line in text.splitlines():
                print(format_text_ar(line, **kwargs))
    else:
        print(format_text_ar(" ".join(input_data), **kwargs))