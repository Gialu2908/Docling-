import logging
from typing import Iterable

import numpy

from docling.datamodel.base_models import BoundingBox, CoordOrigin, OcrCell, Page
from docling.datamodel.pipeline_options import TesseractOcrOptions
from docling.models.base_ocr_model import BaseOcrModel

_log = logging.getLogger(__name__)


class TesserOcrModel(BaseOcrModel):
    def __init__(self, enabled: bool, options: TesseractOcrOptions):
        super().__init__(enabled=enabled, options=options)
        self.options: TesseractOcrOptions

        self.scale = 3  # multiplier for 72 dpi == 216 dpi.
        self.reader = None

        if self.enabled:
            try:
                import tesserocr
            except ImportError:
                msg = (
                    "TesserOCR is not installed."
                    "Please install it via `pip install easyocr` to use this OCR engine."
                )
                raise ImportError(msg)

            # Initialize the tesseractAPI
            lang = "+".join(self.options.lang)
            _log.debug("Initializing TesserOCR: %s", tesserocr.tesseract_version())
            self.reader = tesserocr.PyTessBaseAPI(
                lang=lang, psm=tesserocr.PSM.AUTO, init=True, oem=tesserocr.OEM.DEFAULT
            )
            self.reader_RIL = tesserocr.RIL.TEXTLINE

    def __del__(self):
        if self.reader is not None:
            # Finalize the tesseractAPI
            _log.debug("Finalize TesserOCR")
            self.reader.End()

    def __call__(self, page_batch: Iterable[Page]) -> Iterable[Page]:

        if not self.enabled:
            yield from page_batch
            return

        for page in page_batch:
            ocr_rects = self.get_ocr_rects(page)

            all_ocr_cells = []
            for ocr_rect in ocr_rects:
                high_res_image = page._backend.get_page_image(
                    scale=self.scale, cropbox=ocr_rect
                )

                # Retrieve text snippets with their bounding boxes
                self.reader.SetImage(high_res_image)
                boxes = self.reader.GetComponentImages(self.reader_RIL.TEXTLINE, True)

                cells = []
                for ix, (im, box, _, _) in enumerate(boxes):
                    # Set the area of interest. Tesseract uses Bottom-Left for the origin
                    self.reader.SetRectangle(box["x"], box["y"], box["w"], box["h"])

                    # Extract text within the bounding box
                    text = self.reader.GetUTF8Text().strip()
                    confidence = self.reader.MeanTextConf()
                    left = box["x"] / self.scale
                    bottom = box["y"] / self.scale
                    right = (box["x"] + box["w"]) / self.scale
                    top = (box["y"] + box["h"]) / self.scale

                    cells.append(
                        OcrCell(
                            id=ix,
                            text=text,
                            confidence=confidence,
                            bbox=BoundingBox.from_tuple(
                                # l, b, r, t = coord[0], coord[1], coord[2], coord[3]
                                coord=(left, bottom, right, top),
                                origin=CoordOrigin.BOTTOMLEFT,
                            ),
                        )
                    )

                # del high_res_image
                all_ocr_cells.extend(cells)

            ## Remove OCR cells which overlap with programmatic cells.
            filtered_ocr_cells = self.filter_ocr_cells(all_ocr_cells, page.cells)

            page.cells.extend(filtered_ocr_cells)

            # DEBUG code:
            # self.draw_ocr_rects_and_cells(page, ocr_rects)

            yield page