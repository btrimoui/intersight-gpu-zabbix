#!/usr/bin/env python3

import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone

import requests

CONFIG = {
    "intersight_base_url": "https://eu-central-1.intersight.com",
    "token_url": "https://eu-central-1.intersight.com/iam/token",
    "client_id": "",
    "client_secret": "",
    "verify_ssl": True,

    "zabbix_sender": "/usr/bin/zabbix_sender",
    "zabbix_server": "127.0.0.1",
    "zabbix_port": 10051,
    "zabbix_host": "",

    "window_minutes": 60,
    "granularity_minutes": 10,
    "timeout": 600
}


def iso_now_utc():
    return datetime.now(timezone.utc)


def to_iso(dt):
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def to_epoch(ts):
    if not ts:
        return None
    return int(datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp())


def get_token():
    payload = {"grant_type": "client_credentials"}

    response = requests.post(
        CONFIG["token_url"],
        data=payload,
        auth=(CONFIG["client_id"], CONFIG["client_secret"]),
        verify=CONFIG["verify_ssl"],
        timeout=CONFIG["timeout"]
    )
    response.raise_for_status()

    data = response.json()
    token = data.get("access_token")
    if not token:
        raise RuntimeError(f"No access_token in token response: {data}")
    return token


def post_timeseries(token, query):
    url = f"{CONFIG['intersight_base_url']}/api/v1/telemetry/TimeSeries"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    response = requests.post(
        url,
        headers=headers,
        json=query,
        verify=CONFIG["verify_ssl"],
        timeout=CONFIG["timeout"]
    )
    response.raise_for_status()
    return response.json()


def build_time_window():
    end = iso_now_utc()
    start = end - timedelta(minutes=CONFIG["window_minutes"])
    start_iso = to_iso(start)
    end_iso = to_iso(end)
    interval = f"{start_iso}/{end_iso}"

    granularity = {
        "type": "period",
        "period": f"PT{CONFIG['granularity_minutes']}M",
        "timeZone": "UTC",
        "origin": start_iso
    }
    return interval, granularity


def build_query_gpu(interval, granularity):
    return {
        "queryType": "groupBy",
        "dataSource": "PhysicalEntities",
        "intervals": [interval],
        "granularity": granularity,
        "dimensions": [
            "moid",
            "host.id",
            "name",
            "hw.gpu.controller_id"
        ],
        "filter": {
            "type": "selector",
            "dimension": "instrument.name",
            "value": "hw.gpu"
        },
        "aggregations": [
            {"type": "doubleMax", "name": "gpu_utilization_max", "fieldName": "hw.gpu.utilization"},
            {"type": "doubleMin", "name": "gpu_utilization_min", "fieldName": "hw.gpu.utilization"},
            {"type": "doubleSum", "name": "gpu_utilization_sum", "fieldName": "hw.gpu.utilization"},
            {"type": "longSum", "name": "gpu_utilization_count", "fieldName": "hw.gpu.utilization_count"},

            {"type": "doubleMax", "name": "gpu_power_max", "fieldName": "hw.gpu.power"},
            {"type": "doubleMin", "name": "gpu_power_min", "fieldName": "hw.gpu.power"},
            {"type": "doubleSum", "name": "gpu_power_sum", "fieldName": "hw.gpu.power"},
            {"type": "longSum", "name": "gpu_power_count", "fieldName": "hw.gpu.power_count"},

            {"type": "longMax", "name": "gpu_pcie_link_gen_max", "fieldName": "hw.gpu.pcie_link_gen"},
            {"type": "longMin", "name": "gpu_pcie_link_gen_min", "fieldName": "hw.gpu.pcie_link_gen"},

            {"type": "longMax", "name": "gpu_pcie_link_width_max", "fieldName": "hw.gpu.pcie_link_width"},
            {"type": "longMin", "name": "gpu_pcie_link_width_min", "fieldName": "hw.gpu.pcie_link_width"},

            {"type": "longMax", "name": "gpu_clockspeed_max", "fieldName": "hw.gpu.clockspeed"},
            {"type": "longMin", "name": "gpu_clockspeed_min", "fieldName": "hw.gpu.clockspeed"},
            {"type": "doubleSum", "name": "gpu_clockspeed_sum", "fieldName": "hw.gpu.clockspeed"},
            {"type": "longSum", "name": "gpu_clockspeed_count", "fieldName": "hw.gpu.clockspeed_count"},

            {"type": "longMax", "name": "gpu_memory_clockspeed_max", "fieldName": "hw.gpu.memory.clockspeed"},
            {"type": "longMin", "name": "gpu_memory_clockspeed_min", "fieldName": "hw.gpu.memory.clockspeed"},
            {"type": "doubleSum", "name": "gpu_memory_clockspeed_sum", "fieldName": "hw.gpu.memory.clockspeed"},
            {"type": "longSum", "name": "gpu_memory_clockspeed_count", "fieldName": "hw.gpu.memory.clockspeed_count"},

            {"type": "doubleMax", "name": "gpu_memory_utilization_max", "fieldName": "hw.gpu.memory.utilization"},
            {"type": "doubleMin", "name": "gpu_memory_utilization_min", "fieldName": "hw.gpu.memory.utilization"},
            {"type": "doubleSum", "name": "gpu_memory_utilization_sum", "fieldName": "hw.gpu.memory.utilization"},
            {"type": "longSum", "name": "gpu_memory_utilization_count", "fieldName": "hw.gpu.memory.utilization_count"}
        ],
        "postAggregations": [
            {"type": "expression", "name": "gpu_utilization_avg", "expression": "(\"gpu_utilization_sum\" / \"gpu_utilization_count\")"},
            {"type": "expression", "name": "gpu_power_avg", "expression": "(\"gpu_power_sum\" / \"gpu_power_count\")"},
            {"type": "expression", "name": "gpu_clockspeed_avg", "expression": "(\"gpu_clockspeed_sum\" / \"gpu_clockspeed_count\")"},
            {"type": "expression", "name": "gpu_memory_clockspeed_avg", "expression": "(\"gpu_memory_clockspeed_sum\" / \"gpu_memory_clockspeed_count\")"},
            {"type": "expression", "name": "gpu_memory_utilization_avg", "expression": "(\"gpu_memory_utilization_sum\" / \"gpu_memory_utilization_count\")"}
        ]
    }


def build_query_temp(interval, granularity):
    return {
        "queryType": "groupBy",
        "dataSource": "PhysicalEntities",
        "intervals": [interval],
        "granularity": granularity,
        "dimensions": [
            "host.id",
            "name",
            "sensor_location"
        ],
        "filter": {
            "type": "selector",
            "dimension": "hw.temperature.sensor.name",
            "value": "GPU"
        },
        "aggregations": [
            {"type": "doubleMax", "name": "gpu_temperature_max", "fieldName": "hw.temperature_max"},
            {"type": "doubleMin", "name": "gpu_temperature_min", "fieldName": "hw.temperature_min"},
            {"type": "doubleSum", "name": "gpu_temperature_sum", "fieldName": "hw.temperature"},
            {"type": "longSum", "name": "gpu_temperature_count", "fieldName": "hw.temperature_count"}
        ],
        "postAggregations": [
            {"type": "expression", "name": "gpu_temperature_avg", "expression": "(\"gpu_temperature_sum\" / \"gpu_temperature_count\")"}
        ]
    }


def flatten_events(resp):
    events = []
    if isinstance(resp, list):
        for row in resp:
            event = row.get("event")
            ts = row.get("timestamp")
            if event:
                event["__ts"] = ts
                events.append(event)
    return events


def get_blade_moid(event):
    host_id = event.get("host.id")
    if not host_id:
        return ""
    return str(host_id).split("/")[-1]


def get_physical_key(event):
    blade = get_blade_moid(event)
    name = event.get("name")
    if not blade or not name:
        return ""
    return f"{blade}_{name}"


def get_ctrl_id(event):
    val = event.get("hw.gpu.controller_id")
    if val in (None, ""):
        return ""
    return str(val)


def get_sensor_ctrl(event):
    val = event.get("sensor_location")
    if not val:
        return ""
    m = re.search(r"gpu_core_(\d+)", str(val), re.IGNORECASE)
    if not m:
        return ""
    return str(int(m.group(1)))


def round1(v):
    if v is None:
        return None
    return round(float(v), 1)


def build_ctrl_map(gpu_events):
    ctrl_map = {}
    for e in gpu_events:
        pkey = get_physical_key(e)
        cid = get_ctrl_id(e)
        if not pkey or not cid:
            continue
        ctrl_map.setdefault(pkey, {})
        ctrl_map[pkey][cid] = 1
    return ctrl_map


def set_metric_latest(out, gpu_id, ts, key, value):
    if not gpu_id or not ts or value is None:
        return

    if gpu_id not in out or not out[gpu_id].get("_ts") or ts > out[gpu_id]["_ts"]:
        out[gpu_id] = {"_ts": ts}

    if out[gpu_id]["_ts"] == ts:
        out[gpu_id][key] = value


def process_metrics(gpu_events, temp_events):
    out = {}
    ctrl_map = build_ctrl_map(gpu_events)

    for e in gpu_events:
        pkey = get_physical_key(e)
        if not pkey:
            continue

        cid = get_ctrl_id(e)
        multi = pkey in ctrl_map and len(ctrl_map[pkey]) > 1
        gpu_id = f"{pkey}_C{cid}" if multi and cid else pkey

        ts = to_epoch(e.get("__ts") or e.get("timestamp") or e.get("time") or e.get("bucket_time") or e.get("bucketTime"))
        if not ts:
            continue

        set_metric_latest(out, gpu_id, ts, "utilization_max", e.get("gpu_utilization_max"))
        set_metric_latest(out, gpu_id, ts, "utilization_min", e.get("gpu_utilization_min"))
        set_metric_latest(out, gpu_id, ts, "utilization_avg", round1(e.get("gpu_utilization_avg")))

        set_metric_latest(out, gpu_id, ts, "power_max", e.get("gpu_power_max"))
        set_metric_latest(out, gpu_id, ts, "power_min", e.get("gpu_power_min"))
        set_metric_latest(out, gpu_id, ts, "power_avg", round1(e.get("gpu_power_avg")))

        set_metric_latest(out, gpu_id, ts, "pcie_gen_max", e.get("gpu_pcie_link_gen_max"))
        set_metric_latest(out, gpu_id, ts, "pcie_gen_min", e.get("gpu_pcie_link_gen_min"))

        set_metric_latest(out, gpu_id, ts, "pcie_width_max", e.get("gpu_pcie_link_width_max"))
        set_metric_latest(out, gpu_id, ts, "pcie_width_min", e.get("gpu_pcie_link_width_min"))

        set_metric_latest(out, gpu_id, ts, "clock_max", e.get("gpu_clockspeed_max"))
        set_metric_latest(out, gpu_id, ts, "clock_min", e.get("gpu_clockspeed_min"))
        set_metric_latest(out, gpu_id, ts, "clock_avg", round1(e.get("gpu_clockspeed_avg")))

        set_metric_latest(out, gpu_id, ts, "mem_clock_max", e.get("gpu_memory_clockspeed_max"))
        set_metric_latest(out, gpu_id, ts, "mem_clock_min", e.get("gpu_memory_clockspeed_min"))
        set_metric_latest(out, gpu_id, ts, "mem_clock_avg", round1(e.get("gpu_memory_clockspeed_avg")))

        set_metric_latest(out, gpu_id, ts, "mem_util_max", e.get("gpu_memory_utilization_max"))
        set_metric_latest(out, gpu_id, ts, "mem_util_min", e.get("gpu_memory_utilization_min"))
        set_metric_latest(out, gpu_id, ts, "mem_util_avg", round1(e.get("gpu_memory_utilization_avg")))

    for e in temp_events:
        pkey = get_physical_key(e)
        if not pkey:
            continue

        multi = pkey in ctrl_map and len(ctrl_map[pkey]) > 1
        sctrl = get_sensor_ctrl(e)
        gpu_id = f"{pkey}_C{sctrl}" if multi and sctrl else pkey

        ts = to_epoch(e.get("__ts") or e.get("timestamp") or e.get("time") or e.get("bucket_time") or e.get("bucketTime"))
        if not ts:
            continue

        set_metric_latest(out, gpu_id, ts, "temperature_max", e.get("gpu_temperature_max"))
        set_metric_latest(out, gpu_id, ts, "temperature_min", e.get("gpu_temperature_min"))
        set_metric_latest(out, gpu_id, ts, "temperature_avg", round1(e.get("gpu_temperature_avg")))

    return out


def build_sender_lines(metrics):
    lines = []

    for gpu_id, m in metrics.items():
        ts = m.get("_ts")
        if not ts:
            continue

        entries = [
            (f"gpu.clockspeed.bucketmax[{gpu_id}]", m.get("clock_max")),
            (f"gpu.clockspeed.bucketmin[{gpu_id}]", m.get("clock_min")),
            (f"gpu.clockspeed[{gpu_id}]", m.get("clock_avg")),

            (f"gpu.memclockspeed.bucketmax[{gpu_id}]", m.get("mem_clock_max")),
            (f"gpu.memclockspeed.bucketmin[{gpu_id}]", m.get("mem_clock_min")),
            (f"gpu.memclockspeed[{gpu_id}]", m.get("mem_clock_avg")),

            (f"gpu.memused.bucketmax[{gpu_id}]", m.get("mem_util_max")),
            (f"gpu.memused.bucketmin[{gpu_id}]", m.get("mem_util_min")),
            (f"gpu.memused[{gpu_id}]", m.get("mem_util_avg")),

            (f"gpu.pcie.gen.bucketmin[{gpu_id}]", m.get("pcie_gen_min")),
            (f"gpu.pcie.gen[{gpu_id}]", m.get("pcie_gen_max")),

            (f"gpu.pcie.width.bucketmin[{gpu_id}]", m.get("pcie_width_min")),
            (f"gpu.pcie.width[{gpu_id}]", m.get("pcie_width_max")),

            (f"gpu.power.bucketmax[{gpu_id}]", m.get("power_max")),
            (f"gpu.power.bucketmin[{gpu_id}]", m.get("power_min")),
            (f"gpu.power[{gpu_id}]", m.get("power_avg")),

            (f"gpu.temp.bucketmax[{gpu_id}]", m.get("temperature_max")),
            (f"gpu.temp.bucketmin[{gpu_id}]", m.get("temperature_min")),
            (f"gpu.temp[{gpu_id}]", m.get("temperature_avg")),

            (f"gpu.utilization.bucketmax[{gpu_id}]", m.get("utilization_max")),
            (f"gpu.utilization.bucketmin[{gpu_id}]", m.get("utilization_min")),
            (f"gpu.utilization[{gpu_id}]", m.get("utilization_avg")),
        ]

        for key, value in entries:
            if value is not None:
                lines.append(f"{CONFIG['zabbix_host']} {key} {ts} {value}")

    return lines


def send_to_zabbix(lines):
    if not lines:
        print("No data to send")
        return 0

    with tempfile.NamedTemporaryFile("w", delete=False) as f:
        tmpname = f.name
        for line in lines:
            f.write(line + "\n")

    try:
        cmd = [
            CONFIG["zabbix_sender"],
            "-z", CONFIG["zabbix_server"],
            "-p", str(CONFIG["zabbix_port"]),
            "-T",
            "-i", tmpname
        ]
        print("Running:", " ".join(cmd))
        print("First line:", lines[0])
        result = subprocess.run(cmd, capture_output=True, text=True)
        print(result.stdout)
        if result.returncode != 0:
            print(result.stderr, file=sys.stderr)
        return result.returncode
    finally:
        print("Kept sender file:", tmpname)
        pass

def main():
    interval, granularity = build_time_window()
    token = get_token()

    gpu_resp = post_timeseries(token, build_query_gpu(interval, granularity))
    temp_resp = post_timeseries(token, build_query_temp(interval, granularity))

    gpu_events = flatten_events(gpu_resp)
    temp_events = flatten_events(temp_resp)

    metrics = process_metrics(gpu_events, temp_events)
    lines = build_sender_lines(metrics)

    rc = send_to_zabbix(lines)
    sys.exit(rc)


if __name__ == "__main__":
    main()
