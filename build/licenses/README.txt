Drop third-party licence texts here; build/build.ps1 copies every file in this
folder into  build/dist/Photo-to-IPT Builder/licenses/  on each build.

Required before distributing the .exe outside your machine:

  LGPL-3.0.txt   - the GNU Lesser General Public License v3.0
                   https://www.gnu.org/licenses/lgpl-3.0.txt
                   (PySide6 / Qt is used under LGPL-3.0; the PyPI wheels do NOT
                    bundle the full text, only a Qt-Commercial reference.)

Optional:

  GPL-3.0.txt    - LGPL-3.0 incorporates GPL-3.0 by reference
                   https://www.gnu.org/licenses/gpl-3.0.txt

build.ps1 also auto-copies whatever licence files the installed
pyside6*/shiboken6* wheels ship in their .dist-info/licenses/ folders, and
writes THIRD-PARTY-NOTICES.txt next to the .exe.
