"""Explicit REAL inference, not part of offline tests. Writes ignored evidence."""
import json
import os
import time
from pathlib import Path
os.environ.setdefault('PADDLE_PDX_CACHE_HOME', str(Path('.cache/paddlex').resolve()))
from focuslens.translation import Translator
from focuslens.pipeline import Pipeline
from focuslens.imaging import read_image
from focuslens.ocr import engine


def main():
    start = time.monotonic()
    translator = Translator()
    init = time.monotonic() - start
    english = 'What does the man say he will do in July?'
    start = time.monotonic()
    vietnamese = translator.translate(english)
    report = dict(sentence=dict(english=english, vietnamese=vietnamese,
                               seconds=time.monotonic() - start), translator_init_seconds=init)
    start = time.monotonic()
    pipeline = Pipeline(engine(), translator)
    report['ocr_init_seconds'] = time.monotonic() - start
    report['image'] = 'samples/ov3660/crops/59.png'
    report['pipeline'] = pipeline.process(read_image(report['image']))
    Path('results').mkdir(exist_ok=True)
    Path('results/translation-smoke.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
