import plotly.graph_objs as go
import pandas as pd
import numpy as np
import toml

from dataclasses import dataclass, field
from typing import List

metafile = "frontend_metadata.toml"
meta = toml.load(metafile)["3D"]["cages"]


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
    linesSamples: int = 60
    tbr: pd.DataFrame = None
    lines: List[pd.DataFrame] = field(default_factory=list)
    circles: List[List[pd.DataFrame]] = field(default_factory=list)
    circlesSamples: int = 60
    traces: List[go.Scatter3d] = field(default_factory=list)

    def __post_init__(self):
        self._tbrs()
        self._lines()
        self._circles()
        self._traces()

    def _tbrs(self):
        A, B, C = self.tbr_serial_id
        z = self.tbrDepth
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
                        "z": [z0, z1, z2],
                    }
                )
            )
        self.lines = lines

    def _circles(self):
        theta = np.linspace(0, 2 * np.pi, self.circlesSamples)
        x = self.r * np.cos(theta) + self.center.x
        y = self.r * np.sin(theta) + self.center.y
        for depth in self.circlesDepths:
            self.circles.append(pd.DataFrame({"x": x, "y": y, "z": depth}))

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
                name=f"z={d}",
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


_includePositioning = toml.load(metafile)["3D"]["include"]
if _includePositioning:
    cages = {"cages": ["all", "none"], "all_traces": []}
    for cageKey in meta:
        cageMeta = meta[cageKey]
        # should be cageMeta["name"], but is broken if multiple with same cage name
        cageName = cageKey
        cageGeoemtry = cageMeta["geometry"]
        cageTBRs = cageMeta["tbr"]
        cage = Cage(
            center=Point(cageGeoemtry["centerX"], cageGeoemtry["centerY"]),
            r=cageGeoemtry["radius"],
            b=cageGeoemtry["b"],
            cx=cageGeoemtry["cx"],
            cy=cageGeoemtry["cy"],
            tbr_serial_id=cageTBRs["tbrs"],
            tbrDepth=cageTBRs["depth"],
            linesDepths=cageTBRs["lines_depth"],
            circlesDepths=cageTBRs["circles_depth"],
            name=cageName,
        )
        cages.update({cageName: cage})
        cages["cages"].append(cageName)
        cages["all_traces"].append(cage.traces)
else:
    cages = {}
