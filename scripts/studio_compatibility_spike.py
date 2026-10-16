"""Build a small articulated custom-glass fixture before expensive vehicle runs."""
import argparse
from pathlib import Path

from car2lego3d.common import write_json
from car2lego3d.part_package import plate_glass_package, package_parts, install_parts
from car2lego3d.studio import export_studio
from car2lego3d.ldraw_document import Document


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--library', type=Path, required=True)
    parser.add_argument('--install-to', type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    package = args.output / 'custom-parts'
    glass = plate_glass_package(package, args.library)
    text = f'''0 FILE main.ldr
0 P0 nested hinged door with custom glazing
1 71 0 0 0 1 0 0 0 1 0 0 0 1 2429.dat
1 15 0 0 0 1 0 0 0 1 0 0 0 1 door.ldr
0 STEP
0 FILE door.ldr
1 16 0 0 0 1 0 0 0 1 0 0 0 1 2430.dat
1 16 20 -8 10 1 0 0 0 1 0 0 0 1 door-window.ldr
0 STEP
0 FILE door-window.ldr
1 40 0 0 0 1 0 0 0 1 0 0 0 1 {glass}
0 STEP
0 NOFILE
'''
    source = args.output / 'model.mpd'
    source.write_text(text, encoding='utf-8')
    (args.output/'model-flat.ldr').write_text(Document(text).flatten(),encoding='utf-8')
    export_studio(source, args.output/'studio')
    package_parts(package)
    report = dict(schema='car2lego3d.studio-spike.v1', archive_verified=True,
        studio_open_verified=False, studio_save_reopen_verified=False,
        hinge_operation_verified=False, custom_part_visible_verified=False,
        independent_profile_verified=False, physical_verified=False)
    if args.install_to:
        report['installation'] = install_parts(package,args.install_to)
    write_json(args.output/'compatibility.json',report)


if __name__ == '__main__':
    main()
