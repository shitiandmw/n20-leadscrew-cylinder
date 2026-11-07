"""Freerouting 2.1.0 with its command-line timeout fixed.

2.1.0 routes this board best of the versions tried (DESIGN.md, Routing), but on the command line it can
hang at the end of a run and never write the session. In its source, at the jar's build revision:
- RoutingJobSchedulerActionThread's monitor asks the job to stop at the job timeout, waits up to 30 s,
  then sets the job's state to TIMED_OUT, even if the job has just finished and set COMPLETED;
- Freerouting.InitializeCLI waits only for COMPLETED or TERMINATED, and saves only on COMPLETED.

Whether the CLI sees COMPLETED in the moment before it is overwritten is a race, so a run either writes
its session or sleeps for ever. A thread dump of a hung run (2026-11-05) showed exactly that: the router
thread gone and `main` sleeping in InitializeCLI.

The patch changes InitializeCLI only:
- it also stops waiting on TIMED_OUT;
- it waits up to 60 s for the job thread to finish;
- it then writes the session of the job's final board, as the job thread itself does after each update.

The patched class is compiled against the original jar in the official Eclipse Temurin JDK image, with
no network, and swapped into a copy of the jar; every other entry is copied unchanged. The original source is fetched once from GitHub at the
jar's build revision (its manifest's Build-Revision) and checked against a SHA-256.
"""
import hashlib
import os
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

FREEROUTING = "ghcr.io/freerouting/freerouting:2.1.0"
JAR_SHA256 = "edba23d8b7e048821992a4f2360d64185f5bd47556844b26ded6cb28fd791fbb"   # /app/freerouting-executable.jar
REVISION = "89512b982cbe8d00cccc1837823d9cdcd7c24c8a"                             # the jar's Build-Revision
SRC_URL = f"https://raw.githubusercontent.com/freerouting/freerouting/{REVISION}/src/main/java/app/freerouting/Freerouting.java"
SRC_SHA256 = "fcc58e7276ee3464545449e05730d6e90a3c5589cf1f1e4ee55915a1784a3cb7"
JDK = "eclipse-temurin:21-jdk"
CACHE = Path(os.environ.get("X1_FREEROUTING_CACHE", "/tmp/x1-freerouting"))
JAR = "freerouting-2.1.0-x1.jar"

EDITS = [
    ("    while ((routingJob.state != RoutingJobState.COMPLETED) && (routingJob.state != RoutingJobState.TERMINATED))\n",
     "    // X1 patch: a job that reaches its timeout ends in TIMED_OUT, even if it completed just before\n"
     "    while ((routingJob.state != RoutingJobState.COMPLETED) && (routingJob.state != RoutingJobState.TERMINATED)\n"
     "        && (routingJob.state != RoutingJobState.TIMED_OUT))\n"),
    ("    // Print the serialized routingJob statistics to the console\n",
     "    // X1 patch: let the job thread finish its last pass (up to 60 s), so that its board is the final one\n"
     "    for (int i = 0; (i < 120) && (routingJob.finishedAt == null); i++)\n"
     "    {\n"
     "      try\n"
     "      {\n"
     "        Thread.sleep(500);\n"
     "      } catch (InterruptedException e)\n"
     "      {\n"
     "        break;\n"
     "      }\n"
     "    }\n"
     "\n"
     "    // Print the serialized routingJob statistics to the console\n"),
    ("""    if (routingJob.state == RoutingJobState.COMPLETED)
    {
      try
      {
        Path outputFilePath = Path.of(globalSettings.design_output_filename);
        Files.write(outputFilePath, routingJob.output
            .getData()
            .readAllBytes());
      } catch (IOException e)
""",
     """    // X1 patch: also save a timed-out job, from its final board (as the job thread does after each update)
    if ((routingJob.state == RoutingJobState.COMPLETED) || (routingJob.state == RoutingJobState.TIMED_OUT))
    {
      try (java.io.ByteArrayOutputStream baos = new java.io.ByteArrayOutputStream())
      {
        var boardManager = new app.freerouting.interactive.HeadlessBoardManager(null, routingJob);
        boardManager.replaceRoutingBoard(routingJob.board);
        if (!boardManager.saveAsSpecctraSessionSes(baos, routingJob.name))
        {
          throw new IOException("the session could not be written");
        }
        Files.write(Path.of(globalSettings.design_output_filename), baos.toByteArray());
        FRLogger.info("X1 patch: session written, job state " + routingJob.state);
      } catch (IOException e)
"""),
]


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"failed: {' '.join(cmd)}\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
    return r


def patched_jar():
    """Path of the patched jar, built on first use. Mount its folder and run `java -jar <folder>/<JAR>`."""
    out = CACHE / JAR
    if out.exists() and (CACHE / (JAR + ".sha256")).exists() and \
            (CACHE / (JAR + ".sha256")).read_text().strip() == _sha(out):
        return out
    CACHE.mkdir(parents=True, exist_ok=True)
    uid = f"{os.getuid()}:{os.getgid()}"
    orig = CACHE / "freerouting-2.1.0.jar"
    _run(["docker", "run", "--rm", "--network", "none", "--user", uid, "-v", f"{CACHE}:/out", "--entrypoint", "cp",
          FREEROUTING, "/app/freerouting-executable.jar", f"/out/{orig.name}"])
    if _sha(orig) != JAR_SHA256:
        sys.exit(f"{FREEROUTING} has a different jar than the one this patch was made for")
    src = urllib.request.urlopen(SRC_URL, timeout=60).read()
    if hashlib.sha256(src).hexdigest() != SRC_SHA256:
        sys.exit(f"unexpected source at {SRC_URL}")
    text = src.decode()
    for old, new in EDITS:
        if text.count(old) != 1:
            sys.exit(f"patch does not apply: {old[:60]!r}")
        text = text.replace(old, new)
    (CACHE / "src").mkdir(exist_ok=True)
    (CACHE / "src" / "Freerouting.java").write_text(text)
    _run(["docker", "run", "--rm", "--network", "none", "--user", uid, "-e", "HOME=/tmp", "-v", f"{CACHE}:/w",
          "--entrypoint", "sh", JDK, "-c", f"rm -rf /w/classes && javac -proc:none --release 21 -nowarn "
          f"-cp /w/{orig.name} -d /w/classes /w/src/Freerouting.java"])
    # swap the compiled classes into a copy of the jar; every other entry is copied unchanged
    cls = CACHE / "classes" / "app" / "freerouting"
    new = {f"app/freerouting/{f.name}": f.read_bytes() for f in cls.iterdir()
           if f.name == "Freerouting.class" or f.name.startswith("Freerouting$")}
    tmp = CACHE / (JAR + ".tmp")
    with zipfile.ZipFile(orig) as zi, zipfile.ZipFile(tmp, "w") as zo:
        for info in zi.infolist():
            data = new.pop(info.filename, None)
            zo.writestr(info, zi.read(info) if data is None else data, compress_type=info.compress_type)
        for name, data in new.items():                    # inner classes the original did not have
            zo.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED)
    tmp.replace(out)
    (CACHE / (JAR + ".sha256")).write_text(_sha(out) + "\n")
    return out


if __name__ == "__main__":
    print(patched_jar())
