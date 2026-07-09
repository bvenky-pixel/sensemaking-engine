"""
Learning is a deliberately unimplemented reserved slot (see
src/learning/__init__.py and engine/decisions.md) -- this test exists as
a canary, not coverage: it confirms the stub still raises
NotImplementedError, so if someone starts wiring real logic into
run_learning without deliberately reopening that decision, this test
starts failing and forces the question rather than passing silently.
"""

from __future__ import annotations

import pytest

from src.learning import run_learning


def test_run_learning_is_a_deliberately_unimplemented_stub():
    with pytest.raises(NotImplementedError):
        run_learning()
