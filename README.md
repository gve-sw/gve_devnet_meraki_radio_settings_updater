# Cisco Meraki - Radio Settings Updater

This repository contains sample code for bulk updating radio settings across multiple networks.

`export_rfprofiles.py` will collect & export RF profiles for an existing Meraki network, which can then be copied or modified to use with the update script.

`update_rfprofiles.py` is capable of uploading one or many Meraki RF profiles & applying them to APs if desired. The script will determine whether the profiles are new, or existing ones that need to be updated.

## Contacts

- Matt Schmitz (<mattsc@cisco.com>)

## Solution Components

- Cisco Meraki

## Installation/Configuration

### **Step 1 - Clone repo:**

```bash
git clone <repo_url>
```

### **Step 2 - Install required dependancies:**

```bash
pip install -r requirements.txt
```

### **Step 3 - Provide Cisco Meraki API Key (Optional)**

You may choose to provide the Cisco Meraki API key via the `MERAKI_DASHBOARD_API_KEY` environment variable.

If the environment variable is not provided, then the script will prompt for the API key.

### **Step 4 - Prepare CSV file**

> This step only applies for the `update_rfprofiles.py` script. If only using the `export_rfprofiles.py` code, please proceed to the [Usage](#rf-profile-export) steps.

An example of the CSV format is below:

```csv
Network Name,RF Profiles,APs
Network 01,"Profile01, Profile02","AAAA-AAAA-AAAA,BBBB-BBBB-BBBB"
Network 02,Profile01,ALL
Network 03,"Profile01, Profile02",None
Network 04,Profile01,
```

`Network Name` must match the name of the network as shown in Meraki Dashboard.

`RF Profiles` can be a list of one or more RF profiles to upload to this network. The profile name must match the name field within the RF profile config, not the file name.

`APs` will optionally list the Meraki wireless access points to apply the new RF profiles to. Valid options include:

- Leaving the field blank, or specifying `None`. This will update/create profiles only & not apply to any APs
- `ALL` will provision the assigned RF profile to all access points on the specified network
- A list of one or more AP serial numbers may be provided to selectively apply the RF profile to certain APs within a network.

> NOTE: Only 1 RF profile can be assigned to an individual AP. Therefore, the script will reject any CSV entries that include multiple profiles & AP assignments. Please create only 1 CSV entry for each set of profile-to-AP assignments.

## Usage

### RF Profile Export

To export RF profiles from an existing network, use the following command:

```bash
python3 export_rfprofiles.py
```

The script will prompt to ask which network to export profiles from & where to write the exported data to. All RF profiles exported by this script will be converted to YAML.

### RF Profile Upload

To begin creating / assigning RF profiles, this script will need:

- YAML-formatted RF profiles, as provided by the export script
- A CSV containing networks to modify, RF profiles to upload, and optional assignments to APs. An example of this is shown above in [Step 4](#step-4---prepare-csv-file).

Once ready, run the following command:

```bash
python3 update_rfprofiles.py
```

This script will prompt for the location of the CSV file & directory containing RF profiles.

# Related Sandbox

- [Cisco Meraki Enterprise Lab](https://devnetsandbox.cisco.com/RM/Diagram/Index/e7b3932b-0d47-408e-946e-c23a0c031bda?diagramType=Topology)

# Screenshots

### Demo of profile export script

![/IMAGES/demo-export.gif](/IMAGES/demo-export.gif)

### Demo of profile update script

![/IMAGES/demo-update.gif](/IMAGES/demo-update.gif)

### LICENSE

Provided under Cisco Sample Code License, for details see [LICENSE](LICENSE.md)

### CODE_OF_CONDUCT

Our code of conduct is available [here](CODE_OF_CONDUCT.md)

### CONTRIBUTING

See our contributing guidelines [here](CONTRIBUTING.md)

#### DISCLAIMER

<b>Please note:</b> This script is meant for demo purposes only. All tools/ scripts in this repo are released for use "AS IS" without any warranties of any kind, including, but not limited to their installation, use, or performance. Any use of these scripts and tools is at your own risk. There is no guarantee that they have been through thorough testing in a comparable environment and we are not responsible for any damage or data loss incurred with their use.
You are responsible for reviewing and testing any scripts you run thoroughly before use in any non-testing environment.
