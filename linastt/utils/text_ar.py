import re
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

_regex_arabic_chars = "\u0621-\u063A\u0640-\u064A"
_regex_latin_chars = "a-zA-Z" # TODO: improve me
_arabic_punctuation = "؟!،.?,"
_latin_punctuation = "!?.,:;"
_all_punctuation = "".join(list(set(_latin_punctuation + _arabic_punctuation)))
# Need unescape for regex
_regex_arabic_punctuation = regex_escape(_arabic_punctuation)
_regex_latin_punctuation = regex_escape(_latin_punctuation)
_regex_all_punctuation = regex_escape(_all_punctuation)

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
def digit2word(text):
    text = convert_hindi_numbers(text)
    text = cardinal_numbers_to_letters(text, lang="ar")
    return text


def normalize_punct(text):
    text = re.sub("[;؛]",".",text)
    text = re.sub("[:,]","،",text)
    text = re.sub("[-_]","",text)
    return text


def remove_url(text):
    return re.sub('http://\S+|https://\S+', " ", text)


# this function can get only the arabic chars with/without punctuation.
def get_arabic_only(text,keep_punc=False,keep_latin_chars=False):

    what_to_keep = _regex_arabic_chars
    
    if keep_punc:
        if keep_latin_chars:
            what_to_keep += _regex_all_punctuation
        else:
            what_to_keep += _regex_arabic_punctuation
    
    if keep_latin_chars:
        what_to_keep += _regex_latin_chars

    return re.sub(r"[^"+what_to_keep+"]+", " ", text)

_regex_not_arabic_neither_punctuation = r"(?!["+_regex_arabic_chars+"])\w"
_regex_arabic = r"["+_regex_arabic_chars+"]"

def unglue_arabic_and_latin_chars(line):
    line = re.sub(r"("+_regex_arabic+")("+_regex_not_arabic_neither_punctuation+")", r"\1 \2", line)
    line = re.sub(r"("+_regex_not_arabic_neither_punctuation+")("+_regex_arabic+")", r"\1 \2", line)
    line = re.sub(" {2,}", " ", line)
    return line


def format_text_ar(line, keep_punc=False, keep_latin_chars=True, bw=False):
    input_line = line
    try:
        line = remove_url(line)
        line = symbols_to_letters(line, lang="ar", lower_case=False)
        line = normalize_arabic_currencies(line, lang="ar")
        line = digit2word(line)
        line = remove_arabic_diacritics(line)
        line = normalize_punct(line)
        if not keep_latin_chars:
            line = get_arabic_only(line, keep_punc=keep_punc, keep_latin_chars=keep_latin_chars)
        else:
            line = unglue_arabic_and_latin_chars(line)
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

    import os
    import argparse
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('input', help= " An input file, or an input string", type=str, nargs="+")
    parser.add_argument('--keep_punc', help="Whether to keep punctuations", default= False, action="store_true")
    parser.add_argument('--keep_latin_chars', help="Whether to keep latin characters (otherwise, only arabic characters)", default= False, action="store_true")
    parser.add_argument('--bw', help="Whether to transliterate text into buckwalter encoding.", default= False, action="store_true")
    args = parser.parse_args()

    input = args.input
    kwargs = {
        "keep_punc": args.keep_punc,
        "keep_latin_chars": args.keep_latin_chars,
        "bw": args.bw,
    }

    if len(input) == 1 and os.path.isfile(input[0]):
        with open(input[0], "r") as f:
            text = f.read()
            for line in text.splitlines():
                print(format_text_ar(line, **kwargs))
    else:
        print(format_text_ar(" ".join(input), **kwargs))