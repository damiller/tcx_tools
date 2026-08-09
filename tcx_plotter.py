#!/usr/bin/env python3

import argparse
from dateutil.parser import isoparse

import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

from my_tcx_parser import MyTcxParser

LAP_TYPE_COLORS = {
    "NOT_STARTED": {"name": "Slate Gray", "color": "rgba(148, 163, 184, 0.08)"},
    "SETTLE_IN": {"name": "Light Gray", "color": "rgba(200, 200, 200, 0.12)"},
    "WARMUP": {"name": "Blue", "color": "rgba(59, 130, 246, 0.10)"},
    "WORKOUT": {"name": "Red", "color": "rgba(239, 68, 68, 0.12)"},
    "COOLDOWN": {"name": "Green", "color": "rgba(34, 197, 94, 0.10)"},
    "INTERVAL": {"name": "Purple", "color": "rgba(168, 85, 247, 0.12)"},
    "REST": {"name": "Gold", "color": "rgba(250, 204, 21, 0.12)"},
}


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--smooth-factor", type=int, default=20, help="How much to smooth the heart rate")
    parser.add_argument("file", type=str, help="File to parse")
    args = parser.parse_args()

    tcx = MyTcxParser(args.file)
    smooth_kernel = np.array([1.0 / args.smooth_factor] * args.smooth_factor)
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
    heart_rates = np.array([float(_.HeartRateBpm.Value.text) for _ in heart_points])
    smooth_heart_rates = np.convolve(heart_rates, smooth_kernel, "valid")
    heart_times = np.array([isoparse(_.Time.text) for _ in heart_points])

    if reference_time is None:
        reference_time = heart_times[0]
    normalized_heart_times = [(_-reference_time).total_seconds() / 60.0 for _ in heart_times]
    smooth_normalized_heart_times = normalized_heart_times[args.smooth_factor:]

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
    smooth_hearts_scatter = go.Scatter(xaxis="x", x=smooth_normalized_heart_times, y=smooth_heart_rates, name="Smoothed Heart Rate")
    fig.add_trace(hearts_scatter, row=1, col=1)
    fig.add_trace(smooth_hearts_scatter, row=1, col=1)
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

    for idx, lap in enumerate(tcx.activity.Lap):
        if not hasattr(lap, "Extensions") or not hasattr(lap.Extensions, "LapType"):
            continue

        lap_type_name = str(lap.Extensions.LapType.text).upper()
        lap_style = LAP_TYPE_COLORS.get(lap_type_name)
        if lap_style is None:
            continue

        fill_color = lap_style["color"]

        lap_start = isoparse(lap.attrib["StartTime"])
        start_minutes = (lap_start - reference_time).total_seconds() / 60.0

        if idx + 1 < len(tcx.activity.Lap):
            next_lap_start = isoparse(tcx.activity.Lap[idx + 1].attrib["StartTime"])
            end_minutes = (next_lap_start - reference_time).total_seconds() / 60.0
        else:
            end_minutes = start_minutes + float(lap.TotalTimeSeconds) / 60.0

        if end_minutes <= start_minutes:
            continue

        fig.add_vrect(
            x0=start_minutes,
            x1=end_minutes,
            row="all",
            col="all",
            fillcolor=fill_color,
            line_width=0,
            layer="below",
        )

    seen_lap_types = set()
    for idx, lap in enumerate(tcx.activity.Lap):
        if not hasattr(lap, "Extensions") or not hasattr(lap.Extensions, "LapType"):
            continue
        lap_type_name = str(lap.Extensions.LapType.text).upper()
        seen_lap_types.add(lap_type_name)

    for lap_type_name in sorted(seen_lap_types):
        lap_style = LAP_TYPE_COLORS.get(lap_type_name)
        if lap_style is None:
            continue

        fig.add_trace(
            go.Scatter(
                x=[None],
                y=[None],
                mode="markers",
                marker={"color": lap_style["color"], "size": 12},
                name=f"{lap_type_name.replace('_', ' ').title()} ({lap_style['name']})",
                showlegend=True,
                legendgroup="lap-types",
                hoverinfo="skip",
            )
        )

    fig.show()


if __name__ == '__main__':
    main()
