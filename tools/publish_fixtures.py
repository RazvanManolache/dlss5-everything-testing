"""Compatibility entry point: publish a validated build to both configured sets."""
from pathlib import Path
import argparse
import json
from publish_sets import ROOT, matches, publish


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path)
    p.add_argument('--validation', type=Path, required=True)
    p.add_argument('--installed-snapshot', type=Path, help='Optional additional preservation check from older workflows')
    p.add_argument('--config', type=Path, default=ROOT/'build-sets.json')
    p.add_argument('--output', type=Path, default=ROOT/'state/publication.json')
    a = p.parse_args()
    installed = json.loads(a.installed_snapshot.read_text()) if a.installed_snapshot else {}
    def check_installed():
        for rel, pin in installed.items():
            path = ROOT/rel
            if not path.resolve().is_relative_to(ROOT) or not matches(path, pin):
                raise RuntimeError('Installed file changed: '+rel)
    check_installed()
    a.output.parent.mkdir(parents=True, exist_ok=True)
    publish(a.source, a.validation, a.config, a.output)
    check_installed()


if __name__ == '__main__':
    main()
