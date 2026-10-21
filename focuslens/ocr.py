from .contracts import TextLine


def convert(result):
    texts, scores, polygons = (result[key] for key in ('rec_texts', 'rec_scores', 'rec_polys'))
    if not len(texts) == len(scores) == len(polygons):
        raise ValueError('Inconsistent OCR arrays')
    return [TextLine(str(text), float(score), polygon.tolist() if hasattr(polygon, 'tolist') else polygon)
            for text, score, polygon in zip(texts, scores, polygons)]


def engine():
    from paddleocr import PaddleOCR
    return PaddleOCR(device='cpu', cpu_threads=2, enable_mkldnn=False,
                     text_detection_model_name='PP-OCRv5_mobile_det',
                     text_recognition_model_name='en_PP-OCRv4_mobile_rec',
                     use_doc_orientation_classify=False, use_doc_unwarping=False,
                     use_textline_orientation=False)
