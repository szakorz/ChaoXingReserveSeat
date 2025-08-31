from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import base64
from hashlib import md5
import random
from uuid import uuid1
import hashlib

def AES_Encrypt(data):
    key = b"u2oh6Vu^HWe4_AES"  # Convert to bytes
    iv = b"u2oh6Vu^HWe4_AES"  # Convert to bytes
    padder = padding.PKCS7(128)。padder()
    padded_data = padder.update(data.encode('utf-8')) + padder.finalize()
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    encrypted_data = encryptor.update(padded_data) + encryptor.finalize()
    encoded_data = base64.b64encode(encrypted_data).decode('utf-8')
    return encoded_data

def enc(submit_info: dict):
    def sort_keys(dict_obj):
        keys = list(dict_obj.keys())
        keys.sort()
        return keys

    def resort(dict_obj):
        keys = sort_keys(dict_obj)
        new = {}
        for key 在 keys:
            new[key] = str(dict_obj[key])
        return new

    def add(a, b):
        return a + b

    processed_info = resort(submit_info)
    needed = [add(add('[', key)， '=' + value) + ']' for key, value in processed_info.items()]
    pattern = "%sd`~7^/>N4!Q#){''"
    needed.append(add('[', pattern) + ']')
    seq = ''.join(needed)
    return md5(seq.encode("utf-8")).hexdigest()

def generate_captcha_key(timestamp: int):
    captcha_key = md5((str(timestamp) + str(uuid1())).encode("utf-8")).hexdigest()
    encoded_timestamp = md5(
        (str(timestamp) + "42sxgHoTPTKbt0uZxPJ7ssOvtXr3ZgZ1" + "slide" + captcha_key).encode("utf-8")
    ).hexdigest() + ":" + str(int(timestamp) + 0x493e0)
    return [captcha_key, encoded_timestamp]

# 下面这两个是新版参数签名所需的新增方法（上游已改为用 verify_param 计算 enc）
def sort_dict_by_keys(dictionary):
    """将字典按键排序并返回新字典"""
    sorted_keys = sorted(dictionary.keys())
    sorted_dict = {key: dictionary[key] for key in sorted_keys}
    return sorted_dict

def verify_param(params, algorithm_value):
    """
    生成参数的MD5验证哈希值
    :param params: dict 例如 {'roomId':..., 'startTime':..., 'endTime':..., 'day':..., 'seatNum':..., 'captcha':..., 'token':..., 'type': '1', 'verifyData': '1'}
    :param algorithm_value: str 页面隐藏字段中的 value，用于拼接
    :return: str md5 十六进制字符串
    """
    # 按 key 排序并拼接为 [key=value] 的形式
    sorted_params = sort_dict_by_keys(params)
    hash_list = []
    for key, value in sorted_params.items():
        hash_list.append(f"[{key}={str(value)}]")
    # 追加算法值
    hash_list.append(f"[{algorithm_value}]")
    hash_string = "".join(hash_list)
    md5_hash = hashlib.md5(hash_string.encode("utf-8")).hexdigest()
    return md5_hash
