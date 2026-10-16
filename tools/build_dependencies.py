from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
def dependency(name):
    value=Path(json.loads((ROOT/'build-dependencies.json').read_text())[name])
    return value if value.is_absolute() else ROOT/value
