"""Run one M0 command while recording wall time, RSS, GPU memory, and output."""

import argparse
import datetime
import json
import os
import subprocess
import time


def process_rss_kib(pid):
    try:
        with open("/proc/%d/status" % pid) as infile:
            fields = {}
            for line in infile:
                key, _, value = line.partition(":")
                fields[key] = value.strip()
        return int(fields.get("VmRSS", "0 kB").split()[0])
    except (FileNotFoundError, ProcessLookupError, ValueError):
        return 0


def gpu_memory_mib(pid):
    command = [
        "nvidia-smi", "--query-compute-apps=pid,used_memory",
        "--format=csv,noheader,nounits",
    ]
    try:
        output = subprocess.check_output(
            command, text=True, stderr=subprocess.DEVNULL, timeout=5
        )
    except (subprocess.SubprocessError, OSError):
        return 0
    for line in output.splitlines():
        columns = [x.strip() for x in line.split(",")]
        if len(columns) == 2 and columns[0] == str(pid):
            try:
                return int(columns[1])
            except ValueError:
                return 0
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--stdout_log", required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("a command is required after --")

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(args.stdout_log)), exist_ok=True)
    started_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    start = time.monotonic()
    peak_rss_kib = 0
    peak_gpu_memory_mib = 0
    with open(args.stdout_log, "w") as logfile:
        process = subprocess.Popen(
            command, stdout=logfile, stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        while process.poll() is None:
            peak_rss_kib = max(peak_rss_kib, process_rss_kib(process.pid))
            peak_gpu_memory_mib = max(
                peak_gpu_memory_mib, gpu_memory_mib(process.pid)
            )
            time.sleep(0.25)
        returncode = process.wait()
    finished_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    report = {
        "measurement_schema": "m0.run_measure.v1",
        "command": command,
        "started_at_utc": started_at,
        "finished_at_utc": finished_at,
        "wall_time_seconds": time.monotonic() - start,
        "peak_process_rss_kib": peak_rss_kib,
        "peak_process_gpu_memory_mib": peak_gpu_memory_mib,
        "returncode": returncode,
        "stdout_log": os.path.abspath(args.stdout_log),
    }
    with open(args.output, "w") as outfile:
        json.dump(report, outfile, sort_keys=True, indent=2)
    print(json.dumps(report, sort_keys=True, indent=2))
    raise SystemExit(returncode)


if __name__ == "__main__":
    main()
