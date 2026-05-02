import difflib
from textblob import TextBlob

def preprocess(text):
    return str(TextBlob(text).correct())


def get_corrections(original, corrected):
    orig_words = original.split()
    corr_words = corrected.split()

    diff = difflib.ndiff(orig_words, corr_words)

    corrections = []
    wrong_word = None

    for d in diff:
        if d.startswith("- "):
            wrong_word = d[2:]
        elif d.startswith("+ ") and wrong_word:
            corrections.append({
                "wrong": wrong_word,
                "suggestion": d[2:]
            })
            wrong_word = None

    return corrections