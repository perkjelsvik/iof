import plotly.graph_objs as go
import pandas as pd
import numpy as np

from dataclasses import dataclass, field
from typing import List


@dataclass
class Point:
    x: float
    y: float


@dataclass
class Cage:
    center: Point
    r: float
    b: float
    cx: float
    cy: float
    tbr_serial_id: List[int]
    tbrDepth: float
    linesDepths: List[int]
    circlesDepths: List[int]
    name: str
    linesSamples: int = 300
    tbr: pd.DataFrame = None
    lines: List[pd.DataFrame] = field(default_factory=list)
    circles: List[List[pd.DataFrame]] = field(default_factory=list)
    circlesSamples: int = 500
    traces: List[go.Scatter3d] = field(default_factory=list)

    def __post_init__(self):
        self._tbrs()
        self._lines()
        self._circles()
        self._traces()

    def _tbrs(self):
        A, B, C = self.tbr_serial_id
        z = -self.tbrDepth
        self.tbr = pd.DataFrame(
            {
                "TBR": [A, B, C, A],
                "x": [0, self.b, self.cx, 0],
                "y": [0, 0, self.cy, 0],
                "z": [z, z, z, z],
            }
        )

    def _lines(self):
        theta = np.linspace(0, 2 * np.pi, self.linesSamples)
        x = self.r * np.cos(theta) + self.center.x
        y = self.r * np.sin(theta) + self.center.y
        z0, z1, z2 = self.linesDepths
        lines = []
        for i in range(0, self.linesSamples - 1):
            lines.append(
                pd.DataFrame(
                    {
                        "x": [x[i], x[i], self.center.x],
                        "y": [y[i], y[i], self.center.y],
                        "z": [-z0, -z1, -z2],
                    }
                )
            )
        self.lines = lines

    def _circles(self):
        theta = np.linspace(0, 2 * np.pi, self.circlesSamples)
        x = self.r * np.cos(theta) + self.center.x
        y = self.r * np.sin(theta) + self.center.y
        for depth in self.circlesDepths:
            self.circles.append(pd.DataFrame({"x": x, "y": y, "z": -depth}))

    def _traces(self):
        # TBR triangle
        self.traces.append(
            go.Scatter3d(
                x=self.tbr["x"],
                y=self.tbr["y"],
                z=self.tbr["z"],
                mode="lines",
                line=dict(dash="dot", color="red", width=10),
                hoverinfo="skip",
                name=f"{self.name} TBR triangle",
            )
        )
        # TBR locations
        tbrs = [
            go.Scatter3d(
                x=self.tbr[self.tbr["TBR"] == id]["x"],
                y=self.tbr[self.tbr["TBR"] == id]["y"],
                z=self.tbr[self.tbr["TBR"] == id]["z"],
                mode="markers",
                marker=dict(size=10, opacity=1, color="red"),
                name=f"TBR {id}",
                legendgroup=f"{self.name} TBRs",
            )
            for id in self.tbr_serial_id
        ]
        # Depth circles markings
        circles = [
            go.Scatter3d(
                x=circle["x"],
                y=circle["y"],
                z=circle["z"],
                mode="lines",
                line=dict(color="rgba(0,0,0,0.1)", width=10),
                hoverinfo="skip",
                legendgroup=f"{self.name} Cage",
                name=f"z={-d}",
            )
            for circle, d in zip(self.circles, self.circlesDepths)
        ]
        # Cage frame
        lines = [
            go.Scatter3d(
                x=line["x"],
                y=line["y"],
                z=line["z"],
                mode="lines",
                line=dict(color="rgba(0, 0, 0, 0.1)", width=5),
                showlegend=False,
                hoverinfo="skip",
                legendgroup=f"{self.name} Cage",
            )
            for line in self.lines
        ]
        self.traces += tbrs + circles + lines


# AQUATRAZ
# Meta data not needed, but stored for reference:
# | AB = 42.39 | AC = 39.92 | BC = 44.75 | r_tbr = 24.533016018
aq_center = Point(21.14, 12.45)
aq_r = 26.579
aq_b, aq_cx, aq_cy = 42.391825746953415, 16.366497453560264, 36.406204121068214
aq_tbr = [730, 735, 837]
aq_tbr_depth = 3
aq_lines_depth = [0, 18, 32]
aq_circles_depths = [0, 8, 18]
aq_name = "Aquatraz"
aq_cage = Cage(
    center=aq_center,
    r=aq_r,
    b=aq_b,
    cx=aq_cx,
    cy=aq_cy,
    tbr_serial_id=aq_tbr,
    tbrDepth=aq_tbr_depth,
    linesDepths=aq_lines_depth,
    circlesDepths=aq_circles_depths,
    name=aq_name,
)

# AQUATRAZ AFTER 10th of MAY
# Meta data not needed, but stored for reference:
# | AB = 42.39 | AC = 39.92 | BC = 44.75 | r_tbr = 24.533016018
aq_center_new = Point(19.81, 18.79)
aq_b_new, aq_cx_new, aq_cy_new = 39.62379671662672, 17.721822084838525, 46.0125363983182
aq_tbr_depth_new = 10
aq_cage_new = Cage(
    center=aq_center_new,
    r=aq_r,
    b=aq_b_new,
    cx=aq_cx_new,
    cy=aq_cy_new,
    tbr_serial_id=aq_tbr,
    tbrDepth=aq_tbr_depth_new,
    linesDepths=aq_lines_depth,
    circlesDepths=aq_circles_depths,
    name=aq_name,
)

# REFERENCE
# Meta data not needed, but stored for reference:
# | AB = 42.39 | AC = 39.92 | BC = 44.75 | r_tbr = 24.533016018
ref_center = Point(21.19, 13.27)
ref_r = 25
ref_b, ref_cx, ref_cy = 42.37492120522585, 23.680482062650185, 37.8681107558171
ref_tbr = [836, 734, 730]
ref_tbr_depth = 3
ref_lines_depth = [0, 12.5, 25]
ref_circles_depths = [0, 12.5]
ref_name = "Reference"
ref_cage = Cage(
    center=ref_center,
    r=ref_r,
    b=ref_b,
    cx=ref_cx,
    cy=ref_cy,
    tbr_serial_id=ref_tbr,
    tbrDepth=ref_tbr_depth,
    linesDepths=ref_lines_depth,
    circlesDepths=ref_circles_depths,
    name=ref_name,
)
