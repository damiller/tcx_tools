#!/usr/bin/env python3

import argparse
from dateutil.parser import isoparse
from lxml import etree
from pathlib import Path
import re
from si_prefix import si_format
import sys

from my_tcx_parser import EffortType, LapType, MyTcxParser

WORKOUT_NAME_RE = re.compile(
    r"^(?P<effort>[A-Za-z]+)-(?P<date>\d{8})-(?P<route>[A-Za-z0-9_-]+)-(?P<power>\d+(?:\.\d+)?)W$"
)

def convert_from_camel_to_spaced(name: str) -> str:
    """ Transforms a camel case string into a spaced string. For example, "CamelCase" becomes "Camel Case".
    """
    return re.sub(r'((?<=[a-z])[A-Z]|(?<!\A)[A-Z](?=[a-z]))', r' \1', name)

def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--overwrite", action=argparse.BooleanOptionalAction, help="Overwrite existing file")
    parser.add_argument("--type", type=EffortType, default=EffortType.UNKNOWN, help="Type of effort (pace, LTT, FTP, intervals)")
    parser.add_argument("--route", type=str, default="", help="Route name to add to the activity")
    parser.add_argument("file", type=str, help="File to parse")
    args = parser.parse_args()

    inputPath = Path(args.file)
    tcx = MyTcxParser(inputPath)
    outputPath = inputPath.with_stem(inputPath.stem + "_annotated")
    if Path.exists(outputPath):
        if args.overwrite:
            print(f"Overwriting existing file {outputPath}")
        else:
            print(f"Output file {outputPath} already exists. Specify --overwrite to replace")
            sys.exit(1)

    # Parse the input filename for metadata
    result = WORKOUT_NAME_RE.match(inputPath.stem)
    if isinstance(result, re.Match):
        parsed_effort = EffortType(result.group("effort").lower())
        parsed_date = isoparse(result.group("date"))
        parsed_route = convert_from_camel_to_spaced(result.group("route"))
        if args.route != "" and args.route != parsed_route:
            print(f"Route name in filename ({parsed_route}) does not match specified route name ({args.route})")
        parsed_power = result.group("power")
    else:
        parsed_effort = EffortType.UNKNOWN
        parsed_date = None
        parsed_route = None
        parsed_power = None

    nrLaps = tcx.get_nr_laps()
    print(f"Activity has {nrLaps} laps")

    cumulative_energy = 0
    total_minutes = 0
    target_power = 0
    last_target_power = 0
    lap_type = LapType.NOT_STARTED
    cumulative_energy_by_type = {}
    cumulative_minutes_by_type = {}

    # Add activity metadata under Extensions so it matches the lap-level schema.
    if hasattr(tcx.activity, "Extensions"):
        activity_extensions = tcx.activity.Extensions
    else:
        activity_extensions = etree.SubElement(tcx.activity, "Extensions")

    if args.type == EffortType.UNKNOWN:
        if parsed_effort != EffortType.UNKNOWN:
            args.type = parsed_effort
        else:
            input_type = input("Enter effort type (pace, target_heart_rate, lactate_threshold, ftp_test, intervals): ")
            if input_type:
                args.type = EffortType(input_type)
    effort_type_element = etree.SubElement(activity_extensions, "EffortDetails", attrib={"EffortType": str(args.type)})
    # Details for PACE type effort
    if args.type == EffortType.PACE:
        if parsed_power is None:
            input_power = input("Enter target pace (W): ")
            if input_power:
                parsed_power = input_power
        effort_power_element = etree.SubElement(effort_type_element, "TargetPower")
        effort_power_element._setText(str(parsed_power))

    if args.route != "":
        route_element = etree.SubElement(activity_extensions, "Route")
        route_element._setText(args.route)

    if parsed_date is not None:
        # Sanity check that we have the right data
        activity_date = isoparse(tcx.activity.Id.text).date()
        if parsed_date.date() != activity_date:
            print(f"Warning: date in filename ({parsed_date.date()}) does not match activity start time ({activity_start_time.date()})")

    for i in range(nrLaps):
        manual_lap_type = None
        lap_start = isoparse(tcx.activity.Lap[i].attrib["StartTime"])
        minutes = tcx.activity.Lap[i].TotalTimeSeconds / 60.0
        print(f"Lap {i} has duration {minutes:.2f} minutes")
        target_power_str = input("Target power for this lap: ")

        if target_power_str == "":
            # Use last target power
            print(f"Using previous power {target_power}")
        elif target_power_str[0].isalpha():
            alpha_portion = re.findall(r"\b[a-zA-Z]+", target_power_str)
            print(f"Found alpha {alpha_portion}")
            # Get the lap type by matching the first alphabetical portion against the keys
            to_match = alpha_portion[0].upper()
            matches = [_ for _ in LapType if _.name.startswith(to_match)]
            print(f"Found matches {matches}")
            manual_lap_type = matches[0]
            removed_alpha = target_power_str
            for iPortion in alpha_portion:
                removed_alpha = removed_alpha.replace(iPortion, "")

            target_power = float(removed_alpha)
        else:
            target_power = float(target_power_str)

        extensions = etree.SubElement(tcx.activity.Lap[i], "Extensions")
        target_power_element = etree.SubElement(extensions, "TargetPower")
        target_power_element._setText(str(target_power))
        lap_type_element = etree.SubElement(extensions, "LapType")

        if manual_lap_type is not None:
            lap_type = manual_lap_type
        else:
            if target_power == 0:
                print(f"Settling in lap...")
                lap_type = LapType.SETTLE_IN
            else:
                if lap_type == LapType.NOT_STARTED or lap_type == LapType.SETTLE_IN:
                    print(f"Warming up...")
                    lap_type = lap_type.WARMUP
                elif lap_type == LapType.WARMUP:
                    if target_power > last_target_power:
                        print(f"Beginning effort...")
                        lap_type = lap_type.WORKOUT
                elif lap_type == LapType.WORKOUT:
                    if target_power < last_target_power:
                        print("Cooling down...")
                        lap_type = lap_type.COOLDOWN

        lap_type_element._setText(str(lap_type))
        if lap_type == LapType.SETTLE_IN:
            continue

        avg_power = float(input("Cumulative average power for this lap: "))

        new_cumulative_energy = avg_power * (total_minutes + minutes) * 60
        lap_power = (new_cumulative_energy - cumulative_energy) / (minutes * 60)
        cumulative_energy_by_type[lap_type] = cumulative_energy_by_type.get(lap_type, 0) + lap_power * minutes * 60
        cumulative_minutes_by_type[lap_type] = cumulative_minutes_by_type.get(lap_type, 0) + minutes

        print(f"  Lap power: {lap_power:.1f} W")
        print(f"  Energy exerted: {si_format(new_cumulative_energy, 1)}J")

        lap_power_element = etree.SubElement(extensions, "Power")
        lap_power_element._setText(str(lap_power))
        averaged_power_element = etree.SubElement(extensions, "AveragePower")
        averaged_power_element._setText(str(avg_power))

        last_timepoint = 0
        for trackpoint in tcx.get_trackpoint_iter(i):
            timepoint = (isoparse(str(trackpoint.Time)) - lap_start).total_seconds()
            if timepoint < last_timepoint:
                print(f"    Out of order timepoint at {trackpoint.Time}")
            elif timepoint > last_timepoint + 10:
                print(f"    Large jump in timepoint at {trackpoint.Time}")
            last_timepoint = timepoint
            point_cumulative_energy = cumulative_energy + lap_power * timepoint

            if not hasattr(trackpoint, "Extensions"):
                print(f"    Skipping trackpoint at time {timepoint} with no extensions")
                continue
            extensions = trackpoint.Extensions
            trackpoint_power_element = etree.SubElement(extensions, "Power")
            trackpoint_power_element._setText(str(lap_power))
            target_power_element = etree.SubElement(extensions, "TargetPower")
            target_power_element._setText(str(target_power))
            averaged_power_element = etree.SubElement(extensions, "AveragePower")
            if cumulative_energy == 0:
                avg_point_power = avg_power
            else:
                avg_point_power = point_cumulative_energy / (total_minutes * 60 + timepoint)
            averaged_power_element._setText(str(avg_point_power))

        # Update cumulative energy
        total_minutes += minutes
        cumulative_energy = new_cumulative_energy

        last_target_power = target_power

    # Print workout summary
    if LapType.WORKOUT in cumulative_energy_by_type:
        print(f"Effort duration: {cumulative_minutes_by_type.get(LapType.WORKOUT):.1f} min.")
        effort_power = cumulative_energy_by_type[LapType.WORKOUT] / cumulative_minutes_by_type[LapType.WORKOUT] / 60
        print(f"Effort power   : {effort_power:.1f} W")

        effort_duration_element = etree.SubElement(activity_extensions, "EffortDuration")
        effort_duration_element._setText(str(cumulative_minutes_by_type[LapType.WORKOUT] * 60.0))
        effort_power_element = etree.SubElement(activity_extensions, "ActualPower")
        effort_power_element._setText(str(effort_power))

    with open(outputPath, "wb") as f:
        f.write(etree.tostring(tcx.root, pretty_print=True))


if __name__ == '__main__':
    main()