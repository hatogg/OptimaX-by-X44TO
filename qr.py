"""
OptimaX — крихітний генератор QR-кодів (ISO/IEC 18004): байтовий режим, рівень корекції M, версії 1–10 (до 213
байтів — для посилання на «Монітор на телефоні» цього з запасом). Без сторонніх бібліотек.

encode(text) -> список рядків матриці (True — темний модуль), без «тихої зони» навколо.
"""
from __future__ import annotations

# рівень M: версія -> (кількість кодових слів корекції на блок, [(блоків, слів даних у блоці), …])
BLOCKS_M = {
    1: (10, [(1, 16)]), 2: (16, [(1, 28)]), 3: (26, [(1, 44)]), 4: (18, [(2, 32)]), 5: (24, [(2, 43)]),
    6: (16, [(4, 27)]), 7: (18, [(4, 31)]), 8: (22, [(2, 38), (2, 39)]), 9: (22, [(3, 36), (2, 37)]),
    10: (26, [(4, 43), (1, 44)]),
}
ALIGN = {1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30], 6: [6, 34], 7: [6, 22, 38], 8: [6, 24, 42],
         9: [6, 26, 46], 10: [6, 28, 50]}
REMAINDER = {1: 0, 2: 7, 3: 7, 4: 7, 5: 7, 6: 7, 7: 0, 8: 0, 9: 0, 10: 0}
ECL_M = 0  # біти рівня корекції у форматі: L=1, M=0, Q=3, H=2


def _gf_mul(x: int, y: int) -> int:
    z = 0
    for i in reversed(range(8)):
        z = (z << 1) ^ ((z >> 7) * 0x11D)
        z ^= ((y >> i) & 1) * x
    return z


def _rs_divisor(degree: int) -> list:
    res = [0] * (degree - 1) + [1]
    root = 1
    for _ in range(degree):
        for j in range(degree):
            res[j] = _gf_mul(res[j], root)
            if j + 1 < degree:
                res[j] ^= res[j + 1]
        root = _gf_mul(root, 0x02)
    return res


def _rs_remainder(data: list, divisor: list) -> list:
    res = [0] * len(divisor)
    for b in data:
        factor = b ^ res.pop(0)
        res.append(0)
        for i, coef in enumerate(divisor):
            res[i] ^= _gf_mul(coef, factor)
    return res


def capacity(version: int) -> int:
    """Скільки байтів тексту вміщує версія (рівень M)."""
    ec, groups = BLOCKS_M[version]
    data_bits = sum(n * k for n, k in groups) * 8
    return (data_bits - 4 - (8 if version < 10 else 16)) // 8


def _codewords(data: bytes, version: int) -> list:
    ec, groups = BLOCKS_M[version]
    total_data = sum(n * k for n, k in groups)
    bits = []

    def put(val: int, n: int):
        bits.extend((val >> i) & 1 for i in reversed(range(n)))
    put(0b0100, 4)
    put(len(data), 8 if version < 10 else 16)
    for b in data:
        put(b, 8)
    put(0, min(4, total_data * 8 - len(bits)))
    put(0, (-len(bits)) % 8)
    words = [int("".join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8)]
    pad = 0xEC
    while len(words) < total_data:
        words.append(pad)
        pad ^= 0xEC ^ 0x11
    blocks, k = [], 0
    div = _rs_divisor(ec)
    for n, size in groups:
        for _ in range(n):
            blk = words[k:k + size]
            k += size
            blocks.append((blk, _rs_remainder(blk, div)))
    out = []
    for i in range(max(len(b[0]) for b in blocks)):
        out += [b[0][i] for b in blocks if i < len(b[0])]
    for i in range(ec):
        out += [b[1][i] for b in blocks]
    return out


class _Matrix:
    def __init__(self, version: int):
        self.v = version
        self.n = 17 + 4 * version
        self.m = [[False] * self.n for _ in range(self.n)]
        self.fn = [[False] * self.n for _ in range(self.n)]

    def set_fn(self, x: int, y: int, dark: bool):
        self.m[y][x] = dark
        self.fn[y][x] = True

    def function_patterns(self):
        n = self.n
        for i in range(n):
            self.set_fn(6, i, i % 2 == 0)
            self.set_fn(i, 6, i % 2 == 0)
        for cx, cy in ((3, 3), (n - 4, 3), (3, n - 4)):
            for dy in range(-4, 5):
                for dx in range(-4, 5):
                    x, y = cx + dx, cy + dy
                    if 0 <= x < n and 0 <= y < n:
                        self.set_fn(x, y, max(abs(dx), abs(dy)) not in (2, 4))
        pos = ALIGN[self.v]
        last = len(pos) - 1
        for i, ax in enumerate(pos):
            for j, ay in enumerate(pos):
                if (i, j) in ((0, 0), (0, last), (last, 0)):
                    continue
                for dy in range(-2, 3):
                    for dx in range(-2, 3):
                        self.set_fn(ax + dx, ay + dy, max(abs(dx), abs(dy)) != 1)
        self.format_bits(0)
        if self.v >= 7:
            rem = self.v
            for _ in range(12):
                rem = (rem << 1) ^ ((rem >> 11) * 0x1F25)
            bits = self.v << 12 | rem
            for i in range(18):
                bit = bool((bits >> i) & 1)
                a, b = n - 11 + i % 3, i // 3
                self.set_fn(a, b, bit)
                self.set_fn(b, a, bit)

    def format_bits(self, mask: int):
        n = self.n
        data = ECL_M << 3 | mask
        rem = data
        for _ in range(10):
            rem = (rem << 1) ^ ((rem >> 9) * 0x537)
        bits = (data << 10 | rem) ^ 0x5412

        def bit(i):
            return bool((bits >> i) & 1)
        for i in range(6):
            self.set_fn(8, i, bit(i))
        self.set_fn(8, 7, bit(6))
        self.set_fn(8, 8, bit(7))
        self.set_fn(7, 8, bit(8))
        for i in range(9, 15):
            self.set_fn(14 - i, 8, bit(i))
        for i in range(8):
            self.set_fn(n - 1 - i, 8, bit(i))
        for i in range(8, 15):
            self.set_fn(8, n - 15 + i, bit(i))
        self.set_fn(8, n - 8, True)  # завжди темний модуль

    def place(self, words: list, remainder: int):
        n = self.n
        bits = [(w >> (7 - k)) & 1 for w in words for k in range(8)] + [0] * remainder
        i = 0
        right = n - 1
        while right >= 1:
            if right == 6:
                right = 5
            for vert in range(n):
                for j in range(2):
                    x = right - j
                    upward = ((right + 1) & 2) == 0
                    y = n - 1 - vert if upward else vert
                    if not self.fn[y][x] and i < len(bits):
                        self.m[y][x] = bool(bits[i])
                        i += 1
            right -= 2

    def apply_mask(self, mask: int):
        for y in range(self.n):
            for x in range(self.n):
                if self.fn[y][x]:
                    continue
                if mask == 0:
                    inv = (x + y) % 2 == 0
                elif mask == 1:
                    inv = y % 2 == 0
                elif mask == 2:
                    inv = x % 3 == 0
                elif mask == 3:
                    inv = (x + y) % 3 == 0
                elif mask == 4:
                    inv = (x // 3 + y // 2) % 2 == 0
                elif mask == 5:
                    inv = x * y % 2 + x * y % 3 == 0
                elif mask == 6:
                    inv = (x * y % 2 + x * y % 3) % 2 == 0
                else:
                    inv = ((x + y) % 2 + x * y % 3) % 2 == 0
                if inv:
                    self.m[y][x] = not self.m[y][x]

    def penalty(self) -> int:
        n, m = self.n, self.m
        score = 0
        lines = [m[y] for y in range(n)] + [[m[y][x] for y in range(n)] for x in range(n)]
        pat1 = [True, False, True, True, True, False, True, False, False, False, False]
        pat2 = pat1[::-1]
        for line in lines:
            run, prev = 0, None
            for v in line:
                if v == prev:
                    run += 1
                else:
                    if run >= 5:
                        score += 3 + run - 5
                    run, prev = 1, v
            if run >= 5:
                score += 3 + run - 5
            for i in range(n - 10):
                seg = line[i:i + 11]
                if seg == pat1 or seg == pat2:
                    score += 40
        for y in range(n - 1):
            for x in range(n - 1):
                c = m[y][x]
                if c == m[y][x + 1] == m[y + 1][x] == m[y + 1][x + 1]:
                    score += 3
        dark = sum(sum(r) for r in m)
        k = abs(dark * 20 - n * n * 10) // (n * n)  # кожні 5% відхилення від 50%
        return score + k * 10


def encode(text: str) -> list:
    data = text.encode("utf-8")
    version = next((v for v in BLOCKS_M if capacity(v) >= len(data)), None)
    if version is None:
        raise ValueError("text is too long for a version 1-10 QR code")
    words = _codewords(data, version)
    best, best_score = None, None
    for mask in range(8):
        qm = _Matrix(version)
        qm.function_patterns()
        qm.place(words, REMAINDER[version])
        qm.apply_mask(mask)
        qm.format_bits(mask)
        s = qm.penalty()
        if best_score is None or s < best_score:
            best, best_score = qm, s
    return best.m
