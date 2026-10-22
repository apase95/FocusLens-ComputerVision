"""Greedy CTC on NTC raw output; no softmax or confidence calibration."""
import numpy as np


def greedy_decode(scores, characters):
    """Blank is index zero. Confidence averages first retained timestep scores.

    Accepts logits or probabilities, but logits' mean is NOT a probability.
    Blank separates repeated characters; empty output has confidence zero.
    """
    scores = np.asarray(scores)
    if (scores.ndim != 3 or scores.shape[-1] != len(characters) or
            len(characters) < 2 or not np.isfinite(scores).all()):
        raise ValueError('Expected finite NTC scores matching blank-prefixed charset')
    result = []
    for row in scores:
        ids = row.argmax(axis=-1)
        keep = np.ones(len(ids), dtype=bool)
        keep[1:] = ids[1:] != ids[:-1]
        keep &= ids != 0
        result.append((''.join(characters[i] for i in ids[keep]),
                       float(row.max(axis=-1)[keep].mean()) if keep.any() else 0.))
    return result


def load_characters(path):
    import yaml
    config = yaml.safe_load(path.read_text())
    post = config['PostProcess']
    if post['name'] != 'CTCLabelDecode':
        raise ValueError('Expected official CTC decoder')
    return ('', *post['character_dict'], ' ')
