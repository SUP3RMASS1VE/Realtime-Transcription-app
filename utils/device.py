import torch
import numpy as np
import subprocess

def get_device(force_cpu=False):
    if force_cpu:
        return "cpu"
    if torch.cuda.is_available():
        return "cuda"
    elif torch.backends.mps.is_available():
        torch.mps.empty_cache()
        return "mps"
    else:
        return "cpu"
    
def get_torch_and_np_dtypes(device, use_bfloat16=False):
    if device == "cuda":
        torch_dtype = torch.bfloat16 if use_bfloat16 else torch.float16
        np_dtype = np.float16
    elif device == "mps":
        torch_dtype = torch.bfloat16 if use_bfloat16 else torch.float16
        np_dtype = np.float16
    else:
        torch_dtype = torch.float32
        np_dtype = np.float32
    return torch_dtype, np_dtype

def cuda_version_check():
    if torch.cuda.is_available():
        try:
            cuda_runtime = subprocess.check_output(["nvcc", "--version"]).decode()
            cuda_version = cuda_runtime.split()[-2]
        except Exception:
            # Fallback to PyTorch's built-in version if nvcc isn't available
            cuda_version = torch.version.cuda
        
        device_name = torch.cuda.get_device_name(0)
        return cuda_version, device_name
    else:
        return None, None
