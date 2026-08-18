import os
import hashlib
import logging

def get_head_hash(filepath: str, chunk_size: int = 4096) -> str:
    """提取文件前 chunk_size 字节计算 MD5。用于快速比对文件同源性。"""
    if not os.path.isfile(filepath):
        return ""
    
    file_size = os.path.getsize(filepath)
    if file_size == 0:
        return "EMPTY"
        
    hasher = hashlib.md5()
    try:
        with open(filepath, "rb") as f:
            hasher.update(f.read(chunk_size))
        return hasher.hexdigest()[:16]
    except Exception as e:
        logging.error(f"Error calculating head hash for {filepath}: {e}")
        return ""

def get_breakpoint_prefix_hash(filepath: str, offset: int, chunk_size: int = 4096) -> str:
    """提取 [offset - chunk_size ~ offset] 区间内的字节块计算 MD5，用于校验断点交界处严密性。"""
    if not os.path.isfile(filepath):
        return ""
        
    file_size = os.path.getsize(filepath)
    if file_size == 0 or offset <= 0:
        return "EMPTY"
        
    start_pos = max(0, offset - chunk_size)
    read_len = offset - start_pos
    
    if read_len <= 0:
        return ""

    hasher = hashlib.md5()
    try:
        with open(filepath, "rb") as f:
            f.seek(start_pos)
            hasher.update(f.read(read_len))
        return hasher.hexdigest()[:16]
    except Exception as e:
        logging.error(f"Error calculating breakpoint prefix hash for {filepath} at offset {offset}: {e}")
        return ""

def get_sample_hash(filepath: str, chunk_size: int = 4096) -> str:
    """提取前 4KB + 后 4KB + 文件大小计算特征指纹，用于传输完成后最终双重校验。"""
    if not os.path.isfile(filepath):
        return ""
        
    file_size = os.path.getsize(filepath)
    if file_size == 0:
        return "EMPTY_0"
        
    hasher = hashlib.md5()
    hasher.update(str(file_size).encode('utf-8'))
    
    try:
        with open(filepath, "rb") as f:
            if file_size <= chunk_size * 2:
                hasher.update(f.read())
            else:
                hasher.update(f.read(chunk_size))
                f.seek(file_size - chunk_size)
                hasher.update(f.read(chunk_size))
        return hasher.hexdigest()[:16]
    except Exception as e:
        logging.error(f"Error calculating sample hash for {filepath}: {e}")
        return ""
