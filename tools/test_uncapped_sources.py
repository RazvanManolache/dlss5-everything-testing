"""CPU-only regression checks for requested presentation policy; not runtime FPS proof."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class UncappedSourceTests(unittest.TestCase):
    def test_background_window_has_no_desktop_chrome_size_limit(self):
        self.assertIn('style=background?WS_POPUP:', (ROOT / 'src/main.cpp').read_text())

    def test_dxgi_and_d3d9_do_not_request_vblank(self):
        for name in ('dx12.inl', 'dx10_11.inl'):
            text = (ROOT / 'src' / name).read_text()
            self.assertIn('swapchain->Present(0,', text)
            self.assertNotIn('swapchain->Present(1,', text)
        self.assertIn('p.PresentationInterval=D3DPRESENT_INTERVAL_IMMEDIATE', (ROOT / 'src/legacy.inl').read_text())

    def test_gl_and_glide_disable_swap_interval(self):
        self.assertIn('swap&&swap(0)', (ROOT / 'src/opengl.inl').read_text())
        text = (ROOT / 'src/programmable_gl.inl').read_text()
        self.assertIn('eglSwapInterval(eglDisplay,0)', text)
        self.assertIn('interval&&interval(0)', text)
        self.assertIn('grBufferSwap(0)', (ROOT / 'src/glide.inl').read_text())

    def test_vulkan_queries_non_fifo_and_reports_unsupported_fallback(self):
        self.assertIn('sc.presentMode=uncappedPresentMode()', (ROOT / 'src/vulkan.inl').read_text())
        text = (ROOT / 'src/vulkan_present.inl').read_text()
        self.assertIn('VK_PRESENT_MODE_IMMEDIATE_KHR', text)
        self.assertIn('VK_PRESENT_MODE_MAILBOX_KHR', text)
        self.assertIn('rendererInfo["uncapped_available"] = false', text)


if __name__ == '__main__':
    unittest.main()
