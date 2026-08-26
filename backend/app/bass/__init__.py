"""Human Bass Engine public package.

The package only depends on shared meter, timing and seeded-random contracts.  It does
not import Groove Engine generator internals, which keeps the future integration seam
explicit.
"""

from .generation import generate_bass_candidates, generate_bass_pattern
from .models import BassPattern

__all__ = ["BassPattern", "generate_bass_candidates", "generate_bass_pattern"]
