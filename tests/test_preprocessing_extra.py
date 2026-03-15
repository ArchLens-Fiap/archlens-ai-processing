import io
from unittest.mock import patch, MagicMock

import pytest
from PIL import Image

from app.domain.preprocessing import preprocess_image, convert_pdf_to_images


class TestPreprocessImageModes:
    def test_grayscale_l_mode_converted_to_rgb(self):
        img = Image.new("L", (100, 100), color=128)
        buf = io.BytesIO()
        img.save(buf, format="PNG")

        result = preprocess_image(buf.getvalue())
        out = Image.open(io.BytesIO(result))
        assert out.mode == "RGB"

    def test_palette_p_mode_converted_to_rgb(self):
        img = Image.new("P", (50, 50))
        buf = io.BytesIO()
        img.save(buf, format="PNG")

        result = preprocess_image(buf.getvalue())
        out = Image.open(io.BytesIO(result))
        assert out.mode == "RGB"


class TestConvertPdfToImages:
    def test_convert_pdf_returns_list_of_bytes(self):
        img = Image.new("RGB", (100, 100), color="red")
        mock_convert = MagicMock(return_value=[img, img])

        with patch.dict("sys.modules", {"pdf2image": MagicMock(convert_from_bytes=mock_convert)}):
            # Need to reload to pick up the mock
            import importlib
            from app.domain import preprocessing
            importlib.reload(preprocessing)
            result = preprocessing.convert_pdf_to_images(b"fake-pdf")
            assert len(result) == 2
            for r in result:
                assert isinstance(r, bytes)

            # Restore
            importlib.reload(preprocessing)

    def test_convert_pdf_empty_result(self):
        mock_convert = MagicMock(return_value=[])

        with patch.dict("sys.modules", {"pdf2image": MagicMock(convert_from_bytes=mock_convert)}):
            import importlib
            from app.domain import preprocessing
            importlib.reload(preprocessing)
            result = preprocessing.convert_pdf_to_images(b"empty-pdf")
            assert result == []
            importlib.reload(preprocessing)

    def test_convert_pdf_missing_poppler_raises(self):
        with patch.dict("sys.modules", {"pdf2image": None}):
            import importlib
            from app.domain import preprocessing
            importlib.reload(preprocessing)
            with pytest.raises(RuntimeError, match="poppler"):
                preprocessing.convert_pdf_to_images(b"data")
            importlib.reload(preprocessing)
