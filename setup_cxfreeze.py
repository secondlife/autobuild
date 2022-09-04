import shutil
from setuptools_scm import get_version
from distutils.core import Command
from pathlib import Path

from cx_Freeze import Executable, setup

ROOT_DIR = Path(__file__).parent.absolute()
COPY_TO_ZIP = ["LICENSE"]


class FinalizeCommand(Command):
    description = "Prepare cx_Freeze build dirs and create a zip file"
    user_options = []

    def initialize_options(self) -> None:
        pass

    def finalize_options(self) -> None:
        pass

    def run(self):
        version = get_version(ROOT_DIR)
        for path in (ROOT_DIR / "build").iterdir():
            if path.name.startswith("exe.") and path.is_dir():
                for to_copy in COPY_TO_ZIP:
                    shutil.copy(ROOT_DIR / to_copy, path / to_copy)
                platform = path.stem[4:path.stem.rfind("-")]
                zip_path = ROOT_DIR / f"dist/autobuild-{platform}-{version}" 
                shutil.make_archive(zip_path, "zip", path)


build_exe_options = {
    "packages": ["autobuild"],
}

awsim = Executable("autobuild/autobuild_main.py", base=None, target_name="autobuild")

setup(
    options={"build_exe": build_exe_options},
    executables=[awsim],
    cmdclass={"finalize": FinalizeCommand}
)
