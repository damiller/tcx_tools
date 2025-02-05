
import lxml
from typing import Iterable

import tcxparser

class MyTcxParser(tcxparser.TCXParser):
    def __init__(self, tcx_file: str):
        super().__init__(tcx_file)

    def get_points_with_heart_rate(self) -> Iterable[lxml.etree.ElementBase]:
        trackpoints = [_ for _ in self.root.Activities.iterdescendants(tag="{*}Trackpoint") if hasattr(_, "HeartRateBpm")]

        return trackpoints