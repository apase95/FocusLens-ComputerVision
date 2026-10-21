"""Local OPUS Marian model; imports lazy, no implicit downloads."""
from pathlib import Path
import re


def source_tokens(text, sp, normalizer):
    return ['>>vie<<'] + sp.encode(normalizer.normalize(text), out_type=str) + ['</s>']


class Translator:
    def __init__(self, root=Path('models/opus-en-vi')):
        root = Path(root)
        if not all((root / name).is_file() for name in ('ct2/model.bin', 'source.spm', 'target.spm')):
            raise RuntimeError('Missing translation model; run .venv/bin/python prepare_translation.py')
        import ctranslate2
        import sentencepiece as spm
        from sacremoses import MosesPunctNormalizer
        self.normalizer = MosesPunctNormalizer(lang='en')
        self.source = spm.SentencePieceProcessor(model_file=str(root / 'source.spm'))
        self.target = spm.SentencePieceProcessor(model_file=str(root / 'target.spm'))
        self.model = ctranslate2.Translator(str(root / 'ct2'), device='cpu', compute_type='int8',
                                           inter_threads=1, intra_threads=2)

    def translate(self, text):
        if not text.strip():
            return ''
        # Join OCR wraps first, then sentence units; never translate box-by-box.
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        sources = [source_tokens(sentence, self.source, self.normalizer) for sentence in sentences]
        if any(len(tokens) > 500 for tokens in sources):
            raise ValueError('Sentence exceeds 500 model tokens; split the document explicitly')
        results = self.model.translate_batch(sources, beam_size=4, max_decoding_length=512)
        if any(len(result.hypotheses[0]) >= 512 for result in results):
            raise ValueError('Translation reached output limit; no silently truncated result returned')
        return ' '.join(self.target.decode([t for t in result.hypotheses[0]
                                           if t not in ('</s>', '>>vie<<')]) for result in results)
