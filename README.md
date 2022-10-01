# Autobuild

[![codecov](https://codecov.io/gh/secondlife/autobuild/branch/main/graph/badge.svg?token=8GBLMAFDIN)](https://codecov.io/gh/secondlife/autobuild)

**Autobuild** is a framework for building packages and for managing the
dependencies of a package on other packages. It provides a common
interface to configuring and building any package, but it is not a
build system like make or cmake. You will still need platform-specific
make, cmake, or project files to configure and build your
library. Autobuild will, however, allow you invoke these commands and
package the product with a common interface.

*Important: Linden Lab Autobuild is not the same as or derived from GNU
Autobuild, but they are similar enough to cause confusion.*

For more information, see [Autobuild's wiki page][wiki].

[wiki]: https://wiki.secondlife.com/wiki/Autobuild

## Environment variables

| Name | Default | Description |
|-|-|-|
| AUTOBUILD_ADDRSIZE | 32 | Target address size |
| AUTOBUILD_BUILD_ID | - | Build identifier |
| AUTOBUILD_CONFIGURATION | - | Target build configuration |
| AUTOBUILD_CONFIG_FILE | autobuild.xml | Autobuild configuration filename |
| AUTOBUILD_CPU_COUNT | - | Build system cpu core count |
| AUTOBUILD_GITHUB_TOKEN | - | GitHub HTTP authorization token to use during package download |
| AUTOBUILD_GITLAB_TOKEN | - | GitLab HTTP authorization token to use during package download |
| AUTOBUILD_INSTALLABLE_CACHE | - | Location of local download cache |
| AUTOBUILD_LOGLEVEL | WARNING | Log level |
| AUTOBUILD_PLATFORM | - | Target platform |
| AUTOBUILD_SCM_SEARCH | true | Whether to search for .git in parent directories if using SCM version discovery |
| AUTOBUILD_VARIABLES_FILE | - | .env file to load |
| AUTOBUILD_VCS_BRANCH | git branch | autobuild-package.xml VCS info: branch name.  |
| AUTOBUILD_VCS_INFO | false | Whether to include version control information in autobuild-package.xml |
| AUTOBUILD_VCS_REVISION | git commit | autobuild-package.xml VCS commit reference to include in autobuild-package.xml. Defaults to current git commit sha. |
| AUTOBUILD_VCS_URL | git remote url | autobuild-package.xml VCS info: repository URL |
| AUTOBUILD_VSVER | - | Target Visual Studio version to use on windows |
