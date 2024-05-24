from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QGraphicsPixmapItem, QGraphicsScene, QGraphicsView

if TYPE_CHECKING:
    from PyQt6.QtGui import QWheelEvent


class GraphicsView(QGraphicsView):
    def __init__(self, scene: QGraphicsScene, pixmap: QGraphicsPixmapItem) -> None:  # cSpell:ignore Pixmap
        super().__init__(scene)

        self.zoom_level = 0

        self.pixmap = pixmap

        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)

    def fit_in_view(self) -> None:
        self.fitInView(self.pixmap, Qt.AspectRatioMode.KeepAspectRatio)

    def wheelEvent(self, event: "QWheelEvent") -> None:  # noqa: N802
        zoom_in_factor = 1.25
        zoom_out_factor = 1 / zoom_in_factor

        if event.angleDelta().y() > 0:
            factor = zoom_in_factor
            self.zoom_level += 1
        else:
            factor = zoom_out_factor
            self.zoom_level -= 1

        if self.zoom_level > 0:
            self.scale(factor, factor)
        else:
            self.zoom_level = 0
            self.fit_in_view()
