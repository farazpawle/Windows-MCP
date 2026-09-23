"""Round-2 3.20: Snapshot badges sit inside their own box and never hide each other."""

from unittest.mock import patch

from PIL import Image

from windows_mcp.desktop.service import Desktop, place_badge
from windows_mcp.tree.views import BoundingBox, Center, TreeElementNode

BADGE = (14, 16)  # typical 1-digit badge size (width, height)


def _overlaps(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _rect(xy, size=BADGE):
    return (xy[0], xy[1], xy[0] + size[0], xy[1] + size[1])


def test_badge_sits_inside_top_left_of_box():
    x, y = place_badge((100, 50, 300, 80), BADGE, [], (1920, 1080))
    assert 100 < x <= 104 and 50 < y <= 54


def test_three_stacked_fields_each_get_their_own_badge():
    boxes = [(10, 10, 200, 32), (10, 34, 200, 56), (10, 58, 200, 80)]
    placed = []
    for box in boxes:
        rect = _rect(place_badge(box, BADGE, placed, (400, 200)))
        assert box[0] <= rect[0] and rect[2] <= box[2]
        assert box[1] <= rect[1] and rect[3] <= box[3]
        placed.append(rect)
    assert not any(_overlaps(a, b) for i, a in enumerate(placed) for b in placed[i + 1 :])


def test_badge_shifts_right_past_an_overlapping_badge():
    # Same box twice (e.g. a group and its only child): second badge moves along.
    box = (10, 10, 200, 40)
    first = _rect(place_badge(box, BADGE, [], (400, 200)))
    second = _rect(place_badge(box, BADGE, [first], (400, 200)))
    assert not _overlaps(first, second)
    assert second[2] <= box[2]


def test_badge_stays_inside_the_image():
    x, y = place_badge((390, 190, 400, 200), BADGE, [], (400, 200))
    assert 0 <= x <= 400 - BADGE[0] and 0 <= y <= 200 - BADGE[1]


def _node(left, top, right, bottom):
    return TreeElementNode(
        name="Edit",
        control_type="Edit",
        window_name="App",
        bounding_box=BoundingBox(
            left=left, top=top, right=right, bottom=bottom, width=right - left, height=bottom - top
        ),
        center=Center(x=(left + right) // 2, y=(top + bottom) // 2),
        metadata={},
    )


def test_later_box_outline_does_not_paint_over_an_earlier_badge():
    desktop = Desktop.__new__(Desktop)
    white = Image.new("RGB", (400, 200), "white")
    # Node 1's outline runs straight through node 0's badge area.
    nodes = [_node(10, 10, 200, 40), _node(12, 14, 150, 60)]
    with patch.object(Desktop, "get_screenshot", return_value=white):
        with patch("windows_mcp.desktop.service.uia.GetVirtualScreenRect") as rect:
            rect.return_value = (0, 0, 400, 200)
            with patch(
                "windows_mcp.desktop.service.random.randint",
                side_effect=[0xFF0000, 0x00FF00],
            ):
                img = desktop.get_annotated_screenshot(nodes=nodes)
    # Badge 0 (red) starts at (12, 12); node 1's green outline covers x=12..13
    # from y=14 down, so (13, 15) is badge unless the outline was drawn over it.
    assert img.getpixel((13, 15)) == (255, 0, 0)
