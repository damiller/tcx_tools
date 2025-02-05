#!/usr/bin/env python3

import argparse
from dateutil.parser import isoparse
import plotly.express as px

from my_tcx_parser import MyTcxParser

def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("file", type=str, help="File to parse")
    args = parser.parse_args()

    tcx = MyTcxParser(args.file)

    heart_points = tcx.get_points_with_heart_rate()
    heart_rates = [int(_.HeartRateBpm.Value.text) for _ in heart_points]
    heart_times = [isoparse(_.Time.text) for _ in heart_points]
    normalized_heart_times = [(_-heart_times[0]).total_seconds() for _ in heart_times]

    fig = px.scatter(x=normalized_heart_times, y=heart_rates)
    fig.show()


if __name__ == '__main__':
    main()
