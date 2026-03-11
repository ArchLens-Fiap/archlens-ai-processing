import hashlib
import io

from PIL import Image

MAX_DIMENSION = 2048


def preprocess_image(image_bytes: bytes) -> bytes:
    image = Image.open(io.BytesIO(image_bytes))

    if image.mode == "RGBA":
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(image, mask=image.split()[3])
        image = background
    elif image.mode != "RGB":
        image = image.convert("RGB")

    if max(image.size) > MAX_DIMENSION:
        ratio = MAX_DIMENSION / max(image.size)
        new_size = (int(image.width * ratio), int(image.height * ratio))
        image = image.resize(new_size, Image.LANCZOS)

    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def compute_file_hash(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()


def convert_pdf_to_images(pdf_bytes: bytes) -> list[bytes]:
    try:
        from pdf2image import convert_from_bytes

        images = convert_from_bytes(pdf_bytes, dpi=200, first_page=1, last_page=5)
        result = []
        for img in images:
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            result.append(buffer.getvalue())
        return result
    except ImportError:
        raise RuntimeError("pdf2image requires poppler to be installed")
