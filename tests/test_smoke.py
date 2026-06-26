"""Phase 0 smoke test — package imports and exposes a version."""

import resourcer


def test_version_exposed() -> None:
    assert isinstance(resourcer.__version__, str)
    assert resourcer.__version__
