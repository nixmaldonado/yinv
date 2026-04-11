# Releasing yinv

## Pre-release checklist

Before pushing to a public GitHub repo or publishing to PyPI:

### Privacy audit

Maintain a **local, uncommitted** list of your real private values — client
name, personal name, home address tokens, client address tokens, account
number, routing number, SWIFT/BIC, bank name. Call it something you'll
recognize (e.g. `~/.yinv-privacy-audit-terms` — add it to your global
`~/.gitignore_global`).

Then, from the repo root:

```sh
# Every term must return zero matches:
while IFS= read -r term; do
  echo "=== $term ==="
  git grep -i -- "$term" || true
done < ~/.yinv-privacy-audit-terms
```

As a positive control, confirm the synthetic fixture tokens **do** appear —
this proves the fixture is still synthetic and hasn't been silently replaced
with real data:

```sh
git grep -i "0000000000"   # should return tests/fixtures/example.yaml + seed.yaml
git grep -i "TESTUS00"     # should return tests/fixtures/example.yaml
```

If the real terms return any matches, **stop**. Do not push. Remove the
leaked data and re-run.

## Release steps

1. Update `CHANGELOG.md` — move `[Unreleased]` entries under a new
   `[X.Y.Z] - YYYY-MM-DD` section.
2. Bump version in `pyproject.toml`.
3. Commit + tag: `git commit -am "Release vX.Y.Z" && git tag vX.Y.Z`.
4. Push: `git push && git push --tags`.
5. Build: `uv build` (or `python -m build`).
6. Publish: `uv publish` (or `twine upload dist/*`).
7. Verify the package landed on PyPI: https://pypi.org/project/yinv/

## Homebrew formula (first release only)

1. Generate resource blocks from PyPI:
   ```sh
   pipx run homebrew-pypi-poet -f yinv
   ```
2. Create a personal tap repo on GitHub: `homebrew-yinv`.
3. Add `Formula/yinv.rb`:
   ```ruby
   class Yinv < Formula
     include Language::Python::Virtualenv

     desc "CLI to generate monthly consulting invoices as PDFs"
     homepage "https://github.com/<user>/invoiceGenerator"
     url "https://files.pythonhosted.org/packages/source/y/yinv/yinv-X.Y.Z.tar.gz"
     sha256 "<sha from PyPI>"
     license "MIT"

     depends_on "pango"
     depends_on "gdk-pixbuf"
     depends_on "libffi"
     depends_on "python@3.12"

     # <resource blocks from homebrew-pypi-poet output>

     def install
       virtualenv_install_with_resources
     end

     test do
       assert_match "yinv", shell_output("#{bin}/yinv --help")
     end
   end
   ```
4. Commit and push the tap.
5. Install from the tap:
   ```sh
   brew tap <user>/yinv
   brew install yinv
   ```

## Subsequent releases

1. Do the privacy audit again (secrets can accumulate over time).
2. Update `CHANGELOG.md`, bump version, tag, push, `uv build && uv publish`.
3. In the tap repo, update `url`, `sha256`, and re-run
   `homebrew-pypi-poet -f yinv` to refresh the resource blocks.
4. Commit the updated formula, push the tap.
