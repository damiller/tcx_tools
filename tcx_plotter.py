#!/usr/bin/env python3

import argparse
from dateutil.parser import isoparse
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

from my_tcx_parser import MyTcxParser

def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("file", type=str, help="File to parse")
    args = parser.parse_args()

    tcx = MyTcxParser(args.file)

    # Find first lap with any target power
    reference_time = None
    for lap in tcx.activity.Lap:
        if not hasattr(lap, "Extensions"):
            continue
        if not hasattr(lap.Extensions, "TargetPower"):
            continue
        if float(lap.Extensions.TargetPower.text) == 0.0:
            continue
        reference_time = isoparse(lap.attrib["StartTime"])
        print(f"Found lap with target power {float(lap.Extensions.TargetPower.text):.1f} at time {reference_time}")
        break
    
    heart_points = tcx.get_points_with_heart_rate()
    heart_rates = [float(_.HeartRateBpm.Value.text) for _ in heart_points]
    heart_times = [isoparse(_.Time.text) for _ in heart_points]
    if reference_time is None:
        reference_time = heart_times[0]
    normalized_heart_times = [(_-reference_time).total_seconds() / 60.0 for _ in heart_times]

    power_points = tcx.get_points_with_power()
    powers = [float(_.Extensions.Power.text) for _ in power_points]
    target_powers = [float(_.Extensions.TargetPower.text) for _ in power_points]
    average_powers = [float(_.Extensions.AveragePower.text) for _ in power_points]
    def heart_rate_value_or_last(x) -> float:
        if not hasattr(heart_rate_value_or_last, "local"):
            setattr(heart_rate_value_or_last, "local", 0.0)
        if hasattr(x, "HeartRateBpm"):
            heart_rate_value_or_last.local = float(x.HeartRateBpm.Value.text)
        return heart_rate_value_or_last.local
    power_hearts = [heart_rate_value_or_last(_) for _ in power_points]
    power_colors = [(_-140.0) / 40.0 for _ in power_hearts]
    power_colors = [max(0, min(1, _)) for _ in power_colors] # Clamps
    power_times = [isoparse(_.Time.text) for _ in power_points]
    normalized_power_times = [(_-reference_time).total_seconds() / 60.0 for _ in power_times]
    
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True)
    fig.update_layout({
        "hovermode": "x unified",
        "hoversubplots": "overlaying"}
    )
    hearts_scatter = go.Scatter(xaxis="x", x=normalized_heart_times, y=heart_rates, name="Heart Rate")
    fig.add_trace(hearts_scatter, row=1, col=1)
    next(fig.select_xaxes(row=1, col=1)).update(title="Time Elapsed (min.)")
    next(fig.select_yaxes(row=1, col=1)).update(title="Heart Rate (bpm)")

    powers_scatter = go.Scatter(x=normalized_power_times, y=powers, name="Power")
    fig.add_trace(powers_scatter, row=2, col=1)

    target_powers_scatter = go.Scatter(x=normalized_power_times, y=target_powers, name="Target Power")
    fig.add_trace(target_powers_scatter, row=2, col=1)

    average_powers_scatter = go.Scatter(
        x=normalized_power_times,
        xaxis="x",
        y=average_powers,
        name="Running Avg. Power",
        marker={"color": power_colors, "colorscale": "plasma", "size": 4, "symbol": "circle"},
        mode="lines+markers"
    )
    fig.add_trace(average_powers_scatter, row=2, col=1)
    next(fig.select_xaxes(row=2, col=1)).update(title="Time Elapsed (min.)")
    next(fig.select_yaxes(row=2, col=1)).update(title="Power (W)")

    fig.show()


if __name__ == '__main__':
    main()
