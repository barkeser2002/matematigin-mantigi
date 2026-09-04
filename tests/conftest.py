import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

from matematigin_mantigi.core.models import SAMPLE_QUESTIONS  # noqa: E402


@pytest.fixture
def sample_questions():
    return list(SAMPLE_QUESTIONS)
