"""Round-4 R4-3: a word's box covers the word, not the spaces after it.

Notepad's word ranges read "460 " and their box spans the space, so a click on the
box centre landed right of the word (centre 337 vs drawn 317) and selected the gap.
"""

from unittest.mock import MagicMock

import pytest

from windows_mcp.uia.controls import Control
from windows_mcp.uia.core import Rect


@pytest.mark.parametrize(
    "raw, right",
    [
        ("460 ", 130),  # one trailing space of four characters: keep 3/4 of 40 px
        ("460", 140),  # nothing to trim
        ("units\r\n", 140),  # a line break has no width on screen
        ("ab  \r\n", 120),  # spaces before the line break do
    ],
)
def test_trailing_spaces_are_trimmed_from_the_box(raw, right):
    assert Control._trim_trailing_space([Rect(100, 10, 140, 30)], raw) == [Rect(100, 10, right, 30)]


def test_a_wrapped_word_keeps_its_boxes():
    # Which share of the text sits on the last line is unknown, so nothing is guessed.
    rects = [Rect(300, 10, 340, 30), Rect(0, 30, 20, 50)]
    assert Control._trim_trailing_space(rects, "wrapped ") == rects


def test_word_boxes_centre_on_the_word_text():
    word_range = MagicMock()
    word_range.GetBoundingRectangles.return_value = [Rect(297, 10, 377, 30)]
    control = MagicMock()
    control.GetPattern.return_value.DocumentRange.GetAttributeValue.return_value = None
    control._iter_word_ranges.return_value = [("460", word_range, "460 ")]
    control._trim_trailing_space = Control._trim_trailing_space

    [(word, [box])] = Control.GetAllWordBoundingBoxes(control)

    assert word == "460"
    assert box.xcenter() == 327  # 297..357: the three digits, not the space after them
