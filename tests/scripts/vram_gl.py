"""Перевірка відеопам'яті на справжньому OpenGL через EGL без екрана (Mesa у CI): виділення буферів, запис шаблонів,
копія відеокартою, звірка; зіпсований байт має знайтися рівно в одному блоці."""
import _boot
import ctypes
import ctypes.util
import sys

sys.argv = _boot.argv("--lang=en")
import vramtest as VT  # noqa: E402


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
gl = VT.GLB(lambda n: egl.eglGetProcAddress(n) or 0)
info = gl.info()
core = VT.Core(gl, 192)
state = {}
VT.run_core(core, state, lambda: None, lambda: False)
clean = dict(errors=core.errors, mb=state.get("mb"), done=state.get("done"), total=state.get("total"),
             state=state.get("state"))
# «зламана комірка»: після запису шаблону змінюємо один байт у другому буфері — звірка мусить це знайти
core.errors = 0
core.write(1, 1)
gl.glBindBuffer(VT.GL_COPY_WRITE_BUFFER, core.bufs[1])
bad = (ctypes.c_ubyte * 1)(0x7E)
gl.glBufferSubData(VT.GL_COPY_WRITE_BUFFER, 3 * VT.BLOCK + 17, 1, bad)
found = core.verify(1, 1)
core.release()
_boot.result(info=info, clean=clean, found=found, bad_bytes=core.bad_bytes, log=core.log[-1:], free=gl.free_mb(),
             gl_error=gl.glGetError())
