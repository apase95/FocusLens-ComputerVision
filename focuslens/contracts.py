from dataclasses import dataclass


@dataclass(frozen=True)
class Frame:
    data: bytes
    width: int
    height: int
    format: str


@dataclass(frozen=True)
class TextLine:
    text: str
    confidence: float
    polygon: list
