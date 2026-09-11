from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def relevance_scores(query: str, documents: list[str]) -> list[float]:
    """Score each document's TF-IDF cosine similarity against a query string.

    Returns one float per document, same order as `documents`. Documents that
    are empty/whitespace score 0.0 without affecting the vectorizer's vocabulary.
    """
    if not documents:
        return []

    non_empty = [(i, d) for i, d in enumerate(documents) if d and d.strip()]
    scores = [0.0] * len(documents)
    if not non_empty:
        return scores

    corpus = [query] + [d for _, d in non_empty]
    vectorizer = TfidfVectorizer(stop_words="english")
    matrix = vectorizer.fit_transform(corpus)
    query_vec = matrix[0:1]
    doc_vecs = matrix[1:]
    sims = cosine_similarity(query_vec, doc_vecs)[0]

    for (original_index, _), sim in zip(non_empty, sims):
        scores[original_index] = float(sim)
    return scores
