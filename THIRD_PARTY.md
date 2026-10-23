# Third-party components

## Bundled fonts

Unmodified files from the Google Fonts repository:

- NanumMyeongjo-Regular.ttf and NanumMyeongjo-Bold.ttf: https://github.com/google/fonts/tree/main/ofl/nanummyeongjo
- NanumGothic-Bold.ttf: https://github.com/google/fonts/tree/main/ofl/nanumgothic

They are distributed under their SIL Open Font Licenses. The full copyright and license texts are bundled in `src/math_testpaper/assets/fonts/OFL-NanumMyeongjo.txt` and `OFL-NanumGothic.txt`. These font licenses are independent of this repository's code license.

HY fonts are optional installed-system inputs. They are not bundled, extracted from source exams, or uploaded.

## Installed dependencies

MathJax 3.2.2: https://github.com/mathjax/MathJax-src/tree/3.2.2 (Apache-2.0). It is installed with npm, not copied into this repository. This project uses its local TeX-to-SVG interface. Version 3 is deliberately pinned for the tested vector output; migration to version 4 needs new output tests. The transitive xmldom dependency is overridden to 0.9.12.

Python dependencies are declared in pyproject.toml and tested versions in requirements-lock.txt. Their own licenses apply to installed copies. PDFium is provided through pypdfium2; its package includes the applicable PDFium third-party notices.

## Layout reference and examples

The template geometry was measured from KICE secondary-school mathematics exam PDFs supplied by the user. No official KICE PDF, logo, extracted font subset, or exam content is distributed in this repository. The template is an unofficial layout inspired by those papers.

The demonstration questions and parabola diagram in `examples/` were authored for this project. User-supplied exams retain their original rights. Jobs and source PDFs are excluded by .gitignore.
