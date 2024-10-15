import json
import logging
import time
from pathlib import Path
from typing import Iterable

from docling.datamodel.base_models import ConversionStatus, InputFormat
from docling.datamodel.document import ConversionResult
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions,
    TesseractCliOcrOptions,
    TesseractOcrOptions,
)
from docling.document_converter import DocumentConverter, FormatOption, PdfFormatOption
from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline

_log = logging.getLogger(__name__)


def main():
    logging.basicConfig(level=logging.INFO)

    input_doc_path = Path("./tests/data/2206.01062.pdf")

    ###########################################################################

    # The following sections contain a combination of PipelineOptions
    # and PDF Backends for various configurations.
    # Uncomment one section at the time to see the differences in the output.

    # PyPdfium without EasyOCR
    # --------------------
    # pipeline_options = PipelineOptions()
    # pipeline_options.do_ocr=False
    # pipeline_options.do_table_structure=True
    # pipeline_options.table_structure_options.do_cell_matching = False

    # doc_converter = DocumentConverter(
    #     pipeline_options=pipeline_options,
    #     pdf_backend=PyPdfiumDocumentBackend,
    # )

    # PyPdfium with EasyOCR
    # -----------------
    # pipeline_options = PipelineOptions()
    # pipeline_options.do_ocr=True
    # pipeline_options.do_table_structure=True
    # pipeline_options.table_structure_options.do_cell_matching = True

    # doc_converter = DocumentConverter(
    #     pipeline_options=pipeline_options,
    #     pdf_backend=PyPdfiumDocumentBackend,
    # )

    # Docling Parse without EasyOCR
    # -------------------------
    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = False
    pipeline_options.do_table_structure = True
    pipeline_options.table_structure_options.do_cell_matching = True
    pipeline_options.do_dummy_picture_classifer = True

    doc_converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
        }
    )

    # Docling Parse with EasyOCR
    # ----------------------
    # pipeline_options = PipelineOptions()
    # pipeline_options.do_ocr=True
    # pipeline_options.do_table_structure=True
    # pipeline_options.table_structure_options.do_cell_matching = True

    # doc_converter = DocumentConverter(
    #     pipeline_options=pipeline_options,
    #     pdf_backend=DoclingParseDocumentBackend,
    # )

    # Docling Parse with Tesseract
    # ----------------------
    # pipeline_options = PipelineOptions()
    # pipeline_options.do_ocr = True
    # pipeline_options.do_table_structure = True
    # pipeline_options.table_structure_options.do_cell_matching = True
    # pipeline_options.ocr_options = TesseractOcrOptions()

    # doc_converter = DocumentConverter(
    #     pipeline_options=pipeline_options,
    #     pdf_backend=DoclingParseDocumentBackend,
    # )

    # Docling Parse with Tesseract CLI
    # ----------------------
    # pipeline_options = PipelineOptions()
    # pipeline_options.do_ocr = True
    # pipeline_options.do_table_structure = True
    # pipeline_options.table_structure_options.do_cell_matching = True
    # pipeline_options.ocr_options = TesseractCliOcrOptions()

    # doc_converter = DocumentConverter(
    #     pipeline_options=pipeline_options,
    #     pdf_backend=DoclingParseDocumentBackend,
    # )

    ###########################################################################

    start_time = time.time()
    conv_result = doc_converter.convert(input_doc_path)
    end_time = time.time() - start_time

    _log.info(f"Document converted in {end_time:.2f} seconds.")

    ## Export results
    output_dir = Path("../../examples/scratch")
    output_dir.mkdir(parents=True, exist_ok=True)
    doc_filename = conv_result.input.file.stem

    # Export Deep Search document JSON format:
    with (output_dir / f"{doc_filename}.json").open("w", encoding="utf-8") as fp:
        fp.write(json.dumps(conv_result.document.export_to_dict()))

    # Export Text format:
    with (output_dir / f"{doc_filename}.txt").open("w", encoding="utf-8") as fp:
        fp.write(conv_result.document.export_to_text())

    # Export Markdown format:
    with (output_dir / f"{doc_filename}.md").open("w", encoding="utf-8") as fp:
        fp.write(conv_result.document.export_to_markdown())

    # Export Document Tags format:
    with (output_dir / f"{doc_filename}.doctags").open("w", encoding="utf-8") as fp:
        fp.write(conv_result.document.export_to_document_tokens())


if __name__ == "__main__":
    main()