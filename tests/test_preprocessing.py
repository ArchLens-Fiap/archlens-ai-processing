import io

from PIL import Image

from app.domain.preprocessing import compute_file_hash, preprocess_image


class TestPreprocessImage:
    def test_small_image_unchanged_dimensions(self, sample_image_bytes):
        result = preprocess_image(sample_image_bytes)
        img = Image.open(io.BytesIO(result))
        assert img.size == (100, 100)
        assert img.mode == "RGB"

    def test_large_image_resized(self, large_image_bytes):
        result = preprocess_image(large_image_bytes)
        img = Image.open(io.BytesIO(result))
        assert max(img.size) <= 2048

    def test_rgba_converted_to_rgb(self, rgba_image_bytes):
        result = preprocess_image(rgba_image_bytes)
        img = Image.open(io.BytesIO(result))
        assert img.mode == "RGB"

    def test_output_is_png(self, sample_image_bytes):
        result = preprocess_image(sample_image_bytes)
        img = Image.open(io.BytesIO(result))
        assert img.format == "PNG"


class TestComputeFileHash:
    def test_deterministic(self):
        data = b"test content"
        assert compute_file_hash(data) == compute_file_hash(data)

    def test_different_content_different_hash(self):
        assert compute_file_hash(b"a") != compute_file_hash(b"b")

    def test_hash_is_sha256_hex(self):
        h = compute_file_hash(b"test")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)
