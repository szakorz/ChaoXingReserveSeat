from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import base64
import hashlib
from uuid import uuid1

def AES_Encrypt(data: str) -> str:
    key = b"u2oh6Vu^HWe4_AES"
    iv = b"u2oh6Vu^HWe4_AES"
    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(data.encode("utf-8")) + padder.finalize()
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    encrypted_data = encryptor.update(padded_data) + encryptor.finalize()
    return base64.b64encode(encrypted_data).decode("utf-8")

def enc(submit_info: dict) -> str:
    # 旧版备用签名逻辑，保留以兼容
    parts = [f"[{k}={str(submit_info[k])}]" for k in sorted(submit_info.keys())]
    parts.append("[%sd`~7^/>N4!Q#){''}]")
    seq = "".join(parts)
    return hashlib.md5(seq.encode("utf-8")).hexdigest()

def generate_captcha_key(timestamp: int):
    captcha_key = hashlib.md5((str(timestamp) + str(uuid1()))。encode("utf-8")).hexdigest()
    encoded_timestamp = hashlib.md5(
        (str(timestamp) + "42sxgHoTPTKbt0uZxPJ7ssOvtXr3ZgZ1" + "slide" + captcha_key).encode("utf-8")
    ).hexdigest() + ":" + str(int(timestamp) + 0x493e0)
    return [captcha_key, encoded_timestamp]

# —— 新版参数签名：verify_param —— #
def _sort_dict_by_keys(d: dict) -> dict:
    return {k: d[k] for k in sorted(d.keys())}

def verify_param(params: dict, algorithm_value: str) -> str:
    """
    将提交表单参数按 key 排序，拼接为 [key=value]... 再追加 [algorithm_value]，取 MD5
    params 示例：
      {'roomId':..., 'startTime':..., 'endTime':..., 'day':..., 'seatNum':..., 'captcha':..., 'token':..., 'type':'1','verifyData':'1'}
    """
    parts = [f"[{k}={str(v)}]" for k, v in _sort_dict_by_keys(params).items()]
    parts.append(f"[{algorithm_value}]")
    s = "".join(parts)
    return hashlib.md5(s.encode("utf-8")).hexdigest()

