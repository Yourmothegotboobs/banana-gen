import struct
import zlib


def _xor_bytes(data: bytes, key: int = 0x5A) -> bytes:
    return bytes((b ^ key) for b in data)


def embed_png_private_chunk(png_bytes: bytes, chunk_type: bytes, payload: bytes) -> bytes:
    if not png_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return png_bytes
    chunk_type = chunk_type[:4]
    payload_crc = zlib.crc32(chunk_type)
    payload_crc = zlib.crc32(payload, payload_crc) & 0xFFFFFFFF
    chunk = struct.pack(
        ">I4s%dsI" % len(payload),
        len(payload), chunk_type, payload, payload_crc,
    )
    # 在 IEND 前插入
    iend = png_bytes.rfind(b"IEND")
    if iend <= 0:
        return png_bytes + chunk
    # IEND 记录从长度字段开始，需回溯 4 字节长度 + 4 类型
    start = iend - 4
    return png_bytes[:start] + chunk + png_bytes[start:]


def embed_info_to_png(png_bytes: bytes, info: dict) -> bytes:
    import json
    raw = json.dumps(info, ensure_ascii=False).encode("utf-8")
    obf = _xor_bytes(raw)
    return embed_png_private_chunk(png_bytes, b"prIv", obf)


def extract_info_from_png(png_bytes: bytes) -> dict:
    try:
        data = png_bytes
        pos = 8  # 跳过签名
        while pos + 8 <= len(data):
            length = struct.unpack(">I", data[pos:pos+4])[0]
            ctype = data[pos+4:pos+8]
            if ctype == b"prIv":
                payload = data[pos+8:pos+8+length]
                raw = _xor_bytes(payload)
                import json
                return json.loads(raw.decode("utf-8"))
            pos += 12 + length  # len + type + data + crc
    except Exception:
        pass
    return {}


