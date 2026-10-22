"""Terminate and reap descendants only through an owned Popen handle."""

import subprocess

import psutil


def stop_process(process):
    if process.poll() is None:
        try:
            children = psutil.Process(process.pid).children(recursive=True)
        except psutil.NoSuchProcess:
            children = []
        # Windows venv python.exe can be a launcher for another python.exe.
        # Stop its descendants as well; killing the launcher alone leaves the job alive.
        for child in reversed(children):
            try:
                child.terminate()
            except psutil.NoSuchProcess:
                pass
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)
        _, alive = psutil.wait_procs(children, timeout=3)
        for child in alive:
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
        _, survivors = psutil.wait_procs(alive, timeout=3)
        if survivors:
            raise RuntimeError("Unable to stop job descendants")
