import unittest
from normalize_renderer_labels import display,prose,normalize


class RendererNameTests(unittest.TestCase):
    def test_names_and_vendor_features(self):
        self.assertEqual(display('Phoenix / NVIDIA'),'Phoenix DLSS5 / NVIDIA DLSS5')
        self.assertEqual(display('DLSS5 Phoenix and NVIDIA NR'),'Phoenix DLSS5 and NVIDIA DLSS5 NR')
        value='NVIDIA GeForce RTX 5080; NVIDIA CUDA; NVIDIA DLSS SR; NVIDIA Frame Generation'
        self.assertEqual(display(value),value)

    def test_paths_wire_values_and_code_examples_stay_intact(self):
        value='`Phoenix.json` `phoenix` [Phoenix](https://example.org/Phoenix/model)\n```ini\n[Phoenix]\nBackend=3\n```'
        self.assertEqual(prose(value),value.replace('[Phoenix](', '[Phoenix DLSS5]('))
        code='cfg["Phoenix"]; backend="phoenix"; file="Phoenix.addon32"; Text="Phoenix controls";'
        self.assertEqual(normalize(code,'src/View.cs'),code.replace('Phoenix controls','Phoenix DLSS5 controls'))
        self.assertEqual(normalize('Append("[Phoenix]\\nBackend=3");','app/PhoenixControlClient.cs'),'Append("[Phoenix]\\nBackend=3");')
        hardware='Rendering GPU (optimized NVIDIA); NVIDIA NVAPI headers; NVIDIA Streamline; NVIDIA upscaling'
        self.assertEqual(display(hardware),hardware)

    def test_dashboard_templates_and_generated_html(self):
        self.assertEqual(normalize('`Phoenix / NVIDIA`','dashboard/app.js'),'`Phoenix DLSS5 / NVIDIA DLSS5`')
        self.assertEqual(normalize("page = '''<h1>DLSS5 Phoenix</h1>'''",'tools/render_readme_benchmarks.py'),"page = '''<h1>Phoenix DLSS5</h1>'''")

    def test_normalization_is_idempotent(self):
        value='Phoenix DLSS5 / NVIDIA DLSS5, NVIDIA DLSS5 NR'
        self.assertEqual(display(display(value)),value)

    def test_sentence_endings_and_pairings(self):
        self.assertEqual(display('NVIDIA/Phoenix. Phoenix-only.'),
            'NVIDIA DLSS5/Phoenix DLSS5. Phoenix DLSS5-only.')


if __name__=='__main__':unittest.main()
