import copy
import random
from typing import Tuple

from deepsearch_glm.nlp_utils import init_nlp_model
from deepsearch_glm.utils.doc_utils import (
    to_docling_document,
    to_legacy_document_format,
)
from deepsearch_glm.utils.load_pretrained_models import load_pretrained_nlp_models
from docling_core.types import BaseText
from docling_core.types import Document as DsDocument
from docling_core.types import Document as DsLegacyDocument
from docling_core.types import DocumentDescription as DsDocumentDescription
from docling_core.types import FileInfoObject as DsFileInfoObject
from docling_core.types import PageDimensions, PageReference, Prov, Ref
from docling_core.types import Table as DsSchemaTable
from docling_core.types.doc.base import BoundingBox as DsBoundingBox
from docling_core.types.doc.base import Figure, TableCell
from docling_core.types.experimental import BoundingBox, CoordOrigin
from docling_core.types.experimental.document import DoclingDocument
from PIL import ImageDraw
from pydantic import BaseModel, ConfigDict

from docling.datamodel.base_models import Cluster, FigureElement, Table, TextElement
from docling.datamodel.document import ConversionResult, layout_label_to_ds_type
from docling.utils.utils import create_hash


class GlmOptions(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_names: str = ""  # e.g. "language;term;reference"


class GlmModel:
    def __init__(self, options: GlmOptions):
        self.options = options

        load_pretrained_nlp_models()
        self.model = init_nlp_model(model_names=self.options.model_names)

    def _to_legacy_document(self, conv_res) -> DsDocument:
        title = ""
        desc = DsDocumentDescription(logs=[])

        page_hashes = [
            PageReference(
                hash=create_hash(conv_res.input.document_hash + ":" + str(p.page_no)),
                page=p.page_no + 1,
                model="default",
            )
            for p in conv_res.pages
        ]

        file_info = DsFileInfoObject(
            filename=conv_res.input.file.name,
            document_hash=conv_res.input.document_hash,
            num_pages=conv_res.input.page_count,
            page_hashes=page_hashes,
        )

        main_text = []
        tables = []
        figures = []

        page_no_to_page = {p.page_no: p for p in conv_res.pages}

        for element in conv_res.assembled.elements:
            # Convert bboxes to lower-left origin.
            target_bbox = DsBoundingBox(
                element.cluster.bbox.to_bottom_left_origin(
                    page_no_to_page[element.page_no].size.height
                ).as_tuple()
            )

            if isinstance(element, TextElement):
                main_text.append(
                    BaseText(
                        text=element.text,
                        obj_type=layout_label_to_ds_type.get(element.label),
                        name=element.label,
                        prov=[
                            Prov(
                                bbox=target_bbox,
                                page=element.page_no + 1,
                                span=[0, len(element.text)],
                            )
                        ],
                    )
                )
            elif isinstance(element, Table):
                index = len(tables)
                ref_str = f"#/tables/{index}"
                main_text.append(
                    Ref(
                        name=element.label,
                        obj_type=layout_label_to_ds_type.get(element.label),
                        ref=ref_str,
                    ),
                )

                # Initialise empty table data grid (only empty cells)
                table_data = [
                    [
                        TableCell(
                            text="",
                            # bbox=[0,0,0,0],
                            spans=[[i, j]],
                            obj_type="body",
                        )
                        for j in range(element.num_cols)
                    ]
                    for i in range(element.num_rows)
                ]

                # Overwrite cells in table data for which there is actual cell content.
                for cell in element.table_cells:
                    for i in range(
                        min(cell.start_row_offset_idx, element.num_rows),
                        min(cell.end_row_offset_idx, element.num_rows),
                    ):
                        for j in range(
                            min(cell.start_col_offset_idx, element.num_cols),
                            min(cell.end_col_offset_idx, element.num_cols),
                        ):
                            celltype = "body"
                            if cell.column_header:
                                celltype = "col_header"
                            elif cell.row_header:
                                celltype = "row_header"
                            elif cell.row_section:
                                celltype = "row_section"

                            def make_spans(cell):
                                for rspan in range(
                                    min(cell.start_row_offset_idx, element.num_rows),
                                    min(cell.end_row_offset_idx, element.num_rows),
                                ):
                                    for cspan in range(
                                        min(
                                            cell.start_col_offset_idx, element.num_cols
                                        ),
                                        min(cell.end_col_offset_idx, element.num_cols),
                                    ):
                                        yield [rspan, cspan]

                            spans = list(make_spans(cell))
                            table_data[i][j] = TableCell(
                                text=cell.text,
                                bbox=cell.bbox.to_bottom_left_origin(
                                    page_no_to_page[element.page_no].size.height
                                ).as_tuple(),
                                # col=j,
                                # row=i,
                                spans=spans,
                                obj_type=celltype,
                                # col_span=[cell.start_col_offset_idx, cell.end_col_offset_idx],
                                # row_span=[cell.start_row_offset_idx, cell.end_row_offset_idx]
                            )

                tables.append(
                    DsSchemaTable(
                        num_cols=element.num_cols,
                        num_rows=element.num_rows,
                        obj_type=layout_label_to_ds_type.get(element.label),
                        data=table_data,
                        prov=[
                            Prov(
                                bbox=target_bbox,
                                page=element.page_no + 1,
                                span=[0, 0],
                            )
                        ],
                    )
                )

            elif isinstance(element, FigureElement):
                index = len(figures)
                ref_str = f"#/figures/{index}"
                main_text.append(
                    Ref(
                        name=element.label,
                        obj_type=layout_label_to_ds_type.get(element.label),
                        ref=ref_str,
                    ),
                )
                figures.append(
                    Figure(
                        prov=[
                            Prov(
                                bbox=target_bbox,
                                page=element.page_no + 1,
                                span=[0, 0],
                            )
                        ],
                        obj_type=layout_label_to_ds_type.get(element.label),
                        # data=[[]],
                    )
                )

        page_dimensions = [
            PageDimensions(page=p.page_no + 1, height=p.size.height, width=p.size.width)
            for p in conv_res.pages
        ]

        ds_doc = DsDocument(
            name=title,
            description=desc,
            file_info=file_info,
            main_text=main_text,
            tables=tables,
            figures=figures,
            page_dimensions=page_dimensions,
        )

        return ds_doc

    def __call__(
        self, conv_res: ConversionResult
    ) -> Tuple[DsLegacyDocument, DoclingDocument]:
        ds_doc = self._to_legacy_document(conv_res)
        ds_doc_dict = ds_doc.model_dump(by_alias=True)

        glm_doc = self.model.apply_on_doc(ds_doc_dict)
        # ds_doc_dict = to_legacy_document_format(
        #    glm_doc, ds_doc_dict, update_name_label=True
        # )

        docling_doc: DoclingDocument = to_docling_document(glm_doc)  # Experimental
        # legacy_doc: DsLegacyDocument = None

        # if self.create_legacy_output:
        #    legacy_doc = DsLegacyDocument.model_validate(ds_doc_dict)

        # DEBUG code:
        def draw_clusters_and_cells(ds_document, page_no):
            clusters_to_draw = []
            image = copy.deepcopy(conv_res.pages[page_no].image)
            for ix, elem in enumerate(ds_document.main_text):
                if isinstance(elem, BaseText):
                    prov = elem.prov[0]
                elif isinstance(elem, Ref):
                    _, arr, index = elem.ref.split("/")
                    index = int(index)
                    if arr == "tables":
                        prov = ds_document.tables[index].prov[0]
                    elif arr == "figures":
                        prov = ds_document.pictures[index].prov[0]
                    else:
                        prov = None

                if prov and prov.page == page_no:
                    clusters_to_draw.append(
                        Cluster(
                            id=ix,
                            label=elem.name,
                            bbox=BoundingBox.from_tuple(
                                coord=prov.bbox,
                                origin=CoordOrigin.BOTTOMLEFT,
                            ).to_top_left_origin(conv_res.pages[page_no].size.height),
                        )
                    )

            draw = ImageDraw.Draw(image)
            for c in clusters_to_draw:
                x0, y0, x1, y1 = c.bbox.as_tuple()
                draw.rectangle([(x0, y0), (x1, y1)], outline="red")
                draw.text((x0 + 2, y0 + 2), f"{c.id}:{c.label}", fill=(255, 0, 0, 255))

                cell_color = (
                    random.randint(30, 140),
                    random.randint(30, 140),
                    random.randint(30, 140),
                )
                for tc in c.cells:  # [:1]:
                    x0, y0, x1, y1 = tc.bbox.as_tuple()
                    draw.rectangle([(x0, y0), (x1, y1)], outline=cell_color)
            image.show()

        # draw_clusters_and_cells(ds_doc, 0)
        # draw_clusters_and_cells(exported_doc, 0)

        return docling_doc
