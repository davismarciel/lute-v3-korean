# Sprint 1 validation

Environment: Linux, Python 3.14.4, Lute 3.10.3, Kiwi 0.23.2, model 0.23.0.
Dependencies installed in an isolated environment under `/tmp`; all application
and database integration checks use temporary test data, never docker/my_data.
The previously uninitialized upstream language-definitions submodule was checked
out at the commit already recorded by this fork. No submodule files were edited.

Commands (with that virtual environment activated):

```sh
python -m pytest plugins/lute-korean/tests -q
python -m pytest plugins/lute-korean/tests tests/unit/parse tests/unit/language tests/unit/read/render tests/unit/book --ignore=tests/unit/parse/test_JapaneseParser.py -q
python -m pylint plugins/lute-korean/lute_korean_parser --disable=duplicate-code --score=n
uv build plugins/lute-korean --out-dir /tmp/lute-korean-dist
```

- Combined run: 150 passed (52 new, 98 existing).
- Initial existing-tests run including Japanese: 98 passed, 5 failed because
  libmecab.so/mecab-config are absent. Japanese tests were excluded from the
  combined run; no changes were made to Japanese or its tests.
- New tests cover every requested sentence, conjugated lemmas, particles,
  past/polite morphology, context, desire/future evidence, mixed scripts,
  punctuation/whitespace/paragraphs, zero-length copulas, unknown input,
  missing analysis and explicit model errors.
- App test-client check: startup, predefined-language selection and loading,
  UTF-8 transcript import, reading route and term form, stored surface term
  lookup/rendering, and compatibility with existing multiword terms.
- Wheel and source distribution built; wheel contains the language definition
  and both parser and CLI entry points.

Reading was checked through the Flask test client and rendering services, without
browser automation. Windows execution was not tested. No Sprint 2 functionality,
core code or database migrations were introduced.

For existing tests, upstream requires `lute/config/config.yml` with ENV: dev,
a temporary DATAPATH, and a DBNAME beginning with test_. A temporary ignored
config was used and removed after validation.
