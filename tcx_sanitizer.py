#!/usr/bin/env python3

import argparse
from dateutil.parser import isoparse
from pathlib import Path

from my_tcx_parser import MyTcxParser

def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("file", type=str, help="File to parse")
    args = parser.parse_args()
    input_path = Path(args.file)
    tcx = MyTcxParser(input_path)
    nr_laps = tcx.get_nr_laps()

    for i in range(nr_laps):
        lap_start = isoparse(tcx.activity.Lap[i].attrib["StartTime"])
        point_iterator = tcx.get_trackpoint_iter(i)
        last_timepoint = 0
        for trackpoint in point_iterator:
            timepoint = (isoparse(str(trackpoint.Time)) - lap_start).total_seconds()
            if timepoint < last_timepoint:
                print(f"    Out of order timepoint at {trackpoint.Time}")
            elif timepoint > last_timepoint + 10:
                print(f"    Large jump in timepoint at {trackpoint.Time}")
            last_timepoint = timepoint

if __name__ == '__main__':
    main()