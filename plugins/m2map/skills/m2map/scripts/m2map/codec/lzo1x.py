"""Pure-Python LZO1X-1 compressor + decompressor (minilzo compatible).

`server_attr` blocks are written by the game tools with ``lzo1x_1_compress`` and
read with ``lzo1x_decompress_safe`` (see reference/mapformat/server-attr.md and
m2dev-server-src ``lzo_manager.cpp:24,32-40``).  There is no ``python-lzo``
module in this environment, so the codec is implemented here.

Control flow of :func:`decompress` is a port of the minilzo
``lzo1x_decompress`` state machine (LZO 2.10 ``lzo1x_d.ch``), cross-checked
against the JavaScript port in
``<MAPFORGE>/index.html:1069-1096``.

:func:`compress` emits a standard LZO1X bitstream (the same instruction set the
minilzo encoder uses: M2 / M3 / M4 matches, literal runs, EOF marker).  It is a
greedy single-slot-hash encoder, so its *output bytes* are not guaranteed to be
identical to a particular minilzo build's output -- only the decompressed data
is.  Do not use it to try to reproduce a shipped `server_attr` byte-for-byte;
use :class:`m2map.codec.server_attr.ServerAttr` block preservation for that.

Stream reference
----------------
==============  ==========================================================
literal run     first byte >17 at stream start: count = b-17;
                else code 0..15 (count = 3+t, t==0 -> 255-extended);
                counts 1..3 after a match ride in the low 2 bits of the
                match's second-to-last byte
M2 match        b >= 64: len 3..8, distance 1..2048   (2 bytes)
M3 match        b in 32..63: len 3..33+, distance 1..16384 (3+ bytes)
M4 match        b in 16..31: len 3..9+, distance 16385..49151 (3+ bytes)
M1 match        b in 0..15 after a match: len 2, distance 1..1024
EOF             0x11 0x00 0x00 (M4 marker, zero offset)
==============  ==========================================================
"""

from __future__ import annotations

__all__ = [
    "compress",
    "decompress",
    "worst_case_size",
    "LZOError",
    "M1_MAX_OFFSET",
    "M2_MAX_OFFSET",
    "M3_MAX_OFFSET",
    "M4_MAX_OFFSET",
]


class LZOError(Exception):
    """Raised on a malformed / truncated LZO1X stream."""


# --- LZO1X instruction-set constants (minilzo config1x.h) -------------------
M1_MAX_OFFSET = 0x0400
M2_MAX_OFFSET = 0x0800
M3_MAX_OFFSET = 0x4000
M4_MAX_OFFSET = 0xBFFF

M2_MIN_LEN, M2_MAX_LEN = 3, 8
M3_MAX_LEN = 33
M4_MAX_LEN = 9

M3_MARKER = 32
M4_MARKER = 16


def worst_case_size(n: int) -> int:
    """Output-buffer bound used by the server (``lzo_manager.cpp:42-45``)."""
    return n + (n >> 4) + 67


# ---------------------------------------------------------------------------
# decompressor
# ---------------------------------------------------------------------------
def decompress(src, out_len=None) -> bytes:
    """Decode an LZO1X stream.

    Parameters
    ----------
    src : bytes-like
        Compressed stream (ends with the 0x11 0x00 0x00 EOF marker).
    out_len : int, optional
        Expected output size.  Checked when given (server_attr blocks must be
        exactly 65536 bytes: ``sectree_manager.cpp:450-548``).
    """
    src = bytes(src)
    n = len(src)
    out = bytearray()
    ip = 0

    def _byte():
        nonlocal ip
        if ip >= n:
            raise LZOError("input overrun")
        b = src[ip]
        ip += 1
        return b

    def _lit(count):
        nonlocal ip
        if ip + count > n:
            raise LZOError("input overrun in literal run")
        out.extend(src[ip:ip + count])
        ip += count

    def _copy_match(dist, length):
        if dist <= 0 or dist > len(out):
            raise LZOError("match distance %d out of range" % dist)
        pos = len(out) - dist
        if dist >= length:
            out.extend(out[pos:pos + length])
        else:  # overlapping run - the engine copies byte by byte
            for _ in range(length):
                out.append(out[pos])
                pos += 1

    def _ext(base):
        """255-chunk length extension: each zero byte adds 255."""
        t = 0
        while True:
            b = _byte()
            if b:
                return t + base + b
            t += 255
            if t > (1 << 26):
                raise LZOError("length extension runaway")

    state = "top"
    t = 0

    # --- stream prologue (minilzo: `if (*ip > 17)`) ---
    if n and src[0] > 17:
        t = _byte() - 17
        if t < 4:
            state = "match_next"
        else:
            _lit(t)
            state = "first_literal_run"

    while True:
        if state == "top":
            t = _byte()
            if t >= 16:
                state = "match"
                continue
            if t == 0:
                t = _ext(15)
            _lit(t + 3)
            state = "first_literal_run"

        elif state == "first_literal_run":
            t = _byte()
            if t >= 16:
                state = "match"
                continue
            # M1 in this position: len 3, distance 2049..3072
            dist = (1 + M2_MAX_OFFSET) + (t >> 2) + (_byte() << 2)
            _copy_match(dist, 3)
            state = "match_done"

        elif state == "match":
            if t >= 64:  # M2
                dist = 1 + ((t >> 2) & 7) + (_byte() << 3)
                _copy_match(dist, (t >> 5) - 1 + 2)
            elif t >= 32:  # M3
                length = t & 31
                length = _ext(31) if length == 0 else length
                if ip + 1 >= n:
                    raise LZOError("input overrun in M3 offset")
                dist = 1 + (src[ip] >> 2) + (src[ip + 1] << 6)
                ip += 2
                _copy_match(dist, length + 2)
            elif t >= 16:  # M4 (or EOF)
                dist_hi = (t & 8) << 11
                length = t & 7
                length = _ext(7) if length == 0 else length
                if ip + 1 >= n:
                    raise LZOError("input overrun in M4 offset")
                dist = dist_hi + (src[ip] >> 2) + (src[ip + 1] << 6)
                ip += 2
                if dist == 0:  # m_pos == op -> end of stream
                    break
                _copy_match(dist + 0x4000, length + 2)
            else:  # M1
                dist = 1 + (t >> 2) + (_byte() << 2)
                _copy_match(dist, 2)
            state = "match_done"

        elif state == "match_done":
            t = src[ip - 2] & 3
            if t == 0:
                state = "top"
                continue
            state = "match_next"

        elif state == "match_next":
            _lit(t)
            t = _byte()
            state = "match"

    if out_len is not None and len(out) != out_len:
        raise LZOError("decompressed %d bytes, expected %d" % (len(out), out_len))
    return bytes(out)


# ---------------------------------------------------------------------------
# compressor
# ---------------------------------------------------------------------------
def _match_len(src, m, ip, end):
    """Common-prefix length of src[m:] and src[ip:], capped at `end`.

    Overlapping matches (m_len > distance) are legal in LZO -- the decoder
    copies byte by byte -- and comparing the *input* buffer against itself has
    exactly that semantics.
    """
    limit = end - ip
    k = 0
    step = 16
    while k < limit:
        c = step if k + step <= limit else limit - k
        if src[m + k:m + k + c] == src[ip + k:ip + k + c]:
            k += c
            if step < 4096:
                step *= 2
        else:
            for j in range(c):
                if src[m + k + j] != src[ip + k + j]:
                    return k + j
            k += c  # not reached
    return k


def _emit_literals(out, src, ii, ip):
    t = ip - ii
    if t == 0:
        return
    if not out and t <= 238:
        out.append(17 + t)
    elif t <= 3:
        out[-2] |= t          # rides in the previous match's low 2 bits
    elif t <= 18:
        out.append(t - 3)
    else:
        tt = t - 18
        out.append(0)
        while tt > 255:
            tt -= 255
            out.append(0)
        out.append(tt)
    out.extend(src[ii:ip])


def _emit_match(out, m_off, m_len):
    if m_len <= M2_MAX_LEN and m_off <= M2_MAX_OFFSET:
        m_off -= 1
        out.append(((m_len - 1) << 5) | ((m_off & 7) << 2))
        out.append(m_off >> 3)
    elif m_off <= M3_MAX_OFFSET:
        m_off -= 1
        if m_len <= M3_MAX_LEN:
            out.append(M3_MARKER | (m_len - 2))
        else:
            m_len -= M3_MAX_LEN
            out.append(M3_MARKER)
            while m_len > 255:
                m_len -= 255
                out.append(0)
            out.append(m_len)
        out.append((m_off << 2) & 0xFF)
        out.append((m_off >> 6) & 0xFF)
    else:
        if m_off > M4_MAX_OFFSET:
            raise LZOError("match offset %d exceeds LZO1X limit" % m_off)
        m_off -= 0x4000
        marker = M4_MARKER | ((m_off & 0x4000) >> 11)
        if m_len <= M4_MAX_LEN:
            out.append(marker | (m_len - 2))
        else:
            m_len -= M4_MAX_LEN
            out.append(marker)
            while m_len > 255:
                m_len -= 255
                out.append(0)
            out.append(m_len)
        out.append((m_off << 2) & 0xFF)
        out.append((m_off >> 6) & 0xFF)


def compress(src) -> bytes:
    """LZO1X-1 compress.  Output decodes with any minilzo ``lzo1x_decompress*``."""
    src = bytes(src)
    n = len(src)
    out = bytearray()
    ii = 0
    ip = 0
    # minilzo keeps the last 20 bytes out of the match search; the same tail
    # margin keeps the trailing-literal shape real decoders expect.
    ip_end = n - 20
    table = {}

    while ip < ip_end:
        key = src[ip:ip + 3]
        m = table.get(key, -1)
        table[key] = ip
        if m < 0 or ip - m > M4_MAX_OFFSET:
            ip += 1
            continue
        m_len = _match_len(src, m, ip, n)
        if m_len < 3:
            ip += 1
            continue
        _emit_literals(out, src, ii, ip)
        _emit_match(out, ip - m, m_len)
        ip += m_len
        ii = ip

    _emit_literals(out, src, ii, n)
    out += b"\x11\x00\x00"
    return bytes(out)
