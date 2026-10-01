# Johnathan 'Qasparr' (Κασπάρρ) Monroe, Keeper of the Secret Treasure
# All Rights Reserved, Without Prejudice.  CashApp $axoneme
"""safeval -- a tiny safe arithmetic evaluator for number-claims over the wire.

A ``recompute`` callable cannot cross JSON, so the API accepts
``proof: {"expression": "17+76", "expected": 93}`` and evaluates the
expression here, with no ``eval`` and no names -- only numbers and
arithmetic operators. Anything else is a ValueError, which the gate
reports as UNRESOLVED ("recomputation raised ..."), never as a crash.
"""

from __future__ import annotations

import ast
import operator

_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def evaluate(expression: str) -> int | float:
    """Evaluate a pure-arithmetic expression. Raises ValueError if unsafe."""
    if not isinstance(expression, str) or not expression.strip():
        raise ValueError("empty expression")
    if len(expression) > 200:
        raise ValueError("expression too long")
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"not an arithmetic expression: {exc}") from exc
    return _walk(tree.body)


def _walk(node: ast.AST) -> int | float:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise ValueError(f"constants must be numbers, got {node.value!r}")
        return node.value
    if isinstance(node, ast.BinOp):
        op = _OPS.get(type(node.op))
        if op is None:
            raise ValueError(f"operator {type(node.op).__name__} not allowed")
        return op(_walk(node.left), _walk(node.right))
    if isinstance(node, ast.UnaryOp):
        op = _UNARY_OPS.get(type(node.op))
        if op is None:
            raise ValueError(f"unary {type(node.op).__name__} not allowed")
        return op(_walk(node.operand))
    raise ValueError(f"{type(node).__name__} not allowed in expressions")
