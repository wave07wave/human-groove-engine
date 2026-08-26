import hashlib

import numpy as np


def derive_seed(master_seed: int, *namespace: object) -> int:
    payload = "\x1f".join([str(master_seed), *(str(item) for item in namespace)]).encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:16], "big")


class HierarchicalRNG:
    """Stable, namespace-derived streams. Never relies on Python's randomized hash()."""

    def __init__(self, master_seed: int):
        self.master_seed = master_seed

    def stream(self, *namespace: object) -> np.random.Generator:
        return np.random.Generator(np.random.PCG64DXSM(derive_seed(self.master_seed, *namespace)))

    def id(self, *namespace: object) -> str:
        value = derive_seed(self.master_seed, *namespace)
        return f"ev-{value:032x}"
