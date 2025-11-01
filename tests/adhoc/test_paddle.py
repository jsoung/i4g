from paddleocr import PaddleOCR

ocr = PaddleOCR(
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
)  # text detection + text recognition
# ocr = PaddleOCR(use_doc_orientation_classify=True, use_doc_unwarping=True) # text image preprocessing + text detection + textline orientation classification + text recognition
# ocr = PaddleOCR(use_doc_orientation_classify=False, use_doc_unwarping=False) # text detection + textline orientation classification + text recognition
# ocr = PaddleOCR(
#     text_detection_model_name="PP-OCRv5_mobile_det",
#     text_recognition_model_name="PP-OCRv5_mobile_rec",
#     use_doc_orientation_classify=False,
#     use_doc_unwarping=False,
#     use_textline_orientation=False) # Switch to PP-OCRv5_mobile models
result = ocr.predict("./adhoc/data/simple_text.png")
for res in result:
    res.print()
    res.save_to_img("output")
    res.save_to_json("output")
