import re
import difflib
import threading

MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_SIZE = 384
SEMANTIC_THRESHOLD = 0.40
NEAR_EXACT_THRESHOLD = 0.85
DISPLAY_MIN_SCORE = 0.40


def _cuda_available():
    try:
        import torch  # noqa: F401
        import torch.cuda  # noqa: F401
        return bool(torch.cuda.is_available())
    except Exception:
        return False


def _normalize(text):
    text = (text or '').lower()
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def extract_sentences(text):
    text = re.sub(r'\s+', ' ', text or '').strip()
    if not text:
        return []
    # Protect common abbreviations so they don't split sentences.
    protected = re.sub(
        r'\b(Mr|Mrs|Ms|Dr|Prof|Sr|Jr|Inc|Ltd|Co|U\.S|U\.K|e\.g|i\.e|etc|vs|no|p|pp|vol|fig|et\.al)\.',
        r'\1<DOT>',
        text,
        flags=re.I,
    )
    raw = re.split(r'(?<=[.!?])\s+(?=[A-Z0-9"\'\u201c])', protected)
    sentences = []
    for part in raw:
        part = part.replace('<DOT>', '.').strip()
        if len(part) >= 3:
            sentences.append(part)
    if not sentences and text:
        sentences = [text]
    return sentences


def extract_paragraphs(text):
    text = re.sub(r'[ \t]+', ' ', text or '')
    return [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]


def _exact_match(a, b):
    na, nb = _normalize(a), _normalize(b)
    return bool(na) and na == nb


def _near_exact_match(a, b):
    na, nb = _normalize(a), _normalize(b)
    if not na or not nb or na == nb:
        return False
    return difflib.SequenceMatcher(None, na, nb).ratio() >= NEAR_EXACT_THRESHOLD


def _label(score01):
    if score01 >= 0.70:
        return 'HIGH SIMILARITY'
    if score01 >= 0.50:
        return 'MODERATE SIMILARITY'
    return 'LOW SIMILARITY'


class SimilarityEngine:
    def __init__(self):
        # GPU support: CUDA when available, otherwise CPU.
        self.device = 'cuda' if _cuda_available() else 'cpu'
        self.model = None
        self._lock = threading.Lock()
        self._attempted = False
        self._loaded = False
        self._tfidf_lock = threading.Lock()
        # Load the embedding model in the background so requests never block.
        # Falls back to TF-IDF when the model hub is unreachable.
        threading.Thread(target=self._background_load, daemon=True).start()

    def _background_load(self):
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(MODEL_NAME, device=self.device)
        except Exception:
            self.model = None
        finally:
            with self._lock:
                self._attempted = True
                self._loaded = True

    def load_model(self):
        """Return the embedding model if loaded, else None (never blocks).

        GPU device selection is preserved: when CUDA is available the model
        runs on the GPU. When the model hub is unreachable, self.model stays
        None and the TF-IDF cosine similarity is used instead.
        """
        with self._lock:
            return self.model

    def _semantic_matrix(self, sentences_a, sentences_b):
        model = self.load_model()
        if model is not None:
            from sentence_transformers import util
            import torch
            emb_a = model.encode(
                sentences_a, convert_to_tensor=True, device=self.device,
                show_progress_bar=False,
            )
            emb_b = model.encode(
                sentences_b, convert_to_tensor=True, device=self.device,
                show_progress_bar=False,
            )
            sim = util.cos_sim(emb_a, emb_b)
            return sim.cpu().numpy()

        # Offline fallback: blended TF-IDF cosine (word + character n-grams).
        # Keeps results meaningful when the sentence-transformer model hub is
        # unreachable (e.g. restricted sandbox egress).
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        combined = list(sentences_a) + list(sentences_b)
        n_a = len(sentences_a)
        wmat = TfidfVectorizer(analyzer='word', ngram_range=(1, 2), min_df=1).fit_transform(combined)
        cmat = TfidfVectorizer(analyzer='char', ngram_range=(3, 5), min_df=1).fit_transform(combined)
        mw = cosine_similarity(wmat[:n_a], wmat[n_a:])
        mc = cosine_similarity(cmat[:n_a], cmat[n_a:])
        return 0.6 * mw + 0.4 * mc

    def _paragraph_similarity(self, text_a, text_b):
        paragraphs_a = extract_paragraphs(text_a)
        paragraphs_b = extract_paragraphs(text_b)
        if not paragraphs_a or not paragraphs_b:
            return {'score': 0, 'label': _label(0), 'count': 0}
        sim = self._semantic_matrix(paragraphs_a, paragraphs_b)
        best = [float(sim[i].max()) for i in range(len(paragraphs_a))]
        score = round(sum(best) / len(best) * 100, 1)
        return {'score': score, 'label': _label(score / 100.0), 'count': len(paragraphs_a)}

    def _detect_passages(self, matched_pairs, sim):
        """Group consecutive matched sentence pairs into detected passages."""
        pairs = sorted(matched_pairs, key=lambda p: p[0])
        runs = []
        run = []
        for i, j in pairs:
            if run and i == run[-1][0] + 1 and j == run[-1][1] + 1:
                run.append((i, j))
            else:
                if len(run) >= 2:
                    runs.append(run)
                run = [(i, j)]
        if len(run) >= 2:
            runs.append(run)

        passages = []
        for run in runs:
            scores = [float(sim[i][j]) for i, j in run]
            passages.append({
                'sentences': len(run),
                'similarity': round(sum(scores) / len(scores) * 100, 1),
                'index_a_start': run[0][0],
                'index_b_start': run[0][1],
            })
        return passages

    def analyze(self, text_a, text_b):
        sentences_a = extract_sentences(text_a)
        sentences_b = extract_sentences(text_b)

        empty = {
            'similarity_score': 0,
            'label': _label(0),
            'explanation': 'No comparable sentences found.',
            'counts': {'exact': 0, 'near_exact': 0, 'semantic': 0},
            'matches': [],
            'coverage': {'a': 0, 'b': 0},
            'passages': [],
            'paragraph_similarity': {'score': 0, 'label': _label(0), 'count': 0},
            'sentences_a': [],
            'sentences_b': [],
            'technical': {
                'model': MODEL_NAME,
                'embedding_size': EMBEDDING_SIZE,
                'device': self.device,
                'cosine_similarity': True,
                'semantic_threshold': SEMANTIC_THRESHOLD,
                'lexical_evidence': True,
                'model_loaded': self.model is not None,
            },
        }
        if not sentences_a or not sentences_b:
            return empty

        sim = self._semantic_matrix(sentences_a, sentences_b)

        # Best match for every sentence in Document A.
        best_per_a = []
        for i in range(len(sentences_a)):
            j = int(sim[i].argmax())
            best_per_a.append((i, j, float(sim[i][j])))

        matches = []
        matched_pairs = []
        used_b = set()
        for i, j, score in best_per_a:
            if score < DISPLAY_MIN_SCORE:
                continue
            if j in used_b:
                continue
            sa, sb = sentences_a[i], sentences_b[j]
            if _exact_match(sa, sb):
                mtype = 'exact'
            elif _near_exact_match(sa, sb):
                mtype = 'near_exact'
            elif score >= SEMANTIC_THRESHOLD:
                mtype = 'semantic'
            else:
                continue
            used_b.add(j)
            matched_pairs.append((i, j))
            matches.append({
                'id': len(matches) + 1,
                'sentence_a': sa,
                'sentence_b': sb,
                'index_a': i,
                'index_b': j,
                'score': round(score * 100, 1),
                'label': _label(score),
                'type': mtype,
            })

        matches.sort(key=lambda m: m['score'], reverse=True)
        for idx, m in enumerate(matches, 1):
            m['id'] = idx

        counts = {'exact': 0, 'near_exact': 0, 'semantic': 0}
        for m in matches:
            counts[m['type']] += 1

        matched_a = {m['index_a'] for m in matches}
        matched_b = {m['index_b'] for m in matches}
        coverage_a = round(len(matched_a) / len(sentences_a) * 100, 1)
        coverage_b = round(len(matched_b) / len(sentences_b) * 100, 1)

        overall = round(
            sum(float(sim[i].max()) for i in range(len(sentences_a)))
            / len(sentences_a) * 100, 1,
        )

        matched_count = sum(1 for m in matches if m['type'] == 'semantic')
        explanation = (
            f"{matched_count} of {len(sentences_a)} comparable sentences "
            "have meaningful overlap."
        )

        return {
            'similarity_score': overall,
            'label': _label(overall / 100.0),
            'explanation': explanation,
            'counts': counts,
            'matches': matches,
            'coverage': {'a': coverage_a, 'b': coverage_b},
            'passages': self._detect_passages(matched_pairs, sim),
            'paragraph_similarity': self._paragraph_similarity(text_a, text_b),
            'sentences_a': sentences_a,
            'sentences_b': sentences_b,
            'technical': {
                'model': MODEL_NAME,
                'embedding_size': EMBEDDING_SIZE,
                'device': self.device,
                'cosine_similarity': True,
                'semantic_threshold': SEMANTIC_THRESHOLD,
                'lexical_evidence': True,
                'model_loaded': self.model is not None,
            },
        }
