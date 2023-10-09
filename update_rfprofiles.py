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

import glob
import os
import sys
from csv import DictReader

import meraki
import yaml
from dotenv import load_dotenv
from meraki.exceptions import APIError
from rich import print
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, track
from rich.prompt import Confirm, Prompt
from rich.table import Table
from yaml import SafeLoader

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


def getNetworks(dashboard: meraki.DashboardAPI, org_id: str) -> dict:
    """
    Collect existing Meraki network names / IDs
    """
    print("Collecting networks...")
    networks = dashboard.organizations.getOrganizationNetworks(org_id)
    print(f"Found {len(networks)} networks.")
    return networks


def getRFProfiles(dashboard: meraki.DashboardAPI, networks: dict) -> dict:
    """
    Export RF profiles from target network
    """
    print("Collecting existing RF Profiles...")
    results = {}
    for network in track(networks):
        if not "wireless" in network["productTypes"]:
            continue
        profiles = dashboard.wireless.getNetworkWirelessRfProfiles(network["id"])
        rf_info = {n["name"]: {"id": n["id"]} for n in profiles}
        results[network["name"].lower()] = {"id": network["id"], "rf": rf_info}
    return results


def collectNewRFprofiles() -> dict:
    """
    Prompt for directory of new template files & read contents
    """
    file_list = []
    while True:
        dir = Prompt.ask("Enter directory containing new RF profiles")
        for path in glob.glob(f"{dir}/*", recursive=True):
            if ".yaml" in path:
                file_list.append(path)
        if len(file_list) == 0:
            print("[yellow]Found no files in that directory..")
        else:
            print(f"[green]Found {len(file_list)} template files.")
            print("Reading files...")
            rfprofiles = {}
            for file in file_list:
                with open(file, "r") as f:
                    contents = yaml.load(f, Loader=SafeLoader)
                    rfprofiles[contents["name"]] = contents
            print("[green]RF Profiles loaded!")
            return rfprofiles


def getRFAssignments(profiles: dict) -> dict:
    """
    Prompt for RF profile assignment CSV & read/validate file
    """
    target_networks = {}
    while True:
        file = Prompt.ask("Enter name of CSV containing profile assignments")
        try:
            with open(file, "r") as f:
                print("Reading CSV...")
                csv = DictReader(f, skipinitialspace=True)
                csv_data = [row for row in csv]
                print("[green]Done!")
                return csv_data
        except FileNotFoundError:
            print(f"[red]Cannot locate file: {file}")
            print()


def validateAssignments(
    current: dict,
    new: dict,
    assignments: dict,
) -> dict:
    """
    Validate desired RF profile uploads / assignments
    """
    print("Validating RF Profile assignments...")
    good = 0
    bad_network = []
    bad_profiles = []
    bad_aps = []
    updates = {}
    for entry in assignments:
        rf_profiles = [p.strip() for p in entry["RF Profiles"].split(",")]
        aps = [p.strip() for p in entry["APs"].split(",")]
        target_network = entry["Network Name"].lower()
        # Check networks match known networks
        if not target_network in current.keys():
            bad_network.append(entry)
            continue
        # Check that profile names match new profiles
        bad_profile = False
        for profile in rf_profiles:
            if not profile in new.keys():
                bad_profiles.append(entry)
                bad_profile = True
        if bad_profile:
            continue
        # Check that if APs are being assigned, only one profile has been provided
        if len(rf_profiles) > 1:
            if aps != "" and aps[0].lower() != "none":
                bad_aps.append(entry)
                continue

        # Set up storage of only networks / profiles that need changes
        updates[target_network] = {}
        updates[target_network]["id"] = current[target_network]["id"]
        updates[target_network]["rf"] = {}

        # Check which profiles are new / updates
        for profile in rf_profiles:
            updates[target_network]["rf"][profile] = {}
            updates[target_network]["rf"][profile]["aps"] = aps
            if profile in current[target_network]["rf"].keys():
                updates[target_network]["rf"][profile]["id"] = current[target_network][
                    "rf"
                ][profile]["id"]
                updates[target_network]["rf"][profile]["oper"] = "update"
            else:
                updates[target_network]["rf"][profile]["oper"] = "add"
        good += 1

    if good == len(assignments):
        print("[green]Profile assignments processed. No issues found!")
    else:
        print(f"\r\nIssues were found. Only {good} passed of {len(assignments)}")
        if Confirm.ask("Show errors?"):
            table = Table(
                "Error",
                "Network Name",
                "RF Profiles",
                "APs",
                expand=True,
                show_lines=True,
            )
            for entry in bad_network:
                table.add_row("Network Name Mismatch", *entry.values())
            for entry in bad_profiles:
                table.add_row("RF Profile Name Mismatch", *entry.values())
            for entry in bad_aps:
                table.add_row("Cannot assign multiple profiles to APs", *entry.values())
            print()
            print(table)
            print()
        if good == 0:
            sys.exit(1)
    return updates


def upload_profiles(
    changes: dict, profiles: dict, dashboard: meraki.DashboardAPI
) -> None:
    """
    Update / Create RF profiles
    """
    print("Beginning RF Profile upload...")
    errors = []
    with Progress() as progress:
        total_prog = progress.add_task("Processing...", total=len(changes.keys()))
        # Process each network
        for network in changes:
            progress.console.print(f"Working on network: {network}")
            rf = changes[network]["rf"]
            netid = changes[network]["id"]
            # Handle profile updates first
            progress.console.print("Uploading RF profiles...")
            for profile in rf:
                profiledata = profiles[profile]
                aps = rf[profile]["aps"]
                try:
                    if rf[profile]["oper"] == "add":
                        response = dashboard.wireless.createNetworkWirelessRfProfile(
                            networkId=netid, **profiledata
                        )
                        # Store new profile ID
                        rf[profile]["id"] = response["id"]
                    elif rf[profile]["oper"] == "update":
                        dashboard.wireless.updateNetworkWirelessRfProfile(
                            networkId=netid,
                            rfProfileId=rf[profile]["id"],
                            **profiledata,
                        )
                except APIError as e:
                    errors.append(
                        {
                            "network": network,
                            "profile": profile,
                            "error": e.message["errors"][0],
                        }
                    )
                    continue
                # Save RF profile ID
                rfid = rf[profile]["id"]
                progress.console.print("Finished uploading profiles!")
                if aps == "" or aps[0].lower() == "none":
                    progress.console.print("No APs to assign.")
                else:
                    progress.console.print("Assigning profiles to APs...")
                    # If ALL APs assigned, need to look up serial numbers
                    try:
                        if aps[0].lower() == "all":
                            progress.console.print("Collecting AP serial numbers...")
                            response = dashboard.networks.getNetworkDevices(
                                networkId=netid
                            )
                            aps = [d["serial"] for d in response if "MR" in d["model"]]
                            if len(aps) == 0:
                                progress.console.print(
                                    "No APs found on this network. Skipping..."
                                )
                            else:
                                progress.console.print(
                                    f"{len(aps)} AP serials collected"
                                )
                        # Update RF profiles on all assigned APs
                        for ap in aps:
                            dashboard.wireless.updateDeviceWirelessRadioSettings(
                                serial=ap, rfProfileId=rfid
                            )
                    except APIError as e:
                        errors.append(
                            {
                                "network": network,
                                "profile": profile,
                                "error": e.message["errors"][0],
                            }
                        )
                        continue
                    progress.console.print("APs assigned!")
            progress.console.print(f"[green]Network {network} completed!")
            progress.update(total_prog, advance=1)

    if len(errors) == 0:
        print("[green]Completed updates!")
    else:
        print(f"\r\n[yellow]Encountered {len(errors)} errors during updates.")
        if Confirm.ask("Show errors?"):
            table = Table(
                "Network",
                "RF Profile",
                "Error Message",
                expand=True,
                show_lines=True,
            )
            for entry in errors:
                table.add_row(*entry.values())
            print()
            print(table)
            print()


def main():
    print()
    print(Panel.fit("  -- Start --  "))
    print()

    print()
    print(Panel.fit("Connect to Meraki", title="Step 1"))
    if API_KEY:
        print("Found API key as environment variable")
        dashboard = meraki.DashboardAPI(
            suppress_logging=True, caller="RFProfileUpdater CiscoGVEDevNet"
        )
    else:
        key = Prompt.ask("Enter Meraki Dashboard API Key")
        dashboard = meraki.DashboardAPI(
            key, suppress_logging=True, caller="RFProfileUpdater CiscoGVEDevNet"
        )
    org_id = getOrgs(dashboard)

    print()
    print(Panel.fit("Collect Deployment Info", title="Step 2"))
    networks = getNetworks(dashboard, org_id)
    rf_profiles = getRFProfiles(dashboard, networks)
    count = len([prof for net in rf_profiles for prof in rf_profiles[net]["rf"]])
    print(f"Saved information about {count} RF profiles.")

    print()
    print(Panel.fit("Collect new profiles & assignments", title="Step 3"))
    new_profiles = collectNewRFprofiles()
    assignments = getRFAssignments(new_profiles)
    proposed_changes = validateAssignments(rf_profiles, new_profiles, assignments)

    print()
    if not Confirm.ask("Ready to deploy changes. Continue?"):
        sys.exit(1)

    print()
    print(Panel.fit("Upload RF Profiles", title="Step 4"))
    upload_profiles(proposed_changes, new_profiles, dashboard)

    print()
    print(Panel.fit("  -- Finished --  "))
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\r\n[red]Quitting...")
