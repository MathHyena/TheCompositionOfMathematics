from pathlib import Path
import subprocess
import re

ROOT = Path.cwd()
OVERLEAF = ROOT / "overleaf_source"
SOURCE = ROOT / "source"
CONVERTER = ROOT / "tools" / "convert_latex_to_pretext.py"

FOLDER_MAP = {
    "00_foundations": "01_foundations",
    "01_algebra": "02_algebra",
    "02_number_theory": "03_number_theory",
    "03_geometry": "04_geometry",
    "04_topology": "05_topology",
    "05_analysis": "06_analysis",
    "06_discrete_mathematics_combinatorics": "07_discrete_mathematics_combinatorics",
    "07_probability": "08_probability",
    "08_statistics": "09_statistics",
    "09_differential_equations_dynamical_systems": "10_differential_equations_dynamical_systems",
    "10_optimization_operations_research": "11_optimization_operations_research",
    "11_numerical_computational_mathematics": "12_numerical_computational_mathematics",
    "12_mathematical_logic_foundations": "13_mathematical_logic_foundations",
    "13_applied_mathematics_modeling": "14_applied_mathematics_modeling",
    "14_reference": "15_reference",
}

PLACEHOLDER = "Content for this section will be added here"

original_converter = CONVERTER.read_text(encoding="utf-8")

converted = 0
skipped_existing = 0
missing_target = 0
skipped_control = 0
failed = 0

try:
    for tex in sorted(OVERLEAF.glob("*/*.tex")):
        folder = tex.parent.name

        if folder not in FOLDER_MAP:
            skipped_control += 1
            continue

        # Skip chapter/control files such as 01_algebra.tex.
        if tex.stem == folder:
            skipped_control += 1
            continue

        ptx = SOURCE / FOLDER_MAP[folder] / f"{tex.stem}.ptx"

        if not ptx.exists():
            print(f"MISSING TARGET: {ptx.relative_to(ROOT)}")
            missing_target += 1
            continue

        current = ptx.read_text(encoding="utf-8")

        # Never overwrite already-populated PreTeXt files.
        if PLACEHOLDER not in current:
            print(f"SKIP POPULATED: {ptx.relative_to(ROOT)}")
            skipped_existing += 1
            continue

        modified = re.sub(
            r'^LATEX_FILE\s*=\s*Path\(".*?"\)',
            f'LATEX_FILE = Path("{tex.relative_to(ROOT).as_posix()}")',
            original_converter,
            count=1,
            flags=re.MULTILINE,
        )

        modified = re.sub(
            r'^PTX_FILE\s*=\s*Path\(".*?"\)',
            f'PTX_FILE = Path("{ptx.relative_to(ROOT).as_posix()}")',
            modified,
            count=1,
            flags=re.MULTILINE,
        )

        CONVERTER.write_text(modified, encoding="utf-8")

        print(f"\nCONVERTING: {tex.relative_to(ROOT)}")
        result = subprocess.run(
            ["python3", str(CONVERTER)],
            cwd=ROOT,
        )

        if result.returncode == 0:
            converted += 1
        else:
            print(f"FAILED: {tex.relative_to(ROOT)}")
            failed += 1

finally:
    CONVERTER.write_text(original_converter, encoding="utf-8")

print("\n=== BATCH CONVERSION SUMMARY ===")
print(f"Converted:       {converted}")
print(f"Already filled:  {skipped_existing}")
print(f"Missing targets: {missing_target}")
print(f"Control skipped: {skipped_control}")
print(f"Failed:          {failed}")
