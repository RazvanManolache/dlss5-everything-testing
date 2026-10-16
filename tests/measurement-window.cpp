#include "measurement_window.h"
#include <cassert>
#include <cmath>

int main() {
    MeasurementWindow window;
    window.warmup = 5;
    window.requested = 20;
    window.before_frame(4.9);
    assert(!window.after_frame(5.1, .2));
    assert(window.frames == 0 && window.start < 0);
    window.before_frame(5.1);
    assert(!window.after_frame(6.1, 1));
    assert(window.frames == 1 && std::abs(window.elapsed - 1) < 1e-9);
    window.before_frame(6.1);
    assert(window.after_frame(25.1, 19));
    assert(window.complete() && window.frames == 2);
    assert(std::abs(window.elapsed - 20) < 1e-9);
    assert(std::abs(window.fps() - .1) < 1e-9);
    window.before_frame(26);
    assert(!window.after_frame(30, 4));
    assert(window.frames == 2 && window.maximum_frame == 19);
    MeasurementWindow disabled;
    disabled.before_frame(100);
    assert(!disabled.after_frame(200, 100));
    assert(disabled.frames == 0 && !disabled.enabled());
}
