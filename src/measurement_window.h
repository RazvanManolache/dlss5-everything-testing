#pragma once
#include <algorithm>
#include <cstdint>

// Frame-boundary timing excludes startup and all post-measurement captures.
struct MeasurementWindow {
    double warmup = 0, requested = 0, start = -1, end = -1, elapsed = 0;
    double sample_start = 0, minimum_fps = 0, maximum_fps = 0, maximum_frame = 0;
    uint64_t frames = 0, sample_frames = 0;
    bool enabled() const { return requested > 0; }
    bool complete() const { return end >= 0; }
    void before_frame(double seconds) {
        if (enabled() && start < 0 && seconds >= warmup) start = seconds;
    }
    bool after_frame(double seconds, double frame_seconds) {
        if (start < 0 || complete()) return false;
        ++frames;
        elapsed = seconds - start;
        maximum_frame = std::max(maximum_frame, frame_seconds);
        if (elapsed < requested) return false;
        end = seconds;
        return true;
    }
    double fps() const { return elapsed > 0 ? frames / elapsed : 0; }
};
