#include "gl_profile_policy.h"
static_assert(acceptedGLProfile(3,3,1,false));
static_assert(!acceptedGLProfile(3,3,2,false));
static_assert(acceptedGLProfile(3,3,2,true));
static_assert(!acceptedGLProfile(4,6,2,true));
static_assert(!acceptedGLProfile(3,3,0,true));
int main() { return 0; }
