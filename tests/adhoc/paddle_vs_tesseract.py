import pytesseract
from paddleocr import PaddleOCR
from PIL import Image

t_text = pytesseract.image_to_string(Image.open("chat_screens/chat_0001.png"))
pocr = PaddleOCR(use_angle_cls=True, lang='en')
paddle_result = pocr.ocr("chat_screens/chat_0001.png", cls=True)
p_text = "\n".join([line[1][0] for line in paddle_result[0]])

print("=== TESSERACT ===")
print(t_text)
print("\n=== PADDLEOCR ===")
print(p_text)
