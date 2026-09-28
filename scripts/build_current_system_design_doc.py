"""Build the formal edition of the Qizhi design document.

The implementation remains in ``build_project_design_doc.py`` so the existing
diagram and typography helpers stay in one place.  This explicit entry point
keeps the deliverable name clear for future maintainers.
"""

from build_project_design_doc import build


if __name__ == "__main__":
    build()
