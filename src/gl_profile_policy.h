#pragma once

constexpr bool acceptedGLProfile(int requestedMajor, int requestedMinor, int actualMask,
                                 bool reshadeLoaded) {
    if (actualMask & 1) return true;
    const bool upgraded = requestedMajor < 4 || (requestedMajor == 4 && requestedMinor < 3);
    return upgraded && reshadeLoaded && (actualMask & 2);
}
