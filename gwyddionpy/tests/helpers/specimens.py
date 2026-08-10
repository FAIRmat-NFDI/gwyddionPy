"""Registry of the raw measurement files the format tests run against.

Each entry names one file under tests/data/, the Gwyddion module expected to
read it, and how many image channels it should yield. Raw file, reference
reference and provenance all live together in the vendor directory, so adding
a vendor or a new firmware revision means one entry here plus the file — the
tests themselves parametrize over this list and need no editing.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

TESTS_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = TESTS_DIR / "data"


@dataclass(frozen=True)
class Specimen:
    """One raw measurement file and what reading it should produce."""

    relpath: str           # path under tests/data/, e.g. "jpk/sample_0.jpk"
    vendor: str
    module: str            # Gwyddion module expected to claim the file
    channels: int          # expected image-channel count
    sha256: str = ""       # of the raw file, so a swapped or edited copy shows up
    notes: str = ""
    # Geometry read directly out of the raw file's own header, where the
    # header is plain text. Used to check the converter against the vendor's
    # own numbers rather than against a previous conversion.
    header_checks: Dict[str, object] = field(default_factory=dict)

    @property
    def path(self) -> Path:
        return DATA_DIR / self.relpath

    @property
    def reference_path(self) -> Path:
        """Reference, kept beside the raw file it describes."""
        return self.path.with_suffix(self.path.suffix + ".json")

    @property
    def id(self) -> str:
        """Parametrize id: the vendor directory plus filename, which is what
        you want to read in a failure line."""
        return self.relpath

    @property
    def filename(self) -> str:
        return Path(self.relpath).name

    def exists(self) -> bool:
        return self.path.is_file()


SPECIMENS: List[Specimen] = [
    Specimen(
        relpath="bruker_nanoscope/VGEP-15m-.0_00000.spm",
        vendor="Bruker Nanoscope",
        module="nanoscope",
        channels=8,
        sha256="f09dac1cc0ef074e289870ccbdacd6d9da76a28e559f7201b2284d8bd76f5ee2",
        notes="own measurement; plain-text header, so its geometry can be "
              "read independently of the converter",
        # Straight from the file's own header lines:
        #   \Scan Size: 20000 nm   \Samps/line: 512   \Lines: 512
        header_checks={"xreal": 20000e-9, "yreal": 20000e-9, "shape": (512, 512)},
    ),
    Specimen(
        relpath="jpk/sample_0.jpk",
        vendor="JPK",
        module="jpkscan",
        channels=10,
        sha256="7b1945c97936f005446b2d75be49643a364ecaf8798a2d2b97b092d40f21de2e",
        notes="trace/retrace pairs; several metadata values carry decimal commas",
    ),
    Specimen(
        relpath="jpk/sample_0.jpk-qi-image",
        vendor="JPK",
        module="jpkscan",
        channels=6,
        sha256="af04539519c8a8a7d498148af7f61288d8f4434a5d8a750a2f47bff999c5d682",
        notes="quantitative-imaging variant of the same vendor format",
    ),
    Specimen(
        relpath="wsxm/sample_0.stp",
        vendor="WSxM",
        module="wsxmfile",
        channels=1,
        sha256="977569f7fdbdc5de92fd8b2172c9ff8fd38f3b8df6de0b4f95a547a8b12da8c5",
    ),
    Specimen(
        relpath="wsxm/sample_0.top",
        vendor="WSxM",
        module="wsxmfile",
        channels=1,
        sha256="861bc8ab110d9cb820971b23df77fffa1e746fe81464890e5f8787e2e291b174",
        notes="second WSxM extension; same module, different container",
    ),
    Specimen(
        relpath="igor_asylum/sample_0.ibw",
        vendor="Igor / Asylum",
        module="igorfile",
        channels=8,
        sha256="84a7fad6032cc735fef6db2781c1d74d385f25b9ead4c3561f50560943233985",
    ),
    Specimen(
        relpath="nanonis/Bias-Spectroscopy002.dat",
        vendor="Nanonis",
        module="nanonis_spec",
        channels=0,
        sha256="491c73fba64369f8305fd384dec5924b752a5b82baf465e9f339fcc5de074257",
        notes="spectroscopy: reads fine, but holds graph data that the data "
              "model does not surface as image channels",
    ),
]

SPECIMENS_BY_ID: Dict[str, Specimen] = {s.relpath: s for s in SPECIMENS}

#: Specimens that carry image channels — the ones whose pixel content is
#: worth comparing. Keeps the spectroscopy file out of tests that would
#: otherwise pass vacuously on it.
IMAGE_SPECIMENS: List[Specimen] = [s for s in SPECIMENS if s.channels > 0]


def find_specimen(identifier: str) -> Optional[Specimen]:
    """Look up a specimen by "vendor/filename", or by bare filename."""
    if identifier in SPECIMENS_BY_ID:
        return SPECIMENS_BY_ID[identifier]
    matches = [s for s in SPECIMENS if s.filename == identifier]
    return matches[0] if len(matches) == 1 else None
