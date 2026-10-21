"""Справжній рендер сцени тесту відеокарти через EGL без екрана (Mesa llvmpipe у CI):
компіляція GLSL 330 core, кадр, детермінованість контрольного кадру, масштабування у «вікно» іншого розміру."""
import _boot
import ctypes
import ctypes.util
import sys
import time

sys.argv = _boot.argv("--lang=en")
import gpubench as GB  # noqa: E402


def egl_context():
    name = ctypes.util.find_library("EGL") or "libEGL.so.1"
    try:
        egl = ctypes.CDLL(name)
    except OSError as e:
        return None, f"no libEGL: {e}"
    egl.eglGetProcAddress.restype = ctypes.c_void_p
    egl.eglGetProcAddress.argtypes = [ctypes.c_char_p]
    addr = egl.eglGetProcAddress(b"eglGetPlatformDisplayEXT")
    if not addr:
        return None, "no eglGetPlatformDisplayEXT"
    gpd = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p)(addr)
    dpy = gpd(0x31DD, None, None)  # EGL_PLATFORM_SURFACELESS_MESA
    egl.eglInitialize.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
    if not dpy or not egl.eglInitialize(dpy, None, None):
        return None, "eglInitialize failed (no Mesa surfaceless platform)"
    egl.eglBindAPI(0x30A2)  # EGL_OPENGL_API
    attrs = (ctypes.c_int * 7)(0x3098, 3, 0x30FB, 3, 0x30FD, 1, 0x3038)  # 3.3 core
    egl.eglCreateContext.restype = ctypes.c_void_p
    egl.eglCreateContext.argtypes = [ctypes.c_void_p] * 4
    ctx = egl.eglCreateContext(dpy, None, None, attrs)
    egl.eglMakeCurrent.argtypes = [ctypes.c_void_p] * 4
    if not ctx or not egl.eglMakeCurrent(dpy, None, None, ctx):
        return None, "no OpenGL 3.3 core context"
    return egl, ""


egl, why = egl_context()
if not egl:
    _boot.result(skip=why)
    sys.exit(0)
gl = GB.GL(lambda n: egl.eglGetProcAddress(n) or 0)
info = gl.info()
W, H = 320, 180
t0 = time.time()
r = GB.Renderer(gl, W, H, GB.QUALITIES["ab"])
compile_s = time.time() - t0
r.frame(7.25)
gl.glFinish()
raw = r.read(r.fbo, W, H)
px = [raw[i] for i in range(0, len(raw), 4 * 97)]  # червоний канал вибірково
checks = [r.check() for _ in range(3)]
dst, _tex = r._target(500, 400)
r.frame(3.0, dst, 500, 400)
gl.glFinish()
raw2 = r.read(dst, 500, 400)
_boot.result(info=info, compile_s=round(compile_s, 2), bytes=len(raw), distinct=len(set(px)),
             mean=sum(px) / len(px), checks=checks, blit_bytes=len(raw2), gl_error=gl.glGetError())
