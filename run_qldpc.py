import builtins
builtins.input = lambda _='': 'n'

import numpy as np
import qldpc
import stim
from bbcodesim import circuit_level_simulation
from codes import create_bivariate_bicycle_codes
from ldpc import bposd_decoder, bp_decoder

# ── Decoder wrappers ────────────────────────────────────────────────
class BPOSDDecoder:
    name = "BPOSD"

    def set_h(self, H, priors, error_rate):
        self.H = H
        self.priors = priors
        self.error_rate = error_rate
        self.decoder = bposd_decoder(
            H,
            channel_probs=priors,
            max_iter=100,
            bp_method="ms",
            ms_scaling_factor=0.625,
            osd_method="osd_cs",
            osd_order=7,
        )

    def decode(self, syndrome):
        return self.decoder.decode(syndrome)


class BPDecoder:
    name = "BP"

    def set_h(self, H, priors, error_rate):
        self.H = H
        self.priors = priors
        self.decoder = bp_decoder(
            H,
            channel_probs=priors,
            max_iter=100,
            bp_method="ms",
            ms_scaling_factor=0.625,
        )
    def decode(self, syndrome):
        return self.decoder.decode(syndrome)

# ── Code ─────────────────────────────────────────────────────────────
code = create_bivariate_bicycle_codes(
    6, 6, [3], [1, 2], [1, 2], [3]
)  # [[72, 12, 6]]

# ── Simulation parameters ─────────────────────────────────────────────
num_trials = 10000
num_repeat = 12
error_rate  = 0.01

decoders = [BPOSDDecoder(), BPDecoder()]

# ── Run ───────────────────────────────────────────────────────────────
logical_errs, logical_errs_per_round, timing = circuit_level_simulation(
    code=code,
    error_rate=error_rate,
    decoders=decoders,
    num_repeat=num_repeat,
    num_trials=num_trials,
    W=1,        # sliding window size
    F=1,        # window stride
    z_basis=False,
    method=0,
    plot=False,
)

# ── Results ───────────────────────────────────────────────────────────
print("\n===== Results =====")
for name in logical_errs:
    print(f"{name}:")
    print(f"  logical error rate        : {logical_errs[name]:.4f}")
    print(f"  logical error rate/round  : {logical_errs_per_round[name]:.6f}")
    print(f"  avg decoding time         : {timing[name]:.6f} s")