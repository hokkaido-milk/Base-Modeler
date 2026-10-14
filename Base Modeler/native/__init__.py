"""Optional ABI-independent macOS accelerator; NumPy remains the reference."""

import ctypes
import sys
from pathlib import Path
import numpy as np

LIBRARY = None
LOAD_ERROR = None
if sys.platform == "darwin":
    try:
        LIBRARY = ctypes.CDLL(
            str(Path(__file__).with_name("libbase_modeler_flow.dylib"))
        )
        array = np.ctypeslib.ndpointer(dtype=np.float32, ndim=2, flags="C_CONTIGUOUS")
        for name in ("bm_compose", "bm_sample"):
            fn = getattr(LIBRARY, name)
            fn.argtypes = [
                array,
                array,
                array,
                ctypes.c_size_t,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
            ]
            fn.restype = None
    except (OSError, AttributeError) as exc:
        LOAD_ERROR = str(exc)
        LIBRARY = None


def integrate(velocity, points, rest, shape):
    if LIBRARY is None:
        raise RuntimeError("The native accelerator is unavailable.")
    if len(shape) != 3 or any(n < 2 for n in shape):
        raise ValueError("Invalid interpolation grid shape.")
    velocity = np.ascontiguousarray(velocity, dtype=np.float32)
    points = np.ascontiguousarray(points, dtype=np.float32)
    rest = np.ascontiguousarray(rest, dtype=np.float32)
    if (
        velocity.shape != (int(np.prod(shape)), 3)
        or points.shape != velocity.shape
        or rest.ndim != 2
        or rest.shape[1] != 3
    ):
        raise ValueError("Invalid native interpolation arrays.")
    if any(not np.isfinite(array).all() for array in (velocity, points, rest)):
        raise ValueError("Non-finite native interpolation coordinates.")
    displacement = np.ascontiguousarray(velocity / 32.0, dtype=np.float32)
    scratch = np.empty_like(displacement)
    for _ in range(5):
        LIBRARY.bm_compose(displacement, points, scratch, len(points), *shape)
        displacement, scratch = scratch, displacement
    result = np.empty_like(rest)
    LIBRARY.bm_sample(displacement, rest, result, len(rest), *shape)
    return result
