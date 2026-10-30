"""
OptimaX — власний тест відеокарти: важка 3D-сцена (raymarching у фрагментному шейдері), бали, FPS, 1% low,
стрес-тест із перевіркою стабільності та датчиками NVIDIA.

Тест запускається окремим процесом (OptimaX.exe --gpu-bench …): якщо драйвер відеокарти «впаде» під
навантаженням, основна програма залишиться живою й покаже, що сталося.

Будова:
    SHADER_FS      — сцена; той самий код компілюється як GLSL 330 core (Windows) і GLSL ES 300 (перевірка)
    GL             — тонка обгортка над функціями OpenGL (адреси дає Qt або EGL)
    Renderer       — рендер сцени в кадр потрібної роздільності, контрольний кадр для перевірки стабільності
    Nvml           — температура, частоти, споживання, причини скидання частот (лише NVIDIA)
    run_child()    — вікно тесту (PyQt6, QOpenGLWindow) — працює в окремому процесі
    start()/Run    — запуск із програми та читання прогресу
"""
from __future__ import annotations

import ctypes
import hashlib
import json
import math
import os
import subprocess
import sys
import tempfile
import time

import engine as E
from i18n import tr

# ───────────────────────── налаштування тесту ─────────────────────────
PRESETS = {
    "1080p": (1920, 1080),
    "1440p": (2560, 1440),
    "4k": (3840, 2160),
}
QUALITY = dict(steps=128, shadow=32, ao=5, refl=72)  # однаковий для всіх пресетів — бали порівнювані
QUALITIES = {"bench": QUALITY, "ab": dict(steps=72, shadow=16, ao=3, refl=40)}
PRESETS["ab"] = (1280, 720)  # заміри розумної оптимізації: легша сцена — чутливіша до процесора й планувальника
AB_SECONDS = 30
if os.environ.get("OPTIMAX_BENCH_FAST"):  # для автоматичних тестів (CI): крихітний кадр і кілька секунд
    for _k in list(PRESETS):
        PRESETS[_k] = (320, 180)
BENCH_SECONDS = 60
WARMUP_SECONDS = 4
CHECK_EVERY = 10.0  # стрес-тест: контрольний кадр раз на 10 секунд
CHECK_SIZE = (480, 270)
CHECK_TIME = 7.25  # момент анімації для контрольного кадру
SCORE_K = 100  # бали = середній FPS × 100
# ревізія циклу кадрів: бали різних ревізій не порівнюються (2 — FPS більше не впирається в частоту монітора)
BENCH_REV = 2
STRESS_MINUTES = (5, 15, 30, 60)

# ───────────────────────── шейдер ─────────────────────────
SHADER_VS = """
void main() {
    vec2 p = vec2(float((gl_VertexID << 1) & 2), float(gl_VertexID & 2));
    gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);
}
"""

SHADER_FS = """
uniform vec2 uRes;
uniform float uTime;
uniform int uSteps;
uniform int uShadow;
uniform int uAO;
uniform int uRefl;
out vec4 fragColor;

const float PI = 3.14159265;
const float CELL = 1.7;
const float MAXH = 4.9;
const float ARENA = 7.4;

float hash12(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}
mat2 rot(float a) { float c = cos(a), s = sin(a); return mat2(c, -s, s, c); }
float sdBox(vec3 p, vec3 b) {
    vec3 q = abs(p) - b;
    return length(max(q, 0.0)) + min(max(q.x, max(q.y, q.z)), 0.0);
}
float sdTorus(vec3 p, vec2 t) { return length(vec2(length(p.xz) - t.x, p.y)) - t.y; }

float pillarHeight(vec2 id) {
    float r = hash12(id);
    float ring = length((id + 0.5) * CELL);
    float h = 0.3 + 4.1 * r * r * smoothstep(ARENA, ARENA + 9.0, ring);
    return h + 0.3 * sin(uTime * 1.1 + r * 6.2831) * step(0.55, r);
}

// повертає відстань; m — матеріал: 1 підлога, 2 колона, 3 знак X, 4 кільце, 5 сфери
float map(vec3 p, out float m, out vec2 cid) {
    m = 1.0;
    cid = vec2(0.0);
    float d = p.y;

    // колони в клітинках сітки
    vec2 id = floor(p.xz / CELL);
    vec2 q = (fract(p.xz / CELL) - 0.5) * CELL;
    float ring = length((id + 0.5) * CELL);
    float bound = min(0.5 * CELL - abs(q.x), 0.5 * CELL - abs(q.y)) + 0.04;
    float dp = bound;
    if (ring > ARENA) {
        float h = pillarHeight(id);
        dp = min(sdBox(vec3(q.x, p.y - 0.5 * h, q.y), vec3(0.46, 0.5 * h, 0.46)) - 0.06, bound);
    }
    dp = max(dp, p.y - MAXH);
    if (dp < d) { d = dp; m = 2.0; cid = id; }

    // знак X у центрі
    vec3 c = p - vec3(0.0, 2.25 + 0.18 * sin(uTime * 1.6), 0.0);
    c.xz = rot(uTime * 0.55) * c.xz;
    vec2 a1 = rot(PI * 0.25) * c.xy;
    vec2 a2 = rot(-PI * 0.25) * c.xy;
    float x = min(sdBox(vec3(a1, c.z), vec3(1.55, 0.27, 0.27)), sdBox(vec3(a2, c.z), vec3(1.55, 0.27, 0.27))) - 0.08;
    if (x < d) { d = x; m = 3.0; }

    // кільце навколо знака
    vec3 t = p - vec3(0.0, 2.25, 0.0);
    t.yz = rot(0.35 + 0.25 * sin(uTime * 0.7)) * t.yz;
    t.xy = rot(uTime * 0.3) * t.xy;
    float tor = sdTorus(t, vec2(2.65, 0.07));
    if (tor < d) { d = tor; m = 4.0; }

    // дзеркальні сфери на орбіті
    vec3 s = p - vec3(0.0, 1.0, 0.0);
    s.xz = rot(-uTime * 0.8) * s.xz;
    float an = 2.0 * PI / 6.0;
    float sec = floor(atan(s.z, s.x) / an + 0.5);
    s.xz = rot(-sec * an) * s.xz;
    s.y -= 0.35 * sin(uTime * 2.0 + sec * 1.7);
    float sp = length(s - vec3(3.6, 0.0, 0.0)) - 0.42;
    if (sp < d) { d = sp; m = 5.0; }
    return d;
}

float mapD(vec3 p) { float m; vec2 c; return map(p, m, c); }

vec3 normal(vec3 p) {
    vec2 e = vec2(0.0015, 0.0);
    return normalize(vec3(mapD(p + e.xyy) - mapD(p - e.xyy), mapD(p + e.yxy) - mapD(p - e.yxy),
                          mapD(p + e.yyx) - mapD(p - e.yyx)));
}

float softShadow(vec3 ro, vec3 rd) {
    float res = 1.0, t = 0.03;
    for (int i = 0; i < uShadow; i++) {
        float h = mapD(ro + rd * t);
        res = min(res, 10.0 * h / t);
        t += clamp(h, 0.03, 0.6);
        if (res < 0.002 || t > 18.0) break;
    }
    return clamp(res, 0.0, 1.0);
}

float ambientOcc(vec3 p, vec3 n) {
    float occ = 0.0, w = 1.0;
    for (int i = 1; i <= uAO; i++) {
        float h = 0.06 + 0.13 * float(i);
        occ += w * (h - mapD(p + n * h));
        w *= 0.72;
    }
    return clamp(1.0 - 1.6 * occ, 0.0, 1.0);
}

vec3 palette(float k) {
    vec3 a = mix(vec3(0.1, 0.65, 1.0), vec3(0.3, 0.42, 1.0), smoothstep(0.0, 0.45, k));
    a = mix(a, vec3(0.62, 0.3, 1.0), smoothstep(0.45, 0.8, k));
    return mix(a, vec3(1.0, 0.28, 0.7), smoothstep(0.85, 1.0, k));
}

// трасування: t — відстань, m — матеріал, glow — світіння від знака
float trace(vec3 ro, vec3 rd, int steps, out float m, out vec2 cid, out float glow) {
    float t = 0.0;
    glow = 0.0;
    m = 0.0;
    for (int i = 0; i < steps; i++) {
        vec3 p = ro + rd * t;
        float mm; vec2 cc;
        float d = map(p, mm, cc);
        vec3 c = p - vec3(0.0, 2.25, 0.0);
        glow += 0.03 * exp(-0.5 * dot(c, c));
        if (d < 0.0012 * t + 0.0008) { m = mm; cid = cc; return t; }
        t += d * 0.92;
        if (t > 60.0) break;
    }
    m = 0.0;
    return t;
}

vec3 sky(vec3 rd) {
    vec3 col = mix(vec3(0.006, 0.007, 0.016), vec3(0.025, 0.018, 0.06), pow(max(rd.y, 0.0), 0.6));
    col += vec3(0.3, 0.14, 0.55) * pow(max(0.0, 1.0 - abs(rd.y) * 5.0), 8.0) * 0.18;
    return col;
}

vec3 shade(vec3 p, vec3 rd, float m, vec2 cid, bool full, out float refl) {
    vec3 n = normal(p);
    vec3 sun = normalize(vec3(-0.55, 0.75, -0.35));
    float dif = max(dot(n, sun), 0.0);
    float sha = full ? softShadow(p + n * 0.01, sun) : 1.0;
    float occ = full ? ambientOcc(p, n) : 0.8;
    vec3 h = normalize(sun - rd);
    float spe = pow(max(dot(n, h), 0.0), 48.0);
    vec3 base = vec3(0.05);
    vec3 emi = vec3(0.0);
    refl = 0.0;
    if (m < 1.5) {
        // підлога: темний глянець і неонова сітка
        vec2 g = abs(fract(p.xz / CELL + 0.5) - 0.5) * CELL;
        float line = smoothstep(0.022, 0.0, min(g.x, g.y));
        float pulse = 0.5 + 0.5 * sin(length(p.xz) * 1.4 - uTime * 2.4);
        base = vec3(0.018, 0.02, 0.03);
        emi = palette(0.35 + 0.3 * sin(length(p.xz) * 0.2)) * line * (0.08 + 0.55 * pulse * pulse)
              * exp(-0.06 * length(p.xz));
        refl = 0.6;
    } else if (m < 2.5) {
        float r = hash12(cid);
        vec2 q = p.xz - (cid + 0.5) * CELL;
        base = mix(vec3(0.03, 0.033, 0.045), vec3(0.06, 0.06, 0.08), r);
        float band = smoothstep(0.455, 0.49, abs(fract(p.y * 0.7 - uTime * 0.3 + r * 3.0) - 0.5));
        float edge = smoothstep(0.43, 0.5, max(abs(q.x), abs(q.y))) * step(0.6, n.y);
        float lit = step(0.3, r);
        emi = palette(r) * (band * 2.2 * lit + edge * 1.6 * step(0.15, r));
        refl = 0.18;
    } else if (m < 3.5) {
        base = vec3(0.015, 0.018, 0.04);
        vec3 c = p - vec3(0.0, 2.25, 0.0);
        float k = clamp(0.5 + 0.3 * (c.x - c.y), 0.0, 1.0);
        float fr = pow(1.0 - max(dot(n, -rd), 0.0), 2.5);
        emi = mix(vec3(0.12, 0.38, 1.0), vec3(0.55, 0.2, 1.0), k) * (0.5 + 2.2 * fr);
        refl = 0.35;
    } else if (m < 4.5) {
        base = vec3(0.35, 0.36, 0.42);
        emi = vec3(0.75, 0.4, 1.0) * 0.5;
        refl = 0.55;
    } else {
        base = vec3(0.03);
        refl = 0.92;
    }
    vec3 amb = vec3(0.05, 0.055, 0.1) * (0.6 + 0.4 * n.y);
    vec3 col = base * (amb * occ + vec3(1.0, 0.93, 0.85) * dif * sha * 1.1);
    col += spe * sha * vec3(0.9, 0.85, 1.0) * (0.25 + refl);
    // відблиск від знака X
    vec3 toX = vec3(0.0, 2.25, 0.0) - p;
    float lx = length(toX);
    col += base * vec3(0.3, 0.38, 1.0) * max(dot(n, toX / lx), 0.0) * 6.0 / (1.0 + lx * lx * 0.3) * occ;
    return col + emi;
}

vec3 aces(vec3 x) {
    return clamp((x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14), 0.0, 1.0);
}

void main() {
    vec2 uv = (2.0 * gl_FragCoord.xy - uRes) / uRes.y;
    float tt = uTime;
    float ang = 0.6 + tt * 0.14;
    float rad = 6.4 + 0.8 * sin(tt * 0.21);
    vec3 ro = vec3(rad * cos(ang), 1.55 + 0.8 * sin(tt * 0.27), rad * sin(ang));
    vec3 ta = vec3(0.0, 2.0, 0.0);
    vec3 ww = normalize(ta - ro);
    vec3 uu = normalize(cross(ww, vec3(0.0, 1.0, 0.0)));
    vec3 vv = cross(uu, ww);
    vec3 rd = normalize(uv.x * uu + uv.y * vv + 1.7 * ww);

    float m, glow;
    vec2 cid;
    float t = trace(ro, rd, uSteps, m, cid, glow);
    vec3 col = sky(rd);
    if (m > 0.5) {
        vec3 p = ro + rd * t;
        float refl;
        col = shade(p, rd, m, cid, true, refl);
        if (refl > 0.0 && uRefl > 0) {
            vec3 n = normal(p);
            vec3 r = reflect(rd, n);
            float fre = refl * (0.35 + 0.65 * pow(1.0 - max(dot(n, -rd), 0.0), 4.0));
            float m2, g2;
            vec2 c2;
            vec3 ro2 = p + n * 0.02;
            float t2 = trace(ro2, r, uRefl, m2, c2, g2);
            vec3 rc = sky(r);
            if (m2 > 0.5) {
                float rr;
                rc = shade(ro2 + r * t2, r, m2, c2, false, rr);
                rc = mix(rc, vec3(0.02, 0.02, 0.05), 1.0 - exp(-0.02 * t2));
            }
            rc += vec3(0.3, 0.35, 1.0) * g2 * 0.06;
            col = mix(col, rc, clamp(fre, 0.0, 1.0));
        }
        col = mix(col, vec3(0.012, 0.01, 0.03), 1.0 - exp(-0.0011 * t * t));
    }
    col += mix(vec3(0.2, 0.42, 1.0), vec3(0.6, 0.28, 1.0), 0.5 + 0.5 * sin(tt * 0.8)) * glow * 0.07;
    col = aces(col * 0.95);
    col = pow(col, vec3(0.4545));
    vec2 q = gl_FragCoord.xy / uRes;
    col *= 0.55 + 0.45 * pow(16.0 * q.x * q.y * (1.0 - q.x) * (1.0 - q.y), 0.18);
    fragColor = vec4(col, 1.0);
}
"""

HEADER_DESKTOP = "#version 330 core\n"
HEADER_ES = "#version 300 es\nprecision highp float;\nprecision highp int;\n"


def shader_sources(es: bool = False) -> tuple:
    head = HEADER_ES if es else HEADER_DESKTOP
    return head + SHADER_VS, head + SHADER_FS


# ───────────────────────── OpenGL ─────────────────────────
GL_TRIANGLES = 0x0004
GL_COLOR_BUFFER_BIT = 0x4000
GL_VERTEX_SHADER, GL_FRAGMENT_SHADER = 0x8B31, 0x8B30
GL_COMPILE_STATUS, GL_LINK_STATUS, GL_INFO_LOG_LENGTH = 0x8B81, 0x8B82, 0x8B84
GL_FRAMEBUFFER, GL_READ_FRAMEBUFFER, GL_DRAW_FRAMEBUFFER = 0x8D40, 0x8CA8, 0x8CA9
GL_COLOR_ATTACHMENT0, GL_FRAMEBUFFER_COMPLETE = 0x8CE0, 0x8CD5
GL_TEXTURE_2D, GL_RGBA8, GL_RGBA, GL_UNSIGNED_BYTE = 0x0DE1, 0x8058, 0x1908, 0x1401
GL_TEXTURE_MIN_FILTER, GL_TEXTURE_MAG_FILTER, GL_LINEAR, GL_NEAREST = 0x2801, 0x2800, 0x2601, 0x2600
GL_BLEND, GL_DEPTH_TEST, GL_SCISSOR_TEST, GL_STENCIL_TEST, GL_CULL_FACE = 0x0BE2, 0x0B71, 0x0C11, 0x0B90, 0x0B44
GL_PACK_ALIGNMENT = 0x0D05
GL_RENDERER, GL_VERSION, GL_VENDOR = 0x1F01, 0x1F02, 0x1F00
GL_CONTEXT_LOST = 0x0507

_u, _i, _f, _e, _p = ctypes.c_uint, ctypes.c_int, ctypes.c_float, ctypes.c_uint, ctypes.c_void_p
_SIGS = {
    "glGetString": (ctypes.c_char_p, _e),
    "glGetError": (_e,),
    "glCreateShader": (_u, _e),
    "glShaderSource": (None, _u, _i, ctypes.POINTER(ctypes.c_char_p), ctypes.POINTER(_i)),
    "glCompileShader": (None, _u),
    "glGetShaderiv": (None, _u, _e, ctypes.POINTER(_i)),
    "glGetShaderInfoLog": (None, _u, _i, ctypes.POINTER(_i), ctypes.c_char_p),
    "glDeleteShader": (None, _u),
    "glCreateProgram": (_u,),
    "glAttachShader": (None, _u, _u),
    "glLinkProgram": (None, _u),
    "glGetProgramiv": (None, _u, _e, ctypes.POINTER(_i)),
    "glGetProgramInfoLog": (None, _u, _i, ctypes.POINTER(_i), ctypes.c_char_p),
    "glDeleteProgram": (None, _u),
    "glUseProgram": (None, _u),
    "glGetUniformLocation": (_i, _u, ctypes.c_char_p),
    "glUniform1f": (None, _i, _f),
    "glUniform2f": (None, _i, _f, _f),
    "glUniform1i": (None, _i, _i),
    "glGenVertexArrays": (None, _i, ctypes.POINTER(_u)),
    "glBindVertexArray": (None, _u),
    "glDeleteVertexArrays": (None, _i, ctypes.POINTER(_u)),
    "glDrawArrays": (None, _e, _i, _i),
    "glViewport": (None, _i, _i, _i, _i),
    "glGenFramebuffers": (None, _i, ctypes.POINTER(_u)),
    "glBindFramebuffer": (None, _e, _u),
    "glDeleteFramebuffers": (None, _i, ctypes.POINTER(_u)),
    "glFramebufferTexture2D": (None, _e, _e, _e, _u, _i),
    "glCheckFramebufferStatus": (_e, _e),
    "glBlitFramebuffer": (None, _i, _i, _i, _i, _i, _i, _i, _i, _u, _e),
    "glGenTextures": (None, _i, ctypes.POINTER(_u)),
    "glBindTexture": (None, _e, _u),
    "glDeleteTextures": (None, _i, ctypes.POINTER(_u)),
    "glTexImage2D": (None, _e, _i, _i, _i, _i, _i, _e, _e, _p),
    "glTexParameteri": (None, _e, _e, _i),
    "glReadPixels": (None, _i, _i, _i, _i, _e, _e, _p),
    "glPixelStorei": (None, _e, _i),
    "glClearColor": (None, _f, _f, _f, _f),
    "glClear": (None, _u),
    "glDisable": (None, _e),
    "glFinish": (None,),
}


class GL:
    """Функції OpenGL за адресами. getproc(b"glName") -> адреса (int) або 0."""

    def __init__(self, getproc):
        functype = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)
        legacy = None
        if E.IS_WIN:
            try:  # функції OpenGL 1.1 Windows віддає лише з opengl32.dll
                legacy = ctypes.WinDLL("opengl32")
            except OSError:
                legacy = None
        for name, sig in _SIGS.items():
            addr = 0
            try:
                addr = int(getproc(name.encode()) or 0)
            except Exception:
                addr = 0
            if addr in (0, 1, 2, 3, -1) and legacy is not None:
                try:
                    addr = ctypes.cast(getattr(legacy, name), ctypes.c_void_p).value or 0
                except AttributeError:
                    addr = 0
            if not addr:
                raise RuntimeError(f"OpenGL: {name}")
            setattr(self, name, functype(*sig)(addr))

    def info(self) -> dict:
        get = lambda k: (self.glGetString(k) or b"").decode("utf-8", "replace")  # noqa: E731
        return dict(renderer=get(GL_RENDERER), version=get(GL_VERSION), vendor=get(GL_VENDOR))


class Renderer:
    """Рендер сцени в окремий кадр (FBO) фіксованої роздільності — бали не залежать від розміру вікна."""

    def __init__(self, gl: GL, width: int, height: int, quality: dict = None, es: bool = False):
        self.gl = gl
        self.w, self.h = width, height
        self.q = dict(QUALITY, **(quality or {}))
        vs, fs = shader_sources(es)
        self.prog = self._program(vs, fs)
        self.loc = {n: gl.glGetUniformLocation(self.prog, n.encode()) for n in
                    ("uRes", "uTime", "uSteps", "uShadow", "uAO", "uRefl")}
        vao = _u(0)
        gl.glGenVertexArrays(1, ctypes.byref(vao))
        self.vao = vao.value
        self.fbo, self.tex = self._target(width, height)
        self.cfbo, self.ctex = self._target(*CHECK_SIZE)
        self.reference = None

    # ── підготовка ──
    def _shader(self, kind: int, src: str) -> int:
        gl = self.gl
        sh = gl.glCreateShader(kind)
        buf = ctypes.c_char_p(src.encode())
        gl.glShaderSource(sh, 1, ctypes.byref(buf), None)
        gl.glCompileShader(sh)
        ok = _i(0)
        gl.glGetShaderiv(sh, GL_COMPILE_STATUS, ctypes.byref(ok))
        if not ok.value:
            raise RuntimeError("GLSL: " + self._log(gl.glGetShaderiv, gl.glGetShaderInfoLog, sh))
        return sh

    def _log(self, getiv, getlog, obj) -> str:
        n = _i(0)
        getiv(obj, GL_INFO_LOG_LENGTH, ctypes.byref(n))
        buf = ctypes.create_string_buffer(max(n.value, 1) + 1)
        getlog(obj, len(buf), None, buf)
        return buf.value.decode("utf-8", "replace").strip()[:600]

    def _program(self, vs: str, fs: str) -> int:
        gl = self.gl
        a, b = self._shader(GL_VERTEX_SHADER, vs), self._shader(GL_FRAGMENT_SHADER, fs)
        p = gl.glCreateProgram()
        gl.glAttachShader(p, a)
        gl.glAttachShader(p, b)
        gl.glLinkProgram(p)
        ok = _i(0)
        gl.glGetProgramiv(p, GL_LINK_STATUS, ctypes.byref(ok))
        gl.glDeleteShader(a)
        gl.glDeleteShader(b)
        if not ok.value:
            raise RuntimeError("GLSL link: " + self._log(gl.glGetProgramiv, gl.glGetProgramInfoLog, p))
        return p

    def _target(self, w: int, h: int) -> tuple:
        gl = self.gl
        tex, fbo = _u(0), _u(0)
        gl.glGenTextures(1, ctypes.byref(tex))
        gl.glBindTexture(GL_TEXTURE_2D, tex.value)
        gl.glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, w, h, 0, GL_RGBA, GL_UNSIGNED_BYTE, None)
        gl.glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        gl.glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        gl.glGenFramebuffers(1, ctypes.byref(fbo))
        gl.glBindFramebuffer(GL_FRAMEBUFFER, fbo.value)
        gl.glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, tex.value, 0)
        if gl.glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE:
            raise RuntimeError(f"OpenGL: framebuffer {w}x{h}")
        return fbo.value, tex.value

    # ── кадр ──
    def _draw(self, fbo: int, w: int, h: int, t: float) -> None:
        gl, q, loc = self.gl, self.q, self.loc
        for cap in (GL_BLEND, GL_DEPTH_TEST, GL_SCISSOR_TEST, GL_STENCIL_TEST, GL_CULL_FACE):
            gl.glDisable(cap)
        gl.glBindFramebuffer(GL_FRAMEBUFFER, fbo)
        gl.glViewport(0, 0, w, h)
        gl.glUseProgram(self.prog)
        gl.glUniform2f(loc["uRes"], float(w), float(h))
        gl.glUniform1f(loc["uTime"], float(t))
        gl.glUniform1i(loc["uSteps"], q["steps"])
        gl.glUniform1i(loc["uShadow"], q["shadow"])
        gl.glUniform1i(loc["uAO"], q["ao"])
        gl.glUniform1i(loc["uRefl"], q["refl"])
        gl.glBindVertexArray(self.vao)
        gl.glDrawArrays(GL_TRIANGLES, 0, 3)
        gl.glBindVertexArray(0)
        gl.glUseProgram(0)

    def frame(self, t: float, dst_fbo: int = None, dst_w: int = 0, dst_h: int = 0) -> None:
        """Малює кадр у власний FBO і (за потреби) масштабує у вікно зі збереженням пропорцій."""
        self._draw(self.fbo, self.w, self.h, t)
        if dst_fbo is None:
            return
        gl = self.gl
        scale = min(dst_w / self.w, dst_h / self.h)
        vw, vh = int(self.w * scale), int(self.h * scale)
        x0, y0 = (dst_w - vw) // 2, (dst_h - vh) // 2
        gl.glBindFramebuffer(GL_DRAW_FRAMEBUFFER, dst_fbo)
        gl.glViewport(0, 0, dst_w, dst_h)
        gl.glClearColor(0.0, 0.0, 0.0, 1.0)
        gl.glClear(GL_COLOR_BUFFER_BIT)
        gl.glBindFramebuffer(GL_READ_FRAMEBUFFER, self.fbo)
        gl.glBlitFramebuffer(0, 0, self.w, self.h, x0, y0, x0 + vw, y0 + vh, GL_COLOR_BUFFER_BIT,
                             GL_LINEAR if scale != 1 else GL_NEAREST)
        gl.glBindFramebuffer(GL_FRAMEBUFFER, dst_fbo)

    def read(self, fbo: int, w: int, h: int) -> bytes:
        gl = self.gl
        buf = ctypes.create_string_buffer(w * h * 4)
        gl.glBindFramebuffer(GL_FRAMEBUFFER, fbo)
        gl.glPixelStorei(GL_PACK_ALIGNMENT, 1)
        gl.glReadPixels(0, 0, w, h, GL_RGBA, GL_UNSIGNED_BYTE, buf)
        return buf.raw

    def check(self) -> bool:
        """Контрольний кадр: на справній відеокарті він щоразу однаковий до біта.
        -> True, якщо кадр збігся з першим (еталонним)."""
        w, h = CHECK_SIZE
        self._draw(self.cfbo, w, h, CHECK_TIME)
        digest = hashlib.sha1(self.read(self.cfbo, w, h)).hexdigest()
        if self.reference is None:
            self.reference = digest
            return True
        return digest == self.reference

    def context_lost(self) -> bool:
        return self.gl.glGetError() == GL_CONTEXT_LOST


# ───────────────────────── датчики NVIDIA ─────────────────────────
THROTTLE_FLAGS = {0x4: "power", 0x8: "hw", 0x20: "thermal", 0x40: "thermal", 0x80: "power"}


class _Util(ctypes.Structure):
    _fields_ = [("gpu", ctypes.c_uint), ("memory", ctypes.c_uint)]


class Nvml:
    """Температура, частоти, споживання й причини скидання частот першої відеокарти NVIDIA."""

    def __init__(self):
        self.lib = None
        self.h = ctypes.c_void_p()
        if not E.IS_WIN:
            return
        for path in ("nvml.dll", r"C:\Program Files\NVIDIA Corporation\NVSMI\nvml.dll"):
            try:
                lib = ctypes.WinDLL(path)
                init = getattr(lib, "nvmlInit_v2", None) or lib.nvmlInit
                if init() != 0:
                    continue
                get = getattr(lib, "nvmlDeviceGetHandleByIndex_v2", None) or lib.nvmlDeviceGetHandleByIndex
                if get(0, ctypes.byref(self.h)) == 0:
                    self.lib = lib
                    return
            except Exception:
                continue

    @property
    def ok(self) -> bool:
        return self.lib is not None

    def name(self) -> str:
        if not self.lib:
            return ""
        buf = ctypes.create_string_buffer(96)
        try:
            if self.lib.nvmlDeviceGetName(self.h, buf, 96) == 0:
                return buf.value.decode("utf-8", "replace")
        except Exception:
            pass
        return ""

    def read(self) -> dict:
        if not self.lib:
            return {}
        lib, h, v = self.lib, self.h, ctypes.c_uint(0)
        out = {}
        try:
            if lib.nvmlDeviceGetTemperature(h, 0, ctypes.byref(v)) == 0:
                out["temp"] = int(v.value)
            if lib.nvmlDeviceGetClockInfo(h, 0, ctypes.byref(v)) == 0:
                out["clock"] = int(v.value)
            if lib.nvmlDeviceGetClockInfo(h, 2, ctypes.byref(v)) == 0:
                out["mem_clock"] = int(v.value)
            if lib.nvmlDeviceGetPowerUsage(h, ctypes.byref(v)) == 0:
                out["power"] = round(v.value / 1000, 1)
            if lib.nvmlDeviceGetFanSpeed(h, ctypes.byref(v)) == 0:
                out["fan"] = int(v.value)
            u = _Util()
            if lib.nvmlDeviceGetUtilizationRates(h, ctypes.byref(u)) == 0:
                out["util"] = int(u.gpu)
            reasons = ctypes.c_ulonglong(0)
            fn = getattr(lib, "nvmlDeviceGetCurrentClocksEventReasons", None) or \
                getattr(lib, "nvmlDeviceGetCurrentClocksThrottleReasons", None)
            if fn and fn(h, ctypes.byref(reasons)) == 0:
                out["throttle"] = sorted({name for bit, name in THROTTLE_FLAGS.items() if reasons.value & bit})
        except Exception:
            pass
        return out

    def close(self) -> None:
        if self.lib:
            try:
                self.lib.nvmlShutdown()
            except Exception:
                pass
            self.lib = None


# ───────────────────────── підсумки ─────────────────────────
def render_target(vendor: str, renderer: str, nv_ok: bool = False, nv_name: str = "") -> dict:
    """Яка відеокарта справді малює тест і чи належать їй датчики NVML.

    На гібридних системах (ноутбук з Optimus, майнінгова карта без виходів, картинка з якої йде через вбудоване
    відео) вікно OpenGL часто малює вбудована графіка, а NVML бачить NVIDIA, що простоює. Без цієї перевірки тест
    підписує результат іменем NVIDIA й показує її холодні датчики поруч із FPS вбудованої графіки.
    -> {gpu: назва карти, що малює; sensors: чи показувати датчики NVML; idle: NVIDIA, що простоює, або ""}
    """
    if "nvidia" in f"{vendor} {renderer}".lower():
        return dict(gpu=nv_name or renderer or "", sensors=bool(nv_ok), idle="")
    return dict(gpu=renderer or "", sensors=False, idle=(nv_name or "NVIDIA") if nv_ok else "")


def frame_stats(frame_ms: list) -> dict:
    """-> avg, low1 (1% найповільніших кадрів), low01 (0.1%), min, max FPS."""
    good = [x for x in frame_ms if x > 0]
    if not good:
        return dict(avg=0.0, low1=0.0, low01=0.0, min=0.0, max=0.0, frames=0)
    total = sum(good)
    s = sorted(good, reverse=True)
    worst = s[:max(1, len(s) // 100)]
    worst01 = s[:max(1, len(s) // 1000)]
    return dict(avg=round(1000 * len(good) / total, 1), low1=round(1000 / (sum(worst) / len(worst)), 1),
                low01=round(1000 / (sum(worst01) / len(worst01)), 1),
                min=round(1000 / s[0], 1), max=round(1000 / s[-1], 1), frames=len(good))


def fps_drop(series: list) -> float:
    """На скільки відсотків FPS наприкінці стрес-тесту нижчий, ніж на початку (після прогріву)."""
    vals = [v for v in series if v]
    if len(vals) < 60:
        return 0.0
    n = max(20, len(vals) // 6)
    head = sorted(vals[5:5 + n])[n // 2] if len(vals) > 5 + n else vals[0]
    tail = sorted(vals[-n:])[n // 2]
    return round(max(0.0, (head - tail) / head * 100), 1) if head else 0.0


def verdict(res: dict) -> str:
    """crash | errors | hot | throttle | stable (стрес-тест) або bench (звичайний тест)."""
    if res.get("state") in ("crash", "lost"):
        return "crash"
    if res.get("errors"):
        return "errors"
    if (res.get("temp_max") or 0) >= 87:
        return "hot"
    if res.get("mode") == "stress" and ((res.get("drop") or 0) >= 8 or "thermal" in (res.get("throttle") or [])):
        return "throttle"
    return "stable" if res.get("mode") == "stress" else "bench"


# ───────────────────────── вікно тесту (окремий процес) ─────────────────────────
def _arg(argv, name: str, default: str = "") -> str:
    for a in argv:
        if a.startswith(f"--{name}="):
            return a.split("=", 1)[1]
    return default


def _write(path: str, data: dict) -> None:
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, path)
    except OSError:
        pass


_MESA_LIBS = []  # підвантажені бібліотеки Mesa: тримаємо посилання, доки живе процес тесту


def load_mesa(folder: str) -> bool:
    """Mesa (mining.py) замість системної opengl32.dll — до того, як Qt її завантажить. Qt просить «opengl32.dll» за
    іменем, а Windows віддає вже завантажений модуль з таким іменем, звідки б він не був. Так тест OpenGL малює
    майнінгова карта: Mesa перекладає OpenGL на DirectX 12 і бере адаптер із MESA_D3D12_DEFAULT_ADAPTER_NAME.
    dxil.dll (підпис шейдерів DirectX 12) драйвер d3d12 теж просить за іменем — тому й її завантажуємо заздалегідь."""
    if not E.IS_WIN or not folder or not os.path.isfile(os.path.join(folder, "opengl32.dll")):
        return False
    try:
        for name in ("dxil.dll", "libglapi.dll", "libgallium_wgl.dll", "opengl32.dll"):
            path = os.path.join(folder, name)
            if os.path.isfile(path):
                _MESA_LIBS.append(ctypes.WinDLL(path))
        return True
    except OSError:
        return False


def keep_composited(hwnd: int) -> bool:
    """Повноекранне OpenGL-вікно Windows виводить в обхід композиції DWM (монопольний показ), і там драйвер
    синхронізує кадри з частотою монітора, хоч ми й просимо swapInterval(0): у вікні 100+ FPS, на весь екран — 60.
    Рамка в 1 px (те саме робить Qt-шне QWindowsWindowFunctions::setHasBorderInFullScreen) лишає вікно під
    композицією: воно так само на весь екран, а FPS не обмежений, як і у віконному режимі."""
    if not E.IS_WIN or not hwnd:
        return False
    try:
        user32 = ctypes.windll.user32
        get_style, set_style = user32.GetWindowLongPtrW, user32.SetWindowLongPtrW
        get_style.restype, get_style.argtypes = ctypes.c_ssize_t, [ctypes.c_void_p, ctypes.c_int]
        set_style.restype = ctypes.c_ssize_t
        set_style.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t]
        user32.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p] + [ctypes.c_int] * 4 + [ctypes.c_uint]
        GWL_STYLE, WS_BORDER = -16, 0x00800000
        # SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED: лише перерахувати рамку
        flags = 0x0001 | 0x0002 | 0x0004 | 0x0010 | 0x0020
        style = get_style(hwnd, GWL_STYLE)
        if not style & WS_BORDER:
            set_style(hwnd, GWL_STYLE, style | WS_BORDER)
            user32.SetWindowPos(hwnd, None, 0, 0, 0, 0, flags)
        return True
    except Exception:
        return False  # без рамки тест однаково пройде — лише з FPS, обмеженим монітором


def run_child(argv) -> int:
    """Точка входу процесу тесту: OptimaX.exe --gpu-bench --preset=1080p --mode=bench|stress --minutes=N --out=…
    [--mesa=<папка Mesa>] — малювати через Mesa на майнінговій карті (до імпорту Qt, див. load_mesa)."""
    mesa = load_mesa(_arg(argv, "mesa", ""))
    from PyQt6.QtCore import Qt, QTimer, QRectF
    from PyQt6.QtGui import QGuiApplication, QSurfaceFormat, QPainter, QColor, QFont, QIcon
    from PyQt6.QtOpenGL import QOpenGLWindow

    preset = _arg(argv, "preset", "1080p")
    mode = _arg(argv, "mode", "bench")
    minutes = max(1, int(_arg(argv, "minutes", "5") or 5))
    out = _arg(argv, "out") or os.path.join(tempfile.gettempdir(), "optimax-gpubench.json")
    width, height = PRESETS.get(preset, PRESETS["1080p"])
    quality = QUALITIES.get(_arg(argv, "quality", "bench"), QUALITY)
    seconds = int(_arg(argv, "seconds", "0") or 0)
    duration = seconds or (BENCH_SECONDS if mode == "bench" else minutes * 60)
    if os.environ.get("OPTIMAX_BENCH_FAST"):
        duration = min(duration, 5 if mode == "bench" else 12)

    fmt = QSurfaceFormat()
    fmt.setVersion(3, 3)
    fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
    fmt.setSwapInterval(0)  # без вертикальної синхронізації — інакше FPS упреться в частоту монітора
    fmt.setSwapBehavior(QSurfaceFormat.SwapBehavior.DoubleBuffer)
    QSurfaceFormat.setDefaultFormat(fmt)
    # між кадрами Qt чекає 5 мс (таймер QWindow::requestUpdate), а Windows може ще й подовжити цю паузу до кроку
    # системного таймера — це стеля FPS самого тесту, а не відеокарти. 0 — новий кадр одразу після попереднього.
    os.environ.setdefault("QT_QPA_UPDATE_IDLE_TIME", "0")
    app = QGuiApplication(sys.argv)
    nv = Nvml()
    state = dict(state="starting", preset=preset, mode=mode, minutes=minutes, duration=duration, t=0.0, fps=0.0,
                 frames=0, errors=0, checks=0, sensors={}, series_fps=[], series_temp=[], series_clock=[], mesa=mesa)
    _write(out, state)

    def font(pt: int, bold: bool = False) -> QFont:
        f = QFont("Segoe UI")
        f.setPointSize(pt)
        if bold:
            f.setWeight(QFont.Weight.DemiBold)
        return f

    class Win(QOpenGLWindow):
        def __init__(self):
            super().__init__()
            self.r = None
            self.t0 = None
            self.last = None
            self.frame_ms = []
            self.sec_frames = 0
            self.sec_start = None
            self.next_check = None
            self.finished = False
            self.hud_ok = True
            self.sensors = {}
            self.temps, self.clocks, self.powers, self.throttle = [], [], [], set()
            self.lost = False
            self.target = dict(gpu="", sensors=False, idle="")  # до initializeGL датчики не читаємо

        def initializeGL(self):
            ctx = self.context()
            try:
                gl = GL(lambda n: int(ctx.getProcAddress(n) or 0))
                self.r = Renderer(gl, width, height, quality)
                info = gl.info()
                self.target = render_target(info["vendor"], info["renderer"], nv.ok, nv.name() if nv.ok else "")
                state.update(gpu=self.target["gpu"], renderer=info["renderer"], gl=info["version"],
                             vendor=info["vendor"])
                if self.target["idle"]:
                    state["idle_gpu"] = self.target["idle"]
                self.r.check()  # еталонний контрольний кадр
            except Exception as e:
                state.update(state="error", error=str(e)[:400])
                _write(out, state)
                QTimer.singleShot(0, app.quit)
                return
            self.frameSwapped.connect(self.update)

        def paintGL(self):
            if self.r is None or self.finished:
                return
            now = time.perf_counter()
            if self.t0 is None:
                self.t0 = self.last = now
                self.sec_start = now
            dt = now - self.last
            self.last = now
            el = now - self.t0
            measured = el - WARMUP_SECONDS
            if measured > 0:
                if self.next_check is None:
                    self.next_check = now + CHECK_EVERY
                self.frame_ms.append(dt * 1000)
                self.sec_frames += 1
            dpr = self.devicePixelRatio()
            self.r.frame(el, self.defaultFramebufferObject(), int(self.width() * dpr), int(self.height() * dpr))
            if mode == "stress" and self.next_check and now >= self.next_check:
                self.next_check = now + CHECK_EVERY
                state["checks"] += 1
                if not self.r.check():
                    state["errors"] += 1
                self.r.frame(el, self.defaultFramebufferObject(), int(self.width() * dpr), int(self.height() * dpr))
                self.last = time.perf_counter()  # контрольний кадр не рахуємо в FPS
            if now - self.sec_start >= 1.0:
                fps = self.sec_frames / (now - self.sec_start)
                if measured > 0:
                    state["series_fps"].append(round(fps, 1))
                    s = self.sensors
                    state["series_temp"].append(s.get("temp"))
                    state["series_clock"].append(s.get("clock"))
                state["fps"] = round(fps if measured > 0 else len(self.frame_ms), 1)
                self.sec_frames = 0
                self.sec_start = now
                if self.r.context_lost():
                    self.lost = True
                    self.finish("lost")
                    return
            state.update(state="warmup" if measured <= 0 else "running", t=round(max(0.0, measured), 1),
                         frames=len(self.frame_ms), sensors=self.sensors)
            self._hud(measured)
            if measured >= duration:
                self.finish("done")

        def _hud(self, measured: float):
            if not self.hud_ok:
                return
            try:
                left = max(0, int(duration - max(0.0, measured)))
                rows = [(tr("gb.hud_warm") if measured <= 0 else
                         tr("gb.hud_line", fps=f"{state['fps']:.0f}", left=f"{left // 60}:{left % 60:02d}"), "#9AA3B8")]
                if mode == "stress":
                    rows.append((tr("gb.hud_err", n=state["errors"], c=state["checks"]), "#9AA3B8"))
                if self.target["sensors"] and self.sensors:
                    s = self.sensors
                    rows.append((tr("gb.hud_sens", t=s.get("temp", "—"), c=s.get("clock", "—"),
                                    w=s.get("power", "—")), "#9AA3B8"))
                if self.target["idle"]:
                    rows.append((tr("gb.hud_idle", gpu=self.target["gpu"] or "?"), "#FFB547"))
                wide = 460 if self.target["idle"] else 330
                bar_y = 50 + 22 * len(rows) + 4
                p = QPainter(self)
                p.setRenderHint(QPainter.RenderHint.Antialiasing)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(8, 10, 20, 170))
                p.drawRoundedRect(QRectF(16, 16, wide, bar_y + 14 - 16), 10, 10)
                p.setPen(QColor("#E8ECF6"))
                p.setFont(font(11, True))
                p.drawText(QRectF(30, 24, wide - 20, 22), f"OptimaX GPU Test · {preset} · "
                           f"{tr('gb.mode_bench') if mode == 'bench' else tr('gb.mode_stress')}"
                           + (" · Mesa" if mesa else ""))
                p.setFont(font(10))
                for i, (text, color) in enumerate(rows):
                    p.setPen(QColor(color))
                    p.drawText(QRectF(30, 50 + 22 * i, wide - 20, 20), text)
                prog = min(1.0, max(0.0, measured) / duration)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(255, 255, 255, 40))
                p.drawRoundedRect(QRectF(30, bar_y, wide - 28, 4), 2, 2)
                p.setBrush(QColor("#7C5CFF"))
                p.drawRoundedRect(QRectF(30, bar_y, (wide - 28) * prog, 4), 2, 2)
                p.setPen(QColor(255, 255, 255, 120))
                p.setFont(font(9))
                p.drawText(QRectF(0, self.height() - 30, self.width() - 16, 20),
                           Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, tr("gb.hud_esc"))
                p.end()
            except Exception:
                self.hud_ok = False

        def poll_sensors(self):
            if not self.target["sensors"]:  # датчики іншої карти, ніж та, що малює, — не показуємо й не враховуємо
                return
            s = nv.read()
            self.sensors = s
            if s.get("temp") is not None:
                self.temps.append(s["temp"])
            if s.get("clock") and state.get("state") == "running":
                self.clocks.append(s["clock"])
            if s.get("power"):
                self.powers.append(s["power"])
            if state.get("state") == "running":
                self.throttle.update(s.get("throttle") or [])

        def finish(self, how: str):
            if self.finished:
                return
            self.finished = True
            st = frame_stats(self.frame_ms)
            res = dict(state=how, preset=preset, mode=mode, minutes=minutes if mode == "stress" else 0,
                       dur=round(len(state["series_fps"]), 0), gpu=state.get("gpu"), gl=state.get("gl"),
                       renderer=state.get("renderer"), errors=state["errors"], checks=state["checks"], **st)
            if state.get("idle_gpu"):
                res["idle_gpu"] = state["idle_gpu"]
            if mesa:
                res["mesa"] = True
            res["score"] = int(round(st["avg"] * SCORE_K)) if how == "done" and mode == "bench" else None
            if self.temps:
                res["temp_max"] = max(self.temps)
            if self.clocks:
                res["clock_avg"] = round(sum(self.clocks) / len(self.clocks))
                res["clock_min"] = min(self.clocks)
            if self.powers:
                res["power_max"] = max(self.powers)
            res["throttle"] = sorted(self.throttle)
            res["drop"] = fps_drop(state["series_fps"])
            res["series_fps"] = state["series_fps"]
            res["series_temp"] = state["series_temp"]
            res["verdict"] = verdict(res)
            state.update(state=how, result=res)
            _write(out, state)
            QTimer.singleShot(150, app.quit)

        def keyPressEvent(self, e):
            if e.key() == Qt.Key.Key_Escape:
                self.cancel()

        def closeEvent(self, e):
            self.cancel()
            super().closeEvent(e)

        def cancel(self):
            if not self.finished:
                self.finished = True
                state.update(state="cancelled")
                _write(out, state)
                QTimer.singleShot(0, app.quit)

    w = Win()
    w.setTitle(f"OptimaX GPU Test — {preset}")
    try:
        from ui_kit import asset
        ic = asset("icon.png")
        if ic:
            w.setIcon(QIcon(ic))
    except Exception:
        pass
    scr = app.primaryScreen().availableGeometry()
    k = min(1.0, scr.width() * 0.86 / 1600, scr.height() * 0.86 / 900)
    w.resize(int(1600 * k), int(900 * k))
    if "--fullscreen" in argv:
        w.showFullScreen()
        keep_composited(int(w.winId()))
    else:
        w.show()

    # опитування датчиків і запис прогресу — окремо від кадрів
    sens = QTimer()
    sens.timeout.connect(w.poll_sensors)
    sens.start(1000)
    w.poll_sensors()
    saver = QTimer()
    saver.timeout.connect(lambda: _write(out, state) if not w.finished else None)
    saver.start(500)
    code = app.exec()
    nv.close()
    if not w.finished:
        state.update(state="cancelled")
        _write(out, state)
    return 0 if code == 0 else code


# ───────────────────────── запуск із програми ─────────────────────────
def self_command() -> list:
    if getattr(sys, "frozen", False):
        return [sys.executable]
    exe = sys.executable
    if E.IS_WIN:
        pyw = os.path.join(os.path.dirname(exe), "pythonw.exe")
        exe = pyw if os.path.exists(pyw) else exe
    return [exe, os.path.join(os.path.dirname(os.path.abspath(__file__)), "optimizer.py")]


class Run:
    """Запущений тест: читає прогрес із файлу, який пише процес тесту."""

    def __init__(self, preset: str, mode: str, minutes: int, fullscreen: bool = False, quality: str = "bench",
                 seconds: int = 0, mesa: str = ""):
        import i18n
        self.preset, self.mode, self.minutes = preset, mode, minutes
        self.out = os.path.join(tempfile.gettempdir(), f"optimax-gpubench-{os.getpid()}-{int(time.time() * 1000)}.json")
        cmd = self_command() + ["--gpu-bench", f"--preset={preset}", f"--mode={mode}", f"--minutes={minutes}",
                                f"--out={self.out}", f"--lang={i18n.LANG}", f"--quality={quality}",
                                f"--seconds={seconds}"]
        if fullscreen:
            cmd.append("--fullscreen")
        env = None
        if mesa:  # Mesa сама обере адаптер за назвою: вбудована графіка (часто без DirectX 12) їй не підходить
            import mining as MG
            cmd.append(f"--mesa={mesa}")
            env = dict(os.environ)
            env.setdefault(MG.ADAPTER_VAR, MG.ADAPTER_NAME)
        here = None if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
        self.proc = subprocess.Popen(cmd, cwd=here, env=env)
        self.started = time.time()
        self.stopped = False

    def poll(self) -> dict:
        data = {}
        try:
            with open(self.out, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            data = {"state": "starting"}
        rc = self.proc.poll()
        if rc is not None and self.stopped and data.get("state") not in ("done", "error", "lost"):
            return dict(data, state="cancelled")
        if rc is not None and data.get("state") not in ("done", "cancelled", "error", "lost"):
            # процес зник без підсумку — найчастіше це скидання відеодрайвера під навантаженням
            data = dict(data, state="crash", exit_code=rc)
            data["result"] = dict(state="crash", preset=self.preset, mode=self.mode, errors=data.get("errors", 0),
                                  checks=data.get("checks", 0), dur=len(data.get("series_fps", [])),
                                  series_fps=data.get("series_fps", []), series_temp=data.get("series_temp", []),
                                  gpu=data.get("gpu"), verdict="crash", exit_code=rc)
        if data.get("state") == "lost" and data.get("result"):
            data["result"]["verdict"] = "crash"
        return data

    @property
    def alive(self) -> bool:
        return self.proc.poll() is None

    def stop(self) -> None:
        self.stopped = True
        if self.alive:
            self.proc.terminate()

    def cleanup(self) -> None:
        for p in (self.out, self.out + ".tmp"):
            try:
                os.remove(p)
            except OSError:
                pass


DEMO_FPS = {"gaming": 214.0, "laptop": 96.0, "old": 31.0, "x3d": 251.0, "xeon": 122.0, "mining": 88.0}
DEMO_GPU = {"gaming": "NVIDIA GeForce RTX 4070", "laptop": "NVIDIA GeForce RTX 4060 Laptop GPU",
            "old": "AMD Radeon RX 570 Series", "x3d": "AMD Radeon RX 7900 XT", "xeon": "NVIDIA GeForce RTX 3060",
            "mining": "NVIDIA P106-100"}
DEMO_SCALE = {"1080p": 1.0, "1440p": 0.58, "4k": 0.27, "ab": 1.65}
# Демо-модель для розумної оптимізації: на ноутбуці максимальний план живлення перегріває процесор
# і відеокарта скидає частоти — OptimaX має це знайти. Решта змін продуктивності дають трохи приросту.
DEMO_EFFECTS = {"laptop": {"laptop_ac_max": -0.075, "ultimate_power": -0.075}}
_demo_runs = [0]


def demo_factor() -> float:
    import abtest
    f = 1.0
    for tid in list(E.JOURNAL.data["applied"]):
        t = E.BY_ID.get(tid)
        if t is None:
            continue
        eff = DEMO_EFFECTS.get(E.DEMO, {}).get(tid)
        if eff is not None:
            f *= 1 + eff
        elif t.group in abtest.PERF_GROUPS:
            f *= 1.006 if E.DEMO == "old" else 1.003
    _demo_runs[0] += 1
    return f * (1 + 0.004 * math.sin(_demo_runs[0] * 2.3))  # невеликий розкид між запусками, як у житті


class DemoRun:
    """Імітація тесту поза Windows: та сама послідовність станів, прискорена в десятки разів."""

    SPEED = 40.0

    def __init__(self, preset: str, mode: str, minutes: int, fullscreen: bool = False, crash: bool = False,
                 quality: str = "bench", seconds: int = 0, mesa: str = ""):
        self.preset, self.mode, self.minutes = preset, mode, minutes
        self.mesa = bool(mesa)
        self.duration = seconds or (BENCH_SECONDS if mode == "bench" else minutes * 60)
        self.started = time.time()
        self.crash = crash
        self.stopped = False
        base = DEMO_FPS.get(E.DEMO, 150.0) * DEMO_SCALE.get(preset, 1.0)
        self.base = base * demo_factor()
        self.nv = E.DEMO in ("gaming", "laptop", "xeon")

    def _series(self, n: int) -> tuple:
        fps, temp = [], []
        hot = E.DEMO == "laptop"
        for i in range(n):
            drop = (0.09 if hot else 0.015) * min(1.0, i / 300)
            wobble = 0.008 * math.sin(i * 0.11) + 0.004 * math.sin(i * 0.53 + 1.3) + 0.003 * math.sin(i * 1.7)
            fps.append(round(self.base * (1 - drop) * (1 + wobble), 1))
            temp.append(int(46 + ((83 if hot else 74) - 46) * (1 - math.exp(-i / 110))) if self.nv else None)
        return fps, temp

    def poll(self) -> dict:
        el = (time.time() - self.started) * self.SPEED - WARMUP_SECONDS
        if self.stopped:
            return {"state": "cancelled"}
        n = int(max(0, min(el, self.duration)))
        fps, temp = self._series(n)
        st = dict(state="warmup" if el <= 0 else "running", preset=self.preset, mode=self.mode, duration=self.duration,
                  t=round(max(0.0, min(el, self.duration)), 1), fps=fps[-1] if fps else 0.0, frames=int(sum(fps)),
                  errors=0, checks=int(n // CHECK_EVERY) if self.mode == "stress" else 0,
                  gpu=DEMO_GPU.get(E.DEMO, "GPU"), gl="4.6.0", series_fps=fps, series_temp=temp,
                  sensors=dict(temp=temp[-1], clock=2610 - (120 if E.DEMO == "laptop" and n > 200 else 0),
                               power=186.0) if (self.nv and temp) else {})
        if self.crash and el > self.duration * 0.4:
            st.update(state="crash")
            st["result"] = dict(state="crash", preset=self.preset, mode=self.mode, errors=0, checks=st["checks"],
                                dur=n, series_fps=fps, series_temp=temp, gpu=st["gpu"], verdict="crash")
            return st
        if el >= self.duration:
            ms = [1000 / f for f in fps for _ in range(max(1, int(f // 20)))]
            stt = frame_stats(ms)
            stt["low1"] = round(stt["avg"] * 0.86, 1)
            stt["low01"] = round(stt["avg"] * 0.74, 1)
            res = dict(state="done", preset=self.preset, mode=self.mode, minutes=self.minutes if self.mode == "stress" else 0,
                       dur=n, gpu=st["gpu"], gl="4.6.0", errors=0, checks=st["checks"], **stt)
            res["score"] = int(round(stt["avg"] * SCORE_K)) if self.mode == "bench" else None
            if self.mesa:
                res["mesa"] = True
            if self.nv:
                res.update(temp_max=max(t for t in temp if t is not None), clock_avg=2595, clock_min=2490,
                           power_max=196.0)
            res["throttle"] = ["thermal"] if (E.DEMO == "laptop" and self.mode == "stress") else []
            res["drop"] = fps_drop(fps)
            res["series_fps"], res["series_temp"] = fps, temp
            res["verdict"] = verdict(res)
            st.update(state="done", result=res)
        return st

    @property
    def alive(self) -> bool:
        st = self.poll().get("state")
        return st in ("warmup", "running", "starting")

    def stop(self) -> None:
        self.stopped = True

    def cleanup(self) -> None:
        pass


def start(preset: str, mode: str, minutes: int = 5, fullscreen: bool = False, quality: str = "bench", seconds: int = 0,
          mesa: str = ""):
    if not E.IS_WIN:
        return DemoRun(preset, mode, minutes, fullscreen, quality=quality, seconds=seconds, mesa=mesa)
    return Run(preset, mode, minutes, fullscreen, quality=quality, seconds=seconds, mesa=mesa)


# ───────────────────────── історія результатів ─────────────────────────
def same_gpu(a: dict, b: dict) -> bool:
    """Чи на одній відеокарті зроблені два заміри (за назвою карти, що малювала, і ознакою «NVIDIA простоювала»)."""
    ga, gb = a.get("gpu"), b.get("gpu")
    if not (ga and gb):
        return True  # невідомо — як раніше
    if bool(a.get("idle_gpu")) != bool(b.get("idle_gpu")):
        return False
    if bool(a.get("mesa")) != bool(b.get("mesa")):  # OpenGL через Mesa повільніший за рідний драйвер
        return False
    return ga == gb


def save_result(cfg, res: dict) -> dict:
    """Додає результат в історію (останні 40) і повертає його з порівнянням із попереднім таким самим тестом."""
    res = dict(res)
    res["ts"] = int(time.time())
    res.pop("series_clock", None)
    if res.get("kind", "own") == "own":
        res.setdefault("rev", BENCH_REV)
    hist = list(cfg["bench"] or [])
    # порівнюємо лише з тим самим тестом на тій самій відеокарті: бали вбудованої графіки й дискретної — різні речі;
    # і лише з тією самою ревізією тесту — інакше виправлення самого тесту виглядало б як приріст від оптимізації
    prev = next((h for h in reversed(hist) if h.get("kind", "own") == res.get("kind", "own")
                 and h.get("preset") == res.get("preset") and h.get("mode") == res.get("mode")
                 and h.get("rev", 1) == res.get("rev", 1) and h.get("score") and same_gpu(h, res)), None)
    if prev and res.get("score"):
        res["delta"] = round((res["score"] - prev["score"]) / prev["score"] * 100, 1)
        try:
            import fpstest as FT
            res["changes"] = len(FT.changes_between(prev["ts"], res["ts"]))
        except Exception:
            res["changes"] = 0
    # графіки зберігаємо лише для останніх результатів, щоб налаштування не розросталися
    for h in hist[:-3]:
        h.pop("series_fps", None)
        h.pop("series_temp", None)
    hist.append(res)
    cfg["bench"] = hist[-40:]
    return res
