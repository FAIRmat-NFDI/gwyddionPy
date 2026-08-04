"""Registry of real vendor sample files — the single source of truth for
every test that needs one.

Adding a vendor or a new format version is meant to cost one entry here plus
the data file (and a regenerated golden JSON), never new test code: the
format tests all parametrize over ``SAMPLES``. Provenance and licensing for
each file live in test-data/README.md.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

TESTS_DIR = Path(__file__).resolve().parents[1]
TEST_DATA = TESTS_DIR.parents[1] / "test-data"
GOLDEN_DIR = TESTS_DIR / "golden"


@dataclass(frozen=True)
class Sample:
    """One real vendor file and what it is expected to contain."""

    filename: str
    vendor: str
    module: str            # Gwyddion module expected to claim the file
    channels: int          # expected image-channel count
    notes: str = ""
    # Header fields read straight out of the vendor's own file, independent
    # of anything gwyconvert reports. Empty when the format's header is not
    # plain-text greppable. See formats/test_vendor_header.py.
    header_checks: Dict[str, object] = field(default_factory=dict)

    @property
    def path(self) -> Path:
        return TEST_DATA / self.filename

    @property
    def golden_path(self) -> Path:
        # "sample_0.jpk-qi-image" -> "sample_0.jpk-qi-image.json"
        return GOLDEN_DIR / f"{self.filename}.json"

    @property
    def id(self) -> str:
        """pytest parametrize id — the filename reads best in test output."""
        return self.filename

    def exists(self) -> bool:
        return self.path.is_file()


SAMPLES: List[Sample] = [
    Sample(
        filename="VGEP-15m-.0_00000.spm",
        vendor="Bruker Nanoscope",
        module="nanoscope",
        channels=8,
        notes="own measurement; ASCII header is greppable, so its scan size "
              "and pixel counts cross-check the converter independently",
        # From the file's own ASCII header: "\\Scan Size: 20000 nm",
        # "\\Samps/line: 512", "\\Lines: 512".
        header_checks={"xreal": 20000e-9, "yreal": 20000e-9, "shape": (512, 512)},
    ),
    Sample(
        filename="sample_0.jpk",
        vendor="JPK",
        module="jpkscan",
        channels=10,
        notes="trace/retrace pairs; metadata values carry decimal commas",
    ),
    Sample(
        filename="sample_0.jpk-qi-image",
        vendor="JPK QI",
        module="jpkscan",
        channels=6,
        notes="quantitative-imaging variant of the same vendor format",
    ),
    Sample(
        filename="sample_0.stp",
        vendor="WSxM",
        module="wsxmfile",
        channels=1,
    ),
    Sample(
        filename="sample_0.top",
        vendor="WSxM",
        module="wsxmfile",
        channels=1,
        notes="second WSxM extension; same module, different container",
    ),
    Sample(
        filename="sample_0.ibw",
        vendor="Igor / Asylum",
        module="igorfile",
        channels=8,
    ),
    Sample(
        filename="Bias-Spectroscopy002.dat",
        vendor="Nanonis",
        module="nanonis_spec",
        channels=0,
        notes="spectroscopy: parses, but holds graph data the gwyddionpy "
              "model does not expose as image channels yet (TODO.md)",
    ),
]

SAMPLES_BY_NAME: Dict[str, Sample] = {s.filename: s for s in SAMPLES}

#: Samples that actually carry image channels — the ones whose pixel/unit
#: content is worth asserting. Keeps the spectroscopy file from generating a
#: row of vacuously-passing sub-tests.
IMAGE_SAMPLES: List[Sample] = [s for s in SAMPLES if s.channels > 0]


def find_sample(filename: str) -> Optional[Sample]:
    return SAMPLES_BY_NAME.get(filename)
