// citro3d's C3D_DEPTHTYPE is a transparent union in C but a class with private
// members in C++, so its two users are defined here, in C, and forward to
// c3d_gpu.cpp with the depth format as an int (-1: no depth buffer).
#include <citro3d.h>

C3D_RenderTarget* c3dvita_RenderTargetCreate(int width, int height, GPU_COLORBUF colorFmt, int depthFmt);
C3D_RenderTarget* c3dvita_RenderTargetCreateFromTex(C3D_Tex* tex, GPU_TEXFACE face, int level, int depthFmt);

C3D_RenderTarget* C3D_RenderTargetCreate(int width, int height, GPU_COLORBUF colorFmt, C3D_DEPTHTYPE depthFmt)
{
	return c3dvita_RenderTargetCreate(width, height, colorFmt, C3D_DEPTHTYPE_OK(depthFmt) ? (int)C3D_DEPTHTYPE_VAL(depthFmt) : -1);
}

C3D_RenderTarget* C3D_RenderTargetCreateFromTex(C3D_Tex* tex, GPU_TEXFACE face, int level, C3D_DEPTHTYPE depthFmt)
{
	return c3dvita_RenderTargetCreateFromTex(tex, face, level, C3D_DEPTHTYPE_OK(depthFmt) ? (int)C3D_DEPTHTYPE_VAL(depthFmt) : -1);
}
