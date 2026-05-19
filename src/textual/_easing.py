"""
Define a series of easing functions for more natural-looking animations.
Taken from https://easings.net/ and translated from JavaScript.
"""

from math import cos, pi, sin, sqrt


def _in_out_expo(x: float) -> float:
    """https://easings.net/#easeInOutExpo"""
    pass


def _in_out_circ(x: float) -> float:
    """https://easings.net/#easeInOutCirc"""
    pass


def _in_out_back(x: float) -> float:
    """https://easings.net/#easeInOutBack"""
    pass


def _in_elastic(x: float) -> float:
    """https://easings.net/#easeInElastic"""
    pass


def _in_out_elastic(x: float) -> float:
    """https://easings.net/#easeInOutElastic"""
    pass


def _out_elastic(x: float) -> float:
    """https://easings.net/#easeInOutElastic"""
    pass


def _out_bounce(x: float) -> float:
    """https://easings.net/#easeOutBounce"""
    pass


def _in_bounce(x: float) -> float:
    """https://easings.net/#easeInBounce"""
    pass


def _in_out_bounce(x: float) -> float:
    """https://easings.net/#easeInOutBounce"""
    pass


EASING = {
    "none": lambda x: 1.0,
    "round": lambda x: 0.0 if x < 0.5 else 1.0,
    "linear": lambda x: x,
    "in_sine": lambda x: 1 - cos((x * pi) / 2),
    "in_out_sine": lambda x: -(cos(x * pi) - 1) / 2,
    "out_sine": lambda x: sin((x * pi) / 2),
    "in_quad": lambda x: x * x,
    "in_out_quad": lambda x: 2 * x * x if x < 0.5 else 1 - pow(-2 * x + 2, 2) / 2,
    "out_quad": lambda x: 1 - pow(1 - x, 2),
    "in_cubic": lambda x: x * x * x,
    "in_out_cubic": lambda x: 4 * x * x * x if x < 0.5 else 1 - pow(-2 * x + 2, 3) / 2,
    "out_cubic": lambda x: 1 - pow(1 - x, 3),
    "in_quart": lambda x: pow(x, 4),
    "in_out_quart": lambda x: 8 * pow(x, 4) if x < 0.5 else 1 - pow(-2 * x + 2, 4) / 2,
    "out_quart": lambda x: 1 - pow(1 - x, 4),
    "in_quint": lambda x: pow(x, 5),
    "in_out_quint": lambda x: 16 * pow(x, 5) if x < 0.5 else 1 - pow(-2 * x + 2, 5) / 2,
    "out_quint": lambda x: 1 - pow(1 - x, 5),
    "in_expo": lambda x: pow(2, 10 * x - 10) if x else 0,
    "in_out_expo": _in_out_expo,
    "out_expo": lambda x: 1 - pow(2, -10 * x) if x != 1 else 1,
    "in_circ": lambda x: 1 - sqrt(1 - pow(x, 2)),
    "in_out_circ": _in_out_circ,
    "out_circ": lambda x: sqrt(1 - pow(x - 1, 2)),
    "in_back": lambda x: 2.70158 * pow(x, 3) - 1.70158 * pow(x, 2),
    "in_out_back": _in_out_back,
    "out_back": lambda x: 1 + 2.70158 * pow(x - 1, 3) + 1.70158 * pow(x - 1, 2),
    "in_elastic": _in_elastic,
    "in_out_elastic": _in_out_elastic,
    "out_elastic": _out_elastic,
    "in_bounce": _in_bounce,
    "in_out_bounce": _in_out_bounce,
    "out_bounce": _out_bounce,
}

DEFAULT_EASING = "in_out_cubic"
DEFAULT_SCROLL_EASING = "out_cubic"
