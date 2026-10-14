/* Base Modeler mesh-flow kernels, GPL-3.0-or-later.
 * Plain float arrays only: no Blender, Python, NumPy ABI or background threads.
 * Build: clang -O3 -ffp-contract=off -arch arm64 -arch x86_64 -dynamiclib
 *        flow.c -o libbase_modeler_flow.dylib
 */
#include <stddef.h>

static inline void interpolate(const float *restrict grid, const float *p,
                               float *restrict result,
                               int nx, int ny, int nz) {
    const float mins[3] = {-.50f, -.25f, -.25f};
    const float span[3] = {1.f, .5f, 2.5f};
    const int shape[3] = {nx, ny, nz};
    int i[3]; float t[3];
    for (int k=0; k<3; ++k) {
        float c=(p[k]-mins[k])*((shape[k]-1)/span[k]);
        float upper=shape[k]-1.00001f;
        c=c<0.f ? 0.f : (c>upper ? upper : c);
        i[k]=(int)c; t[k]=c-i[k];
    }
    size_t at=((size_t)i[0]*ny+i[1])*nz+i[2];
    size_t a=3*at, b=3*(at+nz), c=3*(at+(size_t)ny*nz);
    size_t d=3*(at+(size_t)(ny+1)*nz);
    for (int k=0;k<3;++k) {
        float av=grid[a+k]*(1.f-t[2])+grid[a+3+k]*t[2];
        float bv=grid[b+k]*(1.f-t[2])+grid[b+3+k]*t[2];
        float cv=grid[c+k]*(1.f-t[2])+grid[c+3+k]*t[2];
        float dv=grid[d+k]*(1.f-t[2])+grid[d+3+k]*t[2];
        float low=av*(1.f-t[1])+bv*t[1];
        float high=cv*(1.f-t[1])+dv*t[1];
        result[k]=low*(1.f-t[0])+high*t[0];
    }
}

void bm_compose(const float *restrict displacement,
                const float *restrict points, float *restrict output,
                size_t count, int nx, int ny, int nz) {
    for (size_t i=0;i<count;++i) {
        size_t at=i*3;
        /* A zero velocity point stays fixed under every self-composition.
         * Most of the surrounding grid is empty, especially for local sliders. */
        if (displacement[at]==0.f && displacement[at+1]==0.f && displacement[at+2]==0.f) {
            output[at]=0.f;output[at+1]=0.f;output[at+2]=0.f;continue;
        }
        float point[3]={points[at]+displacement[at],points[at+1]+displacement[at+1],points[at+2]+displacement[at+2]};
        float value[3];interpolate(displacement,point,value,nx,ny,nz);
        for(int k=0;k<3;++k)output[at+k]=displacement[at+k]+value[k];
    }
}

void bm_sample(const float *restrict displacement,
               const float *restrict points, float *restrict output,
               size_t count, int nx, int ny, int nz) {
    for (size_t i=0;i<count;++i) {
        size_t at=i*3;
        float value[3];interpolate(displacement,points+at,value,nx,ny,nz);
        for(int k=0;k<3;++k)output[at+k]=points[at+k]+value[k];
    }
}
