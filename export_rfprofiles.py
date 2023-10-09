"""
Copyright (c) 2023 Cisco and/or its affiliates.
This software is licensed to you under the terms of the Cisco Sample
Code License, Version 1.1 (the "License"). You may obtain a copy of the
License at
               https://developer.cisco.com/docs/licenses
All use of the material herein must be in accordance with the terms of
the License. All rights not expressly granted by the License are
reserved. Unless required by applicable law or agreed to separately in
writing, software distributed under the License is distributed on an "AS
IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
or implied.
"""

from rich import print
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
import meraki
from meraki.exceptions import APIError
from dotenv import load_dotenv
import os
import sys
import yaml

# Load environment variables
load_dotenv()

API_KEY = os.getenv("MERAKI_DASHBOARD_API_KEY")

console = Console()


def getOrgs(dashboard: meraki.DashboardAPI) -> str:
    """
    Get Meraki organizations and prompt user to select one
    """
    with console.status("Connecting to Meraki...."):
        try:
            orgs = dashboard.organizations.getOrganizations()
        except APIError as e:
            print("\r\n[red]Failed to connect to Meraki. Error:")
            print(f"[red]{e.message['errors'][0]}")
            sys.exit(1)
    print("[green]Connected to Meraki dashboard!")
    print(f"Found {len(orgs)} organization(s).\r\n")

    # If one org, return early
    if len(orgs) == 1:
        print(f"Working with Org: {orgs[0]['name']}")
        return orgs[0]["id"]

    # Else, ask which org to use
    print("Available organizations:")
    org_names = [org["name"] for org in orgs]
    for org in orgs:
        print(f"- {org['name']}")

    print()
    selection = Prompt.ask(
        "Which organization should we use?", choices=org_names, show_choices=False
    )
    for org in orgs:
        if org["name"] == selection:
            return org["id"]


def getTargetNetwork(dashboard: meraki.DashboardAPI, org_id: str) -> str:
    """
    Search for network name/ID to export
    """
    print("Collecting networks...")
    networks = dashboard.organizations.getOrganizationNetworks(org_id)
    print(f"Found {len(networks)} networks.")
    while True:
        net_name = Prompt.ask("Enter name of network to export settings from")
        all_names = {n["name"].lower(): n["id"] for n in networks}
        if not net_name.lower() in all_names.keys():
            print("[red]Can't find a matching network name. Please try again.")
        else:
            return all_names[net_name.lower()]


def getRFProfiles(dashboard: meraki.DashboardAPI, network: str):
    """
    Export RF profiles from target network
    """
    print("Collecting RF Profiles...")
    rf_profiles = dashboard.wireless.getNetworkWirelessRfProfiles(network)
    print("[green]Done!")
    return rf_profiles


def writeData(path: str, rf_profiles: dict) -> None:
    """
    Export RF profiles to local files
    """
    print("Writing data...")
    for profile in rf_profiles:
        del profile["networkId"]
        del profile["id"]
        filename = "_".join(profile["name"].lower().split(" "))
        yaml_content = yaml.dump(profile, sort_keys=False)
        filepath = f"{path}/{filename}.yaml"
        try:
            with open(filepath, "w") as f:
                f.write(yaml_content)
        except FileNotFoundError:
            print("[red]Failed - Directory does not exist.")
            sys.exit(1)
    print("[green]Done!")


def main():
    print()
    print(Panel.fit("  -- Start --  "))
    print()

    print()
    print(Panel.fit("Connect to Meraki", title="Step 1"))
    if API_KEY:
        print("Found API key as environment variable")
        dashboard = meraki.DashboardAPI(
            suppress_logging=True, caller="RFProfileExporter CiscoGVEDevNet"
        )
    else:
        key = Prompt.ask("Enter Meraki Dashboard API Key")
        dashboard = meraki.DashboardAPI(
            key, suppress_logging=True, caller="RFProfileExporter CiscoGVEDevNet"
        )
    org_id = getOrgs(dashboard)

    print()
    print(Panel.fit("Select Network", title="Step 2"))
    network = getTargetNetwork(dashboard, org_id)
    rf_profiles = getRFProfiles(dashboard, network)

    print()
    print(Panel.fit("Export RF Profiles", title="Step 3"))
    path = Prompt.ask("Enter directory to export profiles to")
    writeData(path, rf_profiles)

    print()
    print(Panel.fit("  -- Finished --  "))
    print("Please copy and/or edit the required RF profiles")
    print("Then run the [bold]update_rfprofiles.py[/bold] script to make changes.")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\r\n[red]Quitting...")
