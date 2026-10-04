"""Run on each target OS: python scripts/build_app.py."""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parent.parent
output = root / "dist"
output.mkdir(exist_ok=True)
# Build outside synced folders: Finder metadata can invalidate a Mac signature.
with tempfile.TemporaryDirectory(prefix="flexcontrol-build-") as staging:
    stage = Path(staging)
    environment = dict(os.environ, PYINSTALLER_CONFIG_DIR=str(stage / "cache"))
    subprocess.run([
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
        "--onedir", "--name", "FlexControl-Thetis", "--paths", str(root.parent),
        "--osx-bundle-identifier", "nl.pa3eke.flexcontrol-thetis",
        "--distpath", str(stage / "dist"), "--workpath", str(stage / "build"),
        "--specpath", str(stage), str(root / "launcher.py"),
    ], cwd=root, env=environment, check=True)
    if sys.platform == "darwin":
        app = stage / "dist" / "FlexControl-Thetis.app"
        subprocess.run(["xattr", "-cr", str(app)], check=True)
        subprocess.run(["codesign", "--force", "--deep", "--sign", "-", str(app)], check=True)
        subprocess.run(["codesign", "--verify", "--deep", "--strict", str(app)], check=True)
        # A zip preserves the signed app when the project lives in a synced folder.
        subprocess.run(["ditto", "-c", "-k", "--keepParent", str(app),
                        str(output / "FlexControl-Thetis-macOS.zip")], check=True)
        shutil.copytree(app, output / app.name, dirs_exist_ok=True)
    else:
        shutil.copytree(stage / "dist" / "FlexControl-Thetis", output / "FlexControl-Thetis", dirs_exist_ok=True)
        shutil.make_archive(str(output / "FlexControl-Thetis-Windows"), "zip",
                            stage / "dist", "FlexControl-Thetis")
print(f"Desktop-app opgeslagen in {output}")
