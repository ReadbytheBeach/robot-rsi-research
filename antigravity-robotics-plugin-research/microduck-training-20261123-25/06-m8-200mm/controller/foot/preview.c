#include <mujoco/mujoco.h>
#include <math.h>
#include <stdint.h>
/* Integrate genuine MuJoCo substeps, matching the live ground-witness thresholds. */
int foot_roll(const mjModel *m, mjData *d, int count, const int32_t *flags, const int32_t *owner,
              int a, int b, int trunk, const double *verts, int nv, double *air, double limit, int contact_guard, double tilt_min, double max_x, int root_q) {
    const int ids[2]={a,b};
    for (int step=0;step<count;step++) {
        mj_step(m,d);
        if (d->xmat[9*trunk+8]<tilt_min || d->qpos[root_q]>max_x) return 2;
        int grounded[2]={0,0};
        for (int k=0;contact_guard && k<d->ncon;k++) {
            const mjContact *c=d->contact+k;
            if (c->dist>0 || c->efc_address<0) continue;
            int g0=c->geom[0],g1=c->geom[1],f0=flags[g0],f1=flags[g1],i=owner[g0],j=owner[g1];
            int floor=((f0&8) && (f1&2) && !(f1&4)) || ((f1&8) && (f0&2) && !(f0&4));
            int wall=((f0&1) && ((f1&2)||j>=0)) || ((f1&1) && ((f0&2)||i>=0));
            int num=(f0&8)?j:(f1&8)?i:-1;
            if (num<0 && !floor && !wall) continue;
            mjtNum force[6]; mj_contactForce(m,d,k,force);
            if (force[0]<=1e-5) continue;
            if (floor||wall) return 3;
            grounded[num]=1;
        }
        for (int j=0;j<2;j++) {
            const int id=ids[j]; double pos=d->xpos[3*id+2];
            /* A tilted hex nut has support radius at least its half-height. */
            if (grounded[j] || pos<=.00425) { air[j]=0; continue; }
            const double *z=d->xmat+9*id+6;
            double bottom=1e8;
            for (int k=0;k<nv;k++) {
                const double *v=verts+3*k;
                double height=pos+z[0]*v[0]+z[1]*v[1]+z[2]*v[2];
                if (height<bottom) bottom=height;
            }
            if (bottom>.001) air[j]+=m->opt.timestep; else air[j]=0;
            if(air[j]>=limit-1e-9) return 1;
        }
        for (int k=0;contact_guard && k<mjNWARNING;k++) if (d->warning[k].number>0) return 4;
    }
    return 0;
}
