from enum import auto, StrEnum
from pathlib import Path

import lxml
import lxml.etree

from collections.abc import Iterator
from typing import Optional, Iterable, Union

import tcxparser

class EffortType(StrEnum):
    PACE = auto()
    TARGET_HEART_RATE = auto()
    LIMITHR = TARGET_HEART_RATE
    LACTATE_THRESHOLD = auto()
    FTP_TEST = auto()
    INTERVALS = auto()
    UNKNOWN = auto()

class LapType(StrEnum):
    NOT_STARTED = auto()  # Placeholder to hold a last lap before activity has started
    SETTLE_IN = auto()
    WARMUP = auto()
    WORKOUT = auto()
    COOLDOWN = auto()
    INTERVAL = auto()
    REST = auto()

class MyTcxParser(tcxparser.TCXParser):
    _TRACKPOINT_TAG = "{*}Trackpoint"

    def __init__(self, tcx_file: Union[str, Path]):
        super().__init__(tcx_file)

    def get_points_with_heart_rate(self) -> Iterable[lxml.etree.ElementBase]:
        trackpoints = [_ for _ in self.root.Activities.iterdescendants(tag=self._TRACKPOINT_TAG) if hasattr(_, "HeartRateBpm")]

        return trackpoints

    def get_points_with_power(self) -> Iterable[lxml.etree.ElementBase]:
        trackpoints = [_ for _ in self.activity.iterdescendants(tag=self._TRACKPOINT_TAG) if hasattr(_, "Extensions") and hasattr(_.Extensions, "Power")]
        return trackpoints

    def get_nr_laps(self) -> int:
        return len(self.activity.Lap)

    def get_trackpoint_iter(self, lap: Optional[int] = None) -> Iterator[lxml.etree.ElementBase]:
        if lap is None:
            # all the points
            return self.activity.iterdescendants(tag=self._TRACKPOINT_TAG)
        else:
            return self.activity.Lap[lap].iterdescendants(tag=self._TRACKPOINT_TAG)

    def get_nr_points(self, lap: Optional[int] = None) -> int:
        return len(list(self.get_trackpoint_iter(lap)))
