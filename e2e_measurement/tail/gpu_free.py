"""Exit 0 if the GPU has at least NEED_GB free, else 1. Checks once and exits, so no CUDA context
is held while a caller waits (nvidia-smi is broken by the driver mismatch, hence torch)."""
import sys
import torch
need = float(sys.argv[1]) if len(sys.argv) > 1 else 4.5
free, total = torch.cuda.mem_get_info()
print(f"GPU free {free / 2**30:.1f} GiB of {total / 2**30:.1f}", flush=True)
sys.exit(0 if free / 2**30 >= need else 1)
