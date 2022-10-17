from .env import * # make sure GPU related env vars are set before importing torch

import time
import logging

import py3nvml.py3nvml as pynvml # GPU management

logging.basicConfig()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

TIC = {}
GPUMEMPEAK = {}

def tic(name = ""):
    """ start clock
    Args:
        name: name of the clock
    """
    global TIC, GPUMEMPEAK
    TIC[name] = time.time()
    GPUMEMPEAK[name] = gpu_usage()

def toc(name = "", log_mem_usage = False):
    """ end clock and print time elapsed since the last tic 
    Args:
        name: name of the clock
        log_mem_usage: if True, log GPU memory usage
    """
    global TIC
    t = time.time() - TIC.get(name, TIC[""])
    logger.info(f"TIMING {name}: took {t} sec")
    if log_mem_usage:
        gpu_usage(name)
        log_gpu_gpu_mempeak(name)

def get_num_gpus():
    if not torch.cuda.is_available():
        return 0
    pynvml.nvmlInit() # Can throw pynvml.NVMLError_DriverNotLoaded if driver problem
    return pynvml.nvmlDeviceGetCount()
    
def has_gpu():
    return get_num_gpus() > 0

def gpu_mempeak(name = ""):
    """ measure / return peak GPU memory usage peak (since last tic) """
    global GPUMEMPEAK
    GPUMEMPEAK[name] = max(GPUMEMPEAK.get(name, GPUMEMPEAK[""]), gpu_usage(verbose = False))
    return GPUMEMPEAK[name]

def log_gpu_gpu_mempeak(name = ""):
    """ log peak GPU memory usage """
    if has_gpu():
        logger.info(f"GPU MEMORY PEAK {name}: {gpu_mempeak(name)} MB")

def gpu_usage(name = "", index = None, verbose = True, stream = None):
    """
    Args:
        name: name of the clock
        index: GPU index
        stream: stream to log to
    """
    if verbose is None:
        verbose = (stream == None)
    summemused = 0
    indices = range(get_num_gpus())
    if index is None:
        pass
    elif isinstance(index, int):
        assert index in indices, "Got index %d but only %d GPUs available" % (index, indices)
        indices = [index]
    else:
        for i in index:
            assert i in indices, "Got index %d but only %d GPUs available" % (i, indices)
        indices = index
    for igpu in indices:
        handle = pynvml.nvmlDeviceGetHandleByIndex(igpu)
        info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        gpuname = pynvml.nvmlDeviceGetName(handle)
        # use = pynvml.nvmlDeviceGetUtilizationRates(handle) # This info does not seem to be reliable
        memused = info.used // 1024**2
        memtotal = info.total // 1024**2
        if memused >= 10: # There is always a residual GPU memory used (1 or a few MB). Less than 10 MB usually means nothing.
            summemused+= memused
            s = f"GPU MEMORY {name} : {igpu+1}/{len(indices)} {gpuname}: mem {memused} / {memtotal} MB"
            if verbose:
                logger.info(s)
            if stream is not None:
                stream.write(f"{time.time()} {s}")
                stream.flush()
                
    return summemused

def gpu_total_memory(index = 0):
    pynvml.nvmlInit()
    handle = pynvml.nvmlDeviceGetHandleByIndex(index)
    info = pynvml.nvmlDeviceGetMemoryInfo(handle)
    return info.total // 1024**2

def gpu_free_memory(index = 0):
    pynvml.nvmlInit()
    handle = pynvml.nvmlDeviceGetHandleByIndex(index)
    info = pynvml.nvmlDeviceGetMemoryInfo(handle)
    return info.free // 1024**2
