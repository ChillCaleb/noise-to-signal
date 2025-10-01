from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

_analyzer = SentimentIntensityAnalyzer()

def sentiment_scores(text: str) -> dict:
    """
    Returns {'neg','neu','pos','compound'}; compound in [-1,1].
    """
    return _analyzer.polarity_scores(text)

def label_from_compound(compound: float) -> str:
    if compound >= 0.5:  return "strong_positive"
    if compound >= 0.2:  return "positive"
    if compound <= -0.5: return "strong_negative"
    if compound <= -0.2: return "negative"
    return "neutral"
