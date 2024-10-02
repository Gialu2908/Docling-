import logging
from subprocess import PIPE, Popen
from typing import Iterable, Tuple

import pandas as pd

from docling.datamodel.base_models import BoundingBox, CoordOrigin, OcrCell, Page
from docling.datamodel.pipeline_options import TesseractOcrOptions
from docling.models.base_ocr_model import BaseOcrModel

_log = logging.getLogger(__name__)

class TesseractOcrModel(BaseOcrModel):

    def __init__(self, enabled: bool, options: TesseractOcrOptions):
        super().__init__(enabled=enabled, options=options)
        self.options: TesseractOcrOptions

        self.scale = 3  # multiplier for 72 dpi == 216 dpi.

        if self.enabled:
            try:
                self._get_name_and_version()

            except Exception as exc:
                _log.error(f"Tesseract is not available, aborting ...")
                self.enabled = False

    def _get_name_and_version(self) -> Tuple[str, str]:

        if self._name != None and self._version != None:
            return self._name, self._version

        cmd = ["tesseract", "--version"]

        proc = Popen(cmd, stdout=PIPE, stderr=PIPE)
        stdout, stderr = proc.communicate()

        proc.wait()

        # HACK: Windows versions of Tesseract output the version to stdout, Linux versions
        # to stderr, so check both.
        version_line = (
            (stdout.decode("utf8").strip() or stderr.decode("utf8").strip())
            .split("\n")[0]
            .strip()
        )

        # If everything else fails...
        if not version_line:
            version_line = "tesseract XXX"

        name, version = version_line.split(" ")

        self._name = name
        self._version = version

        return name, version

    def _run_tesseract(self, ifilename, languages=None):

        cmd = ["tesseract"]

        if languages:
            cmd += ["-l", "+".join(languages)]

        cmd += [ifilename, "stdout", "tsv"]
        _log.info("command: {}".format(" ".join(cmd)))

        proc = Popen(cmd, stdout=PIPE)
        output, _ = proc.communicate()

        # Read the TSV file generated by Tesseract
        df = pd.read_csv("output_file_name.tsv", sep="\t")

        # Display the dataframe (optional)
        print(df.head())

        # Filter rows that contain actual text (ignore header or empty rows)
        df_filtered = df[df["text"].notnull() & (df["text"].str.strip() != "")]

        return df_filtered

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
                print(high_res_image)

                # FIXME: do we really need to save the image to a file
                fname = "temporary-file.png"
                high_res_image.save(fname)

                if os.path.exists(fname):
                    df = self._run_tesseract(fname)
                    os.remove(fname)
                else:
                    _log.error(f"no image file: {fname}")

                # Print relevant columns (bounding box and text)
                for index, row in df_filtered.iterrows():
                    print(row)

                    text = row["text"]
                    conf = row["confidence"]

                    l = float(row["left"])
                    t = float(row["top"])
                    w = float(row["width"])
                    h = float(row["height"])

                    b = t - h
                    r = l + w

                    cell = OcrCell(
                        id=ix,
                        text=text,
                        confidence=line[2],
                        bbox=BoundingBox.from_tuple(
                            coord=(
                                (l / self.scale) + ocr_rect.l,
                                (b / self.scale) + ocr_rect.t,
                                (r / self.scale) + ocr_rect.l,
                                (t / self.scale) + ocr_rect.t,
                            ),
                            origin=CoordOrigin.TOPLEFT,
                        ),
                    )
                    all_ocr_cells.append(cell)

            ## Remove OCR cells which overlap with programmatic cells.
            filtered_ocr_cells = self.filter_ocr_cells(all_ocr_cells, page.cells)

            page.cells.extend(filtered_ocr_cells)

            # DEBUG code:
            self.draw_ocr_rects_and_cells(page, ocr_rects)

            yield page
