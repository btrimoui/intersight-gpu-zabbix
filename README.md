# intersight-gpu-zabbix
Cisco Intersight GPU Telemetry for Zabbix: Monitoring for UCS X-Series and C-Series GPUs using Python and Intersight API

This repository provides an automated monitoring solution that bridges Cisco Intersight cloud-based telemetry with on-premises Zabbix monitoring. It is optimized for Cisco UCS X-Series (X580p PCIe Nodes) and C-Series (M7/M8) servers.


🚀 Overview

The solution automates the discovery and performance tracking of GPU assets. It leverages the Intersight TimeSeries API to retrieve high-precision metrics—including time-weighted averages calculated directly by the Intersight backend—and pushes them into Zabbix.


Key Features

Backend-Calculated Precision: Utilizes Intersight’s internal Druid engine to provide mathematically accurate averages (Sum/Count logic), ensuring idle time is correctly represented without "snapshot bias."

Intelligent Discovery: Automatically detects single-controller (e.g., L40S) and multi-controller (e.g., A16) GPUs, mapping physical slot IDs (e.g., PCIe-Node2-GPU1) to their respective controllers.

License Aware: Compatible with both Intersight Essentials (10-min interval) and Advantage (1-min interval) tiers.

The precision of your monitoring depends on your Cisco Intersight license tier. You must align the granularity_minutes setting in the gpu_collector.py script with your license to ensure data consistency:


Intersight Essentials (Default):

Interval: 10 minutes.

Configuration: Set "granularity_minutes": 10 in the CONFIG dictionary.

Note: Data is aggregated locally by the Device Connector before being sent to the cloud.

Intersight Advantage:

Interval: 1 minute.

Configuration: Change "granularity_minutes": 1 in the CONFIG dictionary.

Benefit: This allows for high-resolution 1-minute charts in Zabbix, perfect for identifying short-lived performance spikes.


Zabbix 7.x Native: Fully compatible with Zabbix 7.0, utilizing native JSON preprocessing and Trapper items for efficient data ingestion.



🧠 How It Works

1. Discovery Phase

The Zabbix template includes a Discovery Rule (Server GPUs) that queries the Intersight Inventory API.


Logic: A JavaScript preprocessing script identifies the GPU model and bifurcates multi-controller cards (like the A16) into four distinct sub-entities.
Composite ID: It generates a unique {#COMPOSITE_ID} (e.g., BladeMoid_SlotID_C1) used to match incoming telemetry from the Python script.

2. Telemetry Retrieval

The Python script queries the Intersight TimeSeries API. The Intersight backend performs the heavy lifting by aggregating raw telemetry samples into a time-weighted average for the requested window. The script simply fetches these pre-calculated values (Utilization, Power, Temperature, etc.) and forwards them to Zabbix.



🛡️ Security & RBAC

Principle of Least Privilege

For maximum security, it is highly recommended to use a Read-Only account in Cisco Intersight for this integration.


Intersight Role: The system-defined Read-Only role provides all necessary permissions to access the Inventory and Telemetry TimeSeries APIs.
Zabbix Role: Ensure the Zabbix user account has the minimum required permissions to push trapper data to the specific host.

Credential Management

The security of OAuth2 credentials is the sole responsibility of the end-user.


Confidentiality: Never commit your Client ID or Secret Key to a public repository.
Secure Storage: Store your Intersight Secret Key file in a restricted directory with 600 permissions (e.g., /etc/zabbix/keys/).
Environment Variables: The Python script is designed to detect system environment variables for proxies (https_proxy) to avoid hardcoding sensitive network paths.


🛠️ Installation & Configuration

1. Import the Zabbix Template

Import the Cisco_Intersight_GPU_Metrics.yaml file into Zabbix (Data collection > Templates > Import).
Link the template to your Cisco Intersight Host in Zabbix.
Configure the following Macros at the Host level:

{$INTERSIGHT.API.BASE_URL}: e.g., https://eu-central-1.intersight.com

{$INTERSIGHT.OAUTH.CLIENT_ID}: Your API Key ID.

{$INTERSIGHT.OAUTH.CLIENT_SECRET}: Your API Secret Key.

{$INTERSIGHT.PROXY}: (Optional) Your corporate proxy address.

2. Deploy the Python Collector

Place gpu_collector.py on your Zabbix server or a management host.
Install requirements: pip install requests.
Schedule the script via Cron to match your Intersight license interval (e.g., every 10 minutes for Essentials):

*/10 * * * * /usr/bin/python3 /path/to/gpu_collector.py


📊 Metrics Collected

Utilization: Core and Memory usage (%).

Power: Real-time and average power draw (Watts).

Thermal: GPU Core temperature (°C).

Clocks: Graphics and Memory clock speeds (MHz).

PCIe Status: Current Link Generation and Width.
