# Johnathan 'Qasparr' (Κασπάρρ) Monroe, Keeper of the Secret Treasure
# All Rights Reserved, Without Prejudice.  CashApp $axoneme
"""safeval -- a tiny safe arithmetic evaluator for number-claims over the wire.

    "The simple believeth every word: but the prudent man looketh
     well to his going."
    -- Proverbs 14:15

Hypothesis
----------
A number-claim can cross JSON without smuggling code: the wire format
carries an arithmetic *expression* ("17+76") plus the expected value,
and the gate recomputes the expression itself. The expression must be
provably inert -- no names, no calls, no attributes -- before it is
ever evaluated.

Method
------
The expression is parsed with ``ast.parse`` into a syntax tree and
*walked*, never ``eval``'d. The walker accepts exactly four node
shapes: numeric constants, binary operations from a fixed allow-list
(+ - * / // % **), and unary +/-. Every other node -- names, calls,
subscripts, attribute access, lambdas, comprehensions, anything --
raises ValueError. Two independent gates stand in series: a length
cap (200 characters, so no one ships a novel) and the structural
walk. What the walker cannot prove inert is refused, and the gate
above reports the refusal as UNRESOLVED ("recomputation raised ..."),
never as a crash and never as FALSEHOOD -- for the prudent man looks
well to his going, and lack of proof is never scored as proof of
falsehood.

Observation
-----------
``evaluate("17+76")`` returns 93. ``evaluate("__import__('os')")``
raises ValueError at the Name node; ``evaluate("(2+3)**2")`` returns
25; booleans are refused as constants (``True`` is not a number for
this gate's purposes -- it is a name wearing a number's clothes).

Result
------
The API can admit number-claims from any client on any platform
without executing client-supplied code. The analysis is total over
the grammar: the set of accepted programs is exactly arithmetic over
literals, which is why the refusal is structural rather than a
blocklist. Blocklists rot; grammars endure.

Law
---
The parallel is input validation as a duty of care: the gate owes
its operator the same prudence Proverbs demands of the traveler --
look well to the going before the foot lands. Cited for education
only; this module creates no legal effect.
"""

from __future__ import annotations

import ast
import operator

# The only binary operations the walker will perform. This is an
# allow-list, not a blocklist: anything not named here -- bitwise
# operators, matrix multiplication, shifts -- is refused by
# construction. The mapping is from AST node type to the concrete
# function applied, so the set of possible behaviors is closed and
# auditable at a glance.
_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

# Unary plus and minus, for expressions like "-5+8". Unary ``not``,
# ``~``, and ``await`` are absent -- and therefore refused.
_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def evaluate(expression: str) -> int | float:
    """Evaluate a pure-arithmetic expression. Raises ValueError if unsafe.

    The function performs three checks in order, cheapest first:

    1. *Shape*: the input must be a non-empty string under 200
       characters. This rejects the empty expression and the
       pathological long one before any parsing is attempted.
    2. *Syntax*: ``ast.parse(expression, mode="eval")`` must succeed.
       ``mode="eval"`` is itself a restriction -- it accepts only a
       single expression, never statements, so ``"1+2; 3"`` dies here.
    3. *Structure*: ``_walk`` descends the tree and proves every node
       inert (see above). This is where ``"__import__('os')"`` dies --
       at the ``Name`` node, before anything is called.

    Returns an int or float. Raises ValueError with a human-readable
    reason on any refusal, so the gate's note can quote the cause.
    """
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
    """Recursively evaluate one AST node, refusing anything impure.

    The recursion is structural: each node type is handled explicitly,
    and the final ``raise`` is the closed world's border wall. Note
    what is *absent* -- there is no ``ast.Name`` branch (so variables
    and builtins are unnameable), no ``ast.Call`` branch (so nothing
    is invocable), no ``ast.Attribute``/``ast.Subscript`` branches
    (so no object graph is reachable). A hostile expression cannot
    "find a gap" because there are no gaps: unhandled node types fall
    through to the refusal.

    Booleans are refused as constants even though ``isinstance(True,
    int)`` is True in Python -- ``True`` is a name in the source
    language, and this gate does not traffic in names.
    """
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
