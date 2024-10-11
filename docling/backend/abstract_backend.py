from abc import ABC, abstractmethod
from io import BytesIO
from pathlib import Path
from typing import Set, Union

# from docling.datamodel.document import InputDocument
from docling_core.types.experimental import DoclingDocument

from docling.datamodel.base_models import InputFormat


class AbstractDocumentBackend(ABC):
    @abstractmethod
    def __init__(self, in_doc: "InputDocument", path_or_stream: Union[BytesIO, Path]):
        self.path_or_stream = path_or_stream
        self.document_hash = in_doc.document_hash
        self.input_format = in_doc.format

    @abstractmethod
    def is_valid(self) -> bool:
        pass

    @classmethod
    @abstractmethod
    def supports_pagination(cls) -> bool:
        pass

    @abstractmethod
    def unload(self):
        if isinstance(self.path_or_stream, BytesIO):
            self.path_or_stream.close()

        self.path_or_stream = None

    @classmethod
    @abstractmethod
    def supported_formats(cls) -> Set[InputFormat]:
        pass


class PaginatedDocumentBackend(AbstractDocumentBackend):
    """DeclarativeDocumentBackend.

    A declarative document backend is a backend that can transform to DoclingDocument
    straight without a recognition pipeline.
    """

    @abstractmethod
    def page_count(self) -> int:
        pass


class DeclarativeDocumentBackend(AbstractDocumentBackend):
    """DeclarativeDocumentBackend.

    A declarative document backend is a backend that can transform to DoclingDocument
    straight without a recognition pipeline.
    """

    @abstractmethod
    def convert(self) -> DoclingDocument:
        pass
