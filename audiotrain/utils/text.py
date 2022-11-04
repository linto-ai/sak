import re
from num2words import num2words
import unicodedata

_whitespace_re = re.compile(r'[^\S\r\n]+')

def collapse_whitespace(text):
    return re.sub(_whitespace_re, ' ', text).strip()

def transliterate(c):
    # Transliterates a character to its closest ASCII equivalent.
    # For example, "é" becomes "e".
    # This is useful for converting Vietnamese text to ASCII.
    # See https://stackoverflow.com/a/517974/446579
    return unicodedata.normalize("NFKD", c).encode("ascii", "ignore").decode("ascii")


def remove_special_words(text,
    glue_apostrophe = True,
    extra = True,
    ):
    """
    Small process designed for text that has ALREADY been processed (ex: "8" -> "huit"), but some special words might still be present (ex: "<noise>")
    """
    # sometimes empty text could have been transformed to None (ex: in CSV)
    if not text: return ""

    try:
        text = re.sub(r"<.*?>", "", text)
    except:
        print("PROBLEM WITH TEXT:", text, type(text))
        text = re.sub(r"<.*?>", "", text)
    
    if glue_apostrophe:
        text = re.sub(r"'[^\S\r\n]+", "'", text)
    else:
        text = re.sub(r"'", "' ", text).strip()

    if extra:
        text = re.sub(r"\" ", " ", text)
        text = re.sub(r":", " ", text)
        text = re.sub(r"\+", " plus ", text)
        text = re.sub(r"1", " un ", text)
        text = re.sub(r"2", " deux ", text)
        text = re.sub(r"3", " trois ", text)
        text = re.sub(r"4", " quatre ", text)
        text = re.sub(r"5", " cinq ", text)
        text = re.sub(r"6", " six ", text)
        text = re.sub(r"7", " sept ", text)
        text = re.sub(r"8", " huit ", text)
        text = re.sub(r"9", " neuf ", text)

    text = collapse_whitespace(text)

    text = text.lower() # TCOF
    return text

def format_text_fr(text, keep_punc = False):
    
    if isinstance(text, list):
        return [format_text_fr(t) for t in text]
    
    if "\n" in text:
        return "\n".join([format_text_fr(t, keep_punc) for t in text.split("\n")])
   
    text = text.lower()
    for reg, replacement in _corrections_caracteres_speciaux_fr:
        text = re.sub(reg, replacement, text)

    text = ' '+text+' '

    numbers=re.findall("\d+,000",text)
    for n in numbers:
        text = re.sub(n,re.sub(",","",n), text)


    # Replace "." by "point" and "/" by "slash" in internet websites
    # Find all the websites in the text
    websites = [w for w in re.findall('(?:(?:https?|ftp):\/\/)?[\w/\-?=%.]+\.[\w/\-&?=%.]+', text) if ".." not in w]
    websites = sorted(set(websites), key = len, reverse = True)
    for w in websites:
        w2 = w
        w2 = re.sub("\.", " point ", w2)
        w2 = re.sub(":", " deux points ", w2)
        w2 = re.sub("/", " slash ", w2)
        w2 = re.sub("-", " tiret ", w2)
        #text = re.sub(w, w2, text)
        text = text.replace(w, w2)

    # Abbréviations
    text = re.sub(" m\. "," monsieur ",text)
    text = re.sub(" mme\.? ", " madame ",text)
    text = re.sub(" mlle\.? ", " mademoiselle ",text)


    text = re.sub(r"[’‘]","'", text)
    text = re.sub("'","' ", text)
    text = re.sub('"',' " ', text)
    text = re.sub("' '", "''", text)
    text = re.sub(":", " : ", text)
    text = re.sub(";", " ; ", text)
    text = re.sub(',|¸',',', text)
    text = re.sub(", ", " , ", text)
    text = re.sub("\!", " ! ", text)
    text = re.sub("\?", " ? ", text)
    text = re.sub("^ *-+", "", text)
    text = re.sub("\^+","", text)
    text = re.sub(" +(- +)+", " ", text)
    text = re.sub("- ", "-", text)
    text = re.sub("([a-zàâäçèéêëîïôùûü]+)- +", r"\1-", text)
    text = re.sub(" -([a-zàâäçèéêëîïôùûü]+)", r"-\1", text)
    text = re.sub("([,;:\!\?\.]) -([a-zàâäçèéêëîïôùûü]+)", r"\1 \2", text)
    text = re.sub("([a-zàâäçèéêëîïôùûü]{3,})' ", r"\1 ", text)
    text = re.sub("([a-zàâäçèéêëîïôùûü]{2,})' *[,;:\!\?\.]", r"\1 ", text)
    text = re.sub('\.{2,}',' ', text)
    text = re.sub('\. *$',' . ', text)
    text = re.sub('(\d)\. ',r'\1 . ', text)
    
    text=re.sub('\{',' { ',text)
    text=re.sub('\}',' } ',text)
    text=re.sub('\(',' ( ',text)
    text=re.sub('\)',' ) ',text)
    text=re.sub('\[',' [ ',text)
    text=re.sub('\]',' ] ',text)
    text=re.sub(r"<([^<>]*)>",r"\1",text)

    for reg, replacement in _corrections_regex_fr:
        text = re.sub(reg, replacement, text)

    heures=re.findall("\d+ *h *\d+",text)
    for h in heures:
        split_h=h.split('h')
        text_rep=re.sub('^0+','',split_h[0])+' heures '+re.sub('^0+','',split_h[1])
        #text_rep=split_h[0]+' heures '+split_h[1]
        text=text.replace(h, text_rep)

    text = re.sub("(\d+)''",r"\1 secondes ",text)
    text = re.sub("(\d+)'",r"\1 minutes ",text)
    #text = re.sub("(\d+)°",r"\1 degrés ",text)

    chiffres = re.findall(r"\b1(?:ère|ere|er|re|r)|2(?:nd|nde)|\d+(?:ème|eme|e)\b", text)
    chiffres = sorted(list(set(chiffres)), reverse=True, key=len)    
    for chiffre in chiffres:
        word = undigit_fr(re.findall(r"\d+", chiffre)[0], to= "ordinal")
        text = re.sub(r'\b'+str(chiffre)+r'\b', word, text)

    text = re.sub(r"\b(\d+),(\d+)",r"\1 virgule \2", text)
    text = re.sub(r"\b(\d+)\.(\d+)\b",r"\1 point \2", text)
    text = re.sub(r'([a-z])2([a-z])', r'\1 to \2', text) # wav2vec -> wav to vec
    text = re.sub(r'(\d)-', r'\1 ', text) # For things like 40-MFCC
    text = re.sub(r"(\d+)([^\d])",r" \1 \2", text) # add spaces before and after digits

    # Digits
    chiffres = re.findall(r"\b\d[ /\d]*\b",text)
    chiffres = list(map(lambda s: s.strip(r"[/ ]"), chiffres))
    chiffres = sorted(list(set(chiffres)), reverse=True, key=len)    
    for chiffre in chiffres:
        numslash = len(re.findall("/", chiffre))
        if numslash == 0:
            word = undigit_fr(chiffre)
        elif numslash == 1:
            i = chiffre.index("/")
            first = undigit_fr(chiffre[:i])
            second = undigit_fr(chiffre[i+1:], to="denominator")
            if float(chiffre[:i]) > 2. and second[-1] != "s":
                second += "s"
            word = first + " " + second
        else:
            word = "/".join([undigit_fr(s) for s in chiffre.split('/')])
        text = re.sub(r'\b'+str(chiffre)+r'\b', word, text)

    # Fractions
    text = re.sub(r"½", " un demi ", text)
    text = re.sub(r"⅓", " un tiers ", text)
    text = re.sub(r"⅔", " deux tiers ", text)
    text = re.sub(r"¼", " un quart ", text)
    text = re.sub(r"¾", " trois quarts ", text)
    # Exponents
    text = re.sub(r"\bm²", " mètres carrés ", text)
    text = re.sub(r"\bm³", " mètres cubes ", text)
    text = re.sub(r"²", " carrés ", text)
    text = re.sub(r"³", " cubes ", text)

    text = re.sub(r"°c\b", "degrés", text)
    text = re.sub("°", "degrés", text)
    text = re.sub("&"," et ", text)
    text = re.sub('%', ' pour cent ', text)
    text = re.sub('€', ' euros ', text)
    text = re.sub('\$', ' dollars ', text)
    text = re.sub("~"," environ ", text)

    text = re.sub(" '", " ", text)
    text = re.sub('--+',' ', text)
    text = re.sub('_',' ', text)
    text = re.sub('–',' ', text)
    text = re.sub('—+',' ', text)
    text = re.sub('…','...', text)
    text = re.sub('\*+', ' ', text)
    text = re.sub(r"[«“][^\S\r\n]*", '"', text)
    text = re.sub(r"[^\S\r\n]*[»”]", '"', text)
    text = re.sub(r"[’‘]", "'", text)
    text = re.sub(r"–", "-", text)
    text = re.sub('#+',' ', text)
    text = re.sub(" "," ",text)
    text = re.sub(' ', '  ',text)

    text = re.sub('\{|\}|\(|\)|\[|\]|"|=',' ',text)
    text = re.sub('(\.|\?|\!|,|;|:)-',r'\1 ', text)

    for reg, replacement in _corrections_abbreviations_fr:
        text = re.sub(reg, replacement, text)

    if not keep_punc:
        text = re.sub(r',|;|:|\!|\?|/|\.',' ',text)

    text = re.sub(' - | -$|^- ','', text)
    text = collapse_whitespace(text)

    return text

def undigit_fr(str, to="cardinal"):
    str = re.sub(" ","", str)
    if to == "denominator":
        if str == "2": return "demi"
        if str == "3": return "tiers"
        if str == "4": return "quart"
        to = "ordinal"
    return num2words(float(str), lang='fr', to=to)

_corrections_abbreviations_fr = [(r' '+x[0]+r' ', ' '+x[1]+' ') for x in [
    ("g", "grammes"),
    ("μg", "microgrammes"),
    ("mg", "milligrammes"),
    ("kg", "kilogrammes"),
    ("mm", "millimètres"),
    ("cm", "centimètres"),
    # ("l", "litres"), # Caution with "l'"
    ("ml", "millilitres"),
    ("cm2", "centimètres carrés")
]] + [
    ("\+", "plus"),
    ("ᵉʳ", "er"),
    ("ᵉ", "eme"),
    ("@", " arobase ")
]

_corrections_caracteres_speciaux_fr = [(re.compile('%s' % x[0], re.IGNORECASE), '%s' % x[1])
                  for x in [
                    (" ", " "),
                    ("â","â"),
                    ("à","à"),
                    ("á","á"),
                    ("ã","à"),
                    ("ê","ê"),
                    ("é","é"),
                    ("è","è"),
                    ("ô","ô"),
                    ("û","û"),
                    ("î","î"),
                    ("Ã","à"),
                    # ('À','à'),
                    # ('É','é'),
                    # ('È','è'),
                    # ('Â','â'),
                    # ('Ê','ê'),
                    # ('Ç','ç'),
                    # ('Ù','ù'),
                    # ('Û','û'),
                    # ('Î','î'),
                    ("œ","oe"),
                    ("æ","ae")
                ]]

_corrections_regex_fr = [(re.compile(' %s ' % x[0], re.IGNORECASE), ' %s ' % x[1])
                  for x in [
                    ("nº","numéro"),
                    ("n°","numéro"),
                    ("mp3","m p 3"),
                    ("jus +qu'","jusqu'"),
                    ("pres +qu'","presqu'"),
                    ("lors +qu'","lorsqu'"),
                    ("quel +qu'","quelqu'"),
                    ("puis +qu'","puisqu'"),
                    ("aujour +d'","aujourd'"),
                    ("jusqu","jusqu'"),
                    ("presqu","presqu'"),
                    ("lorsqu","lorsqu'"),
                    ("quelqu","quelqu'"),
                    ("puisqu","puisqu'"),
                    ("aujourd","aujourd'"),
                    ("aujourd' +hui","aujourd'hui"),
                    ("quoiqu","quoiqu'"),
                    ("°", " degrés "),
                ]]

if __name__ == "__main__":

    import sys
    print(format_text_fr(" ".join(sys.argv[1:])))