#!/usr/bin/env python3

import argparse
from dateutil.parser import isoparse
from lxml import etree
from pathlib import Path
from si_prefix import si_format

from my_tcx_parser import MyTcxParser

def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("file", type=str, help="File to parse")
    args = parser.parse_args()

    inputPath = Path(args.file)
    tcx = MyTcxParser(inputPath)
    outputPath = inputPath.with_stem(inputPath.stem + "_annotated")
    print(f"{outputPath=}")

    nrLaps = tcx.get_nr_laps()
    print(f"Activity has {nrLaps} laps")

    cumulative_energy = 0
    total_minutes = 0
    target_power = 0

    for i in range(nrLaps):
        lap_start = isoparse(tcx.activity.Lap[i].attrib["StartTime"])
        minutes = tcx.activity.Lap[i].TotalTimeSeconds / 60.0
        print(f"Lap {i} has duration {minutes:.2f} minutes")
        target_power_str = input("Target power for this lap: ")
        if target_power_str == "":
            # Use last target power
            print(f"Using previous power {target_power}")
        else:
            target_power = float(target_power_str)

        extensions = etree.SubElement(tcx.activity.Lap[i], "Extensions")
        target_power_element = etree.SubElement(extensions, "TargetPower")
        target_power_element._setText(str(target_power))

        if target_power == 0:
            print(f"Settling in lap...")
        else:
            avg_power = float(input("Cumulative average power for this lap: "))

            new_cumulative_energy = avg_power * (total_minutes + minutes) * 60
            lap_power = (new_cumulative_energy - cumulative_energy) / (minutes * 60)

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

    with open(outputPath, "wb") as f:
        f.write(etree.tostring(tcx.root, pretty_print=True))

if __name__ == '__main__':
    main()