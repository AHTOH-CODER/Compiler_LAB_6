from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QDialog,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QVBoxLayout,
)

from semantic_analyzer import (
    AstNode,
    ComplexDeclNode,
    ComplexTypeNode,
    FloatLiteralNode,
    IdentifierNode,
    IntLiteralNode,
    ProgramNode,
)


@dataclass
class _TreeNode:
    label: str
    children: List["_TreeNode"] = field(default_factory=list)


@dataclass
class _LayoutNode:
    node: _TreeNode
    width: float
    children: List["_LayoutNode"]


class _AstGraphicsView(QGraphicsView):
    MIN_SCALE = 0.15
    MAX_SCALE = 6.0
    ZOOM_IN_FACTOR = 1.2
    ZOOM_OUT_FACTOR = 1.0 / ZOOM_IN_FACTOR

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.angleDelta().y() > 0:
                self._apply_zoom(self.ZOOM_IN_FACTOR)
            elif event.angleDelta().y() < 0:
                self._apply_zoom(self.ZOOM_OUT_FACTOR)
            event.accept()
            return
        super().wheelEvent(event)

    def keyPressEvent(self, event):
        key = event.key()
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
                self._apply_zoom(self.ZOOM_IN_FACTOR)
                event.accept()
                return
            if key == Qt.Key.Key_Minus:
                self._apply_zoom(self.ZOOM_OUT_FACTOR)
                event.accept()
                return
            if key == Qt.Key.Key_0:
                self.resetTransform()
                event.accept()
                return
        super().keyPressEvent(event)

    def _apply_zoom(self, factor: float):
        current_scale = self.transform().m11()
        new_scale = current_scale * factor
        if new_scale < self.MIN_SCALE or new_scale > self.MAX_SCALE:
            return
        self.scale(factor, factor)


class AstGraphDialog(QDialog):
    NODE_MIN_WIDTH = 120.0
    NODE_HEIGHT = 36.0
    H_SPACING = 24.0
    V_SPACING = 56.0
    MARGIN = 40.0
    TEXT_PADDING_X = 16.0

    def __init__(self, ast_root: AstNode, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Дерево разбора (AST)")
        self.resize(1200, 760)
        self.setStyleSheet("QDialog { background-color: #2b2b2b; }")

        layout = QVBoxLayout(self)
        self.scene = QGraphicsScene(self)
        self.view = _AstGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.view.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.view.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.view.setBackgroundBrush(QBrush(QColor("#1e1e1e")))
        self.view.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.view.setToolTip(
            "Ctrl + колесо мыши: масштаб\n"
            "Ctrl + '+/-': увеличить/уменьшить\n"
            "Ctrl + 0: сбросить масштаб"
        )
        layout.addWidget(self.view)

        tree_root = self._build_ast_tree(ast_root)
        layout_root = self._build_layout(tree_root)
        self._draw_tree(layout_root, self.MARGIN, self.MARGIN)
        self.scene.setSceneRect(self.scene.itemsBoundingRect().adjusted(-20, -20, 20, 20))
        self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def _build_ast_tree(self, ast_root: AstNode) -> _TreeNode:
        if isinstance(ast_root, ProgramNode):
            return _TreeNode(
                "Program",
                [self._build_ast_tree(decl) for decl in ast_root.declarations],
            )
        if isinstance(ast_root, ComplexDeclNode):
            mods = ", ".join(ast_root.modifiers)
            return _TreeNode(
                f"ComplexDecl: {ast_root.name}",
                [
                    _TreeNode(f"modifiers: [{mods}]"),
                    _TreeNode("Type", [self._build_ast_tree(ast_root.type_node)]),
                    _TreeNode("Re", [self._build_ast_tree(ast_root.re)]),
                    _TreeNode("Im", [self._build_ast_tree(ast_root.im)]),
                ],
            )
        if isinstance(ast_root, ComplexTypeNode):
            return _TreeNode(f"Type: {ast_root.name}")
        if isinstance(ast_root, FloatLiteralNode):
            return _TreeNode(f"Float: {ast_root.value}")
        if isinstance(ast_root, IntLiteralNode):
            return _TreeNode(f"Int: {ast_root.value}")
        if isinstance(ast_root, IdentifierNode):
            return _TreeNode(f"Id: {ast_root.name}")
        return _TreeNode(ast_root.label())

    def _measure_node_width(self, label: str) -> float:
        tmp = QGraphicsSimpleTextItem(label)
        tmp.setFont(QFont("Consolas", 10))
        return max(self.NODE_MIN_WIDTH, tmp.boundingRect().width() + self.TEXT_PADDING_X * 2.0)

    def _build_layout(self, node: _TreeNode) -> _LayoutNode:
        child_layouts = [self._build_layout(ch) for ch in node.children]
        own_width = self._measure_node_width(node.label)
        if not child_layouts:
            return _LayoutNode(node=node, width=own_width, children=[])

        children_width = sum(ch.width for ch in child_layouts)
        children_width += self.H_SPACING * (len(child_layouts) - 1)
        width = max(own_width, children_width)
        return _LayoutNode(node=node, width=width, children=child_layouts)

    def _draw_tree(self, layout_node: _LayoutNode, x: float, y: float) -> Tuple[float, float]:
        center_x = x + layout_node.width / 2.0
        node_width = self._measure_node_width(layout_node.node.label)
        node_x = center_x - node_width / 2.0
        node_y = y

        node_rect = QRectF(node_x, node_y, node_width, self.NODE_HEIGHT)
        self._draw_node_box(node_rect, layout_node.node)

        if not layout_node.children:
            return center_x, node_y

        children_total_width = sum(ch.width for ch in layout_node.children)
        children_total_width += self.H_SPACING * (len(layout_node.children) - 1)
        child_cursor_x = center_x - children_total_width / 2.0

        for child in layout_node.children:
            child_center_x, child_top_y = self._draw_tree(
                child,
                child_cursor_x,
                node_y + self.NODE_HEIGHT + self.V_SPACING,
            )
            self.scene.addLine(
                center_x,
                node_y + self.NODE_HEIGHT,
                child_center_x,
                child_top_y,
                QPen(QColor("#FFA500"), 1.5),
            )
            child_cursor_x += child.width + self.H_SPACING

        return center_x, node_y

    def _draw_node_box(self, rect: QRectF, node: _TreeNode):
        fill_color, border_color = self._node_colors(node.label)
        path = QPainterPath()
        path.addRoundedRect(rect, 6.0, 6.0)
        self.scene.addPath(path, QPen(border_color, 1.2), QBrush(fill_color))

        title = QGraphicsSimpleTextItem(node.label)
        title.setBrush(QBrush(QColor("#ffffff")))
        title.setFont(QFont("Consolas", 10))
        title_rect = title.boundingRect()
        title.setPos(
            rect.left() + (rect.width() - title_rect.width()) / 2.0,
            rect.top() + (rect.height() - title_rect.height()) / 2.0,
        )
        self.scene.addItem(title)

    def _node_colors(self, label: str) -> Tuple[QColor, QColor]:
        if label == "Program":
            return QColor("#404040"), QColor("#FFA500")
        if label.startswith("ComplexDecl"):
            return QColor("#4a3a20"), QColor("#FFA500")
        if label.startswith("modifiers"):
            return QColor("#3a3a3a"), QColor("#888888")
        if label in ("Type", "Re", "Im"):
            return QColor("#2f3a47"), QColor("#FFB52E")
        if label.startswith("Type:"):
            return QColor("#2b3552"), QColor("#8ea1cc")
        if label.startswith("Id:"):
            return QColor("#2f4b3f"), QColor("#7ac8a0")
        if label.startswith("Int:"):
            return QColor("#4d3d2f"), QColor("#d4b08a")
        if label.startswith("Float:"):
            return QColor("#4d3d2f"), QColor("#FFA500")
        return QColor("#2b2f38"), QColor("#8a93a5")
