# Development Guide

## Prerequisites

Before developing this project, ensure you have the following installed:

### [uv](https://docs.astral.sh/uv/)  
Python project and environment management.  
Install: [uv docs](https://docs.astral.sh/uv/getting-started/installation/)

### [make](https://www.gnu.org/software/make/)  
Run common project tasks via the `Makefile`.

#### macOS  
```sh
xcode-select --install
```

#### Windows  
```powershell
choco install make
```

#### Linux
Usually pre-installed. If not:
```sh
sudo apt install build-essential   # Debian/Ubuntu
sudo dnf groupinstall "Development Tools"   # Fedora
```

### [git](https://git-scm.com/downloads)  
Version control, and what `make repo` uses to initialise the repository.

### [GitHub CLI](https://cli.github.com)  
Lets `make repo` create the GitHub remote and apply the branch policies.  
Authenticate once with `gh auth login`.

### [Docker](https://docs.docker.com/get-docker/)  
For building and running containerized deployments.


## Installation in development mode

Install all dependencies including development tools:

```bash
uv sync
```

This creates a `.venv` folder and installs the project and default development
dependencies from `pyproject.toml` and the committed `uv.lock` file. After changing
dependencies, use `uv add`/`uv remove`, then run `uv lock` and commit the lockfile.

Activate the environment:

* **Linux / macOS (bash/zsh):**
  ```bash
  source .venv/bin/activate
  ```

* **Windows (PowerShell):**
  ```powershell
  .venv\Scripts\Activate.ps1
  ```

* **Windows (cmd.exe):**
  ```cmd
  .venv\Scripts\activate.bat
  ```

## Development Tasks

All tasks are defined in the `Makefile` for convenience.

### Running the Full Quality Gate

```bash
make qa
```

Runs **Ruff** for linting and formatting, **Mypy** for type checking, and **Pytest** for
the test suite. Each stage is also available on its own: `make lint`, `make format`,
`make typecheck` and `make test`.

### Running Unit Tests

Before running tests, configure environment variables in `.env.test` if needed.

```bash
make test
```

Executes the test suite using **Pytest**, without the lint, format and type checks.

### Recording the README demo GIF

`docs/demo.gif` is a scripted browser walkthrough of the demo database. Recreate it whenever
the UI changes visibly.

**Storyboard** (1200×760 viewport, a visible cursor that moves to each target before
clicking, short pauses so every state is readable; about 80 s in total):

1. **Home**: hold for about 2 s.
2. **Exam**: click the *Esame* card, then *Inizia l'esame* on the setup page. Click the
   correct answer for questions 1 to 5. Jump back to question 2 from the number strip and
   answer it wrong. Jump to question 6 and answer the rest correctly with the `V` / `F` keys,
   quickly, as a fast-forward. Click *Consegna*.
3. **Result**: 29/30 *Promosso!*. Hold, then set the level of the question to review to
   *Difficile*.
4. **Storico**: hover across the progress chart from left to right so the tooltips show.
5. **Esercitazione setup**: turn off the *Facile* chip, pick the *10* preset, turn on
   *Solo domande sbagliate* and open the *Capitoli* picker. Start.
6. **Practice**: answer one question correctly and let it auto-advance. Answer the next one
   wrong, set its level to *Difficile* and click *Avanti*. On the third, click
   *Mostra la risposta*, then *Avanti*.
7. **Domande**: open *Segnali di pericolo* and scroll a little. Mark two questions as seen
   with the eye toggle, set one level to *Difficile*, turn on *Nascondi risposte* and tap two
   answer badges to reveal them. Scroll back up.
8. **Home**: click the logo and hold on the dashboard.

**How it was recorded**

- Run `uv run python scripts/seed_demo.py`, then serve `data/demo.db` on port 8001 as
  `make demo` does. The seed deletes and recreates the file, so restart the server after
  every re-seed.
- Drive Chromium with Playwright (`uv run --with playwright ...`). An init script draws a
  fake cursor that follows `mousemove` and shrinks on `mousedown`, and it keeps its position
  in `sessionStorage` across navigations. Click with `page.mouse.move(..., steps=22)` followed
  by `down` and `up`, instead of `locator.click()`, so the cursor visibly travels.
- Exam answers are not in the page. Read the right ones from `data/demo.db` by joining
  `attemptanswer` and `question` on the attempt id in the URL. Practice cards with instant
  feedback expose the answer in `data-answer`.
- Level buttons use the enum values, as in `.level-option.level-hard` and
  `label.level-chip.level-easy`. Pressing a level control cancels the practice auto-advance,
  so click *Avanti* afterwards.
- Capture frames with a CDP screencast (`Page.startScreencast`, PNG format), not Playwright's
  video recording. The VP8 video is noisy, and GIF frame-diffing then makes a file over 10 MB.
  Write each frame's timestamp into an ffmpeg concat list (`file` and `duration` lines).
- Build the GIF (about 1.7 MB):

  ```bash
  ffmpeg -f concat -safe 0 -i frames.txt \
    -vf "fps=15,mpdecimate=max=0:hi=1:lo=1:frac=0,split[a][b];[a]palettegen=max_colors=256:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle" \
    -fps_mode vfr -loop 0 -final_delay 350 docs/demo.gif
  ```

  `-final_delay` keeps the last frame on screen, because `mpdecimate` drops the duplicate
  frames of the final hold.

### Creating the Repository

Initialise the local repository and create its first commit on `main`:

```bash
make repo
```

The same command then creates the GitHub remote, pushes `main`, and applies the branch
policies. The remote is private by default; to make it public:

```bash
make repo REPO_ARGS=--public
```

`main` is protected: pull requests need one approval including the code owner, all
conversations resolved, the branch up to date with `main`, linear history, and the `qa`
check green. Force pushes and branch deletion are rejected.

Branch rulesets are a paid GitHub feature on private repositories. On a free plan the
command says so, leaves `main` unprotected and finishes the rest; make the repository
public or upgrade the plan, then re-run `make repo` to apply the policies.

The local steps need only git; the remote ones need the
[GitHub CLI](https://cli.github.com) authenticated with `gh auth login`. Without it the
local repository is still created and nothing is pushed.

The command is safe to re-run: each step is skipped if it is already done, so an
interrupted run can be finished by running it again.

### Migrating to Git Worktrees

Migrate the repository to a shared bare-repository layout:

```bash
make worktree
```

This creates `.bare` for the shared Git history and a directory for the current
branch. If the current branch is not the remote default branch, a second directory
is created for that default branch. The converted repository root contains only
`.bare`, the `.git` pointer, and the worktree directories. Before converting, it
copies the complete original repository, including `.git`, to a sibling directory
named `<repo-name>-legacy-bak`, restores the original files to the current branch
worktree, and refuses to overwrite an existing backup or worktree layout. If the
migration fails, the original repository is restored and the temporary backup is
removed.

### Building the Project

```bash
make build
```

Generates a distribution package in the `dist/` directory.

### Releasing

Every push to `main` that passes QA cuts a release: the version is finalized,
tagged, and `main` is bumped to the next prerelease. You can control the release
process with the following options on the `.github/workflows/release.yml` workflow:

- `create-github-release` (on by default) — cuts a GitHub release for the new tag.
- `attach-distribution` (off by default) — builds the distribution and attaches it to the
  GitHub release as downloadable files. Requires `create-github-release` to also be on.
- `publish-to-pypi` (off by default) — builds the distribution and publishes it to PyPI.
  Only relevant if you distribute this project as a package.
- `publish-docker-image` (off by default) — builds the Dockerfile and pushes the image to the
  GitHub Container Registry.
- `prepare-next-version` (on by default) — bumps `main` to the next prerelease once the
  release is out.

#### Publishing to PyPI

Set up Trusted Publishing so no API token has to be stored as a secret:

1. Go to <https://pypi.org/manage/account/publishing/>
2. Under "Add a new pending publisher," choose GitHub Actions
3. Fill in the workflow name `release.yml` and the environment name `pypi`
4. Save. PyPI will now trust publish requests coming from that workflow.

Then, in `.github/workflows/release.yml`, add `id-token: write` to `permissions`, enable
`publish-to-pypi`, and point the deployment environment at the project:

```yaml
    permissions:
      contents: write
      id-token: write
    with:
      cookie-pyrate-ref: ...
      publish-to-pypi: true
      pypi-project-url: https://pypi.org/project/patente_pronta/
```

Without `id-token: write` the whole workflow fails to start, so add it in the same edit.

#### Publishing a Docker image

In `.github/workflows/release.yml`, add `packages: write` to `permissions` and enable
`publish-docker-image`:

```yaml
    permissions:
      contents: write
      packages: write
    with:
      cookie-pyrate-ref: ...
      publish-docker-image: true
```

Each release then pushes `ghcr.io/<owner>/patente-pronta`, tagged with the version
and `latest`. Without `packages: write` the push is refused and the image job fails.

New packages on the GitHub Container Registry are private. Make the package public in its
settings on GitHub, or run `docker login ghcr.io` with a token that has the `read:packages`
scope before pulling. Images are built for `linux/amd64`; set `docker-platforms` (for example
`linux/amd64,linux/arm64`) to build for more.

### Cleaning Up

```bash
make clean
```

Removes build artifacts, caches, and temporary files.


### Building a Docker Image

```bash
make dockerimage
```

Generates a Docker image with the package pre-installed and ready to use. The Dockerfile uses
BuildKit features, so Docker needs the buildx plugin; without it the build stops with
"the --mount option requires BuildKit".





