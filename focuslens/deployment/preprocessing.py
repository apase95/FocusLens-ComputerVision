"""BGR uint8 to normalized NCHW, fixed width feasibility contract.

    PaddleX OCRReisizeNormImg resize_norm_img semantics at a fixed width:
    ceil aspect resize, OpenCV INTER_LINEAR, normalized-zero right padding.
    Unlike its dynamic wrapper, wide inputs are squeezed to width, not expanded.
"""
import math
import numpy as np


def preprocess(bgr, width=320):
    import cv2
    bgr = np.asarray(bgr)
    if (bgr.ndim != 3 or bgr.shape[2] != 3 or min(bgr.shape[:2]) < 1 or
            bgr.dtype != np.uint8 or type(width) is not int or width < 1):
        raise ValueError('Expected nonempty HWC uint8 BGR and positive integer width')
    resized_width = min(width, math.ceil(48 * bgr.shape[1] / bgr.shape[0]))
    image = cv2.resize(bgr, (resized_width, 48)).astype(np.float32)
    image = image.transpose(2, 0, 1) / 255
    image = (image - .5) / .5
    output = np.zeros((1, 3, 48, width), dtype=np.float32)
    output[0, :, :, :resized_width] = image
    return output
