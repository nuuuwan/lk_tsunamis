import json
import os
import re
from dataclasses import asdict, dataclass
from math import asin, cos, radians, sin, sqrt
from urllib.parse import urlencode
from urllib.request import urlopen

from utils import File, Format, JSONFile, Log, Time, TimeFormat

log = Log("Earthquake")


@dataclass
class Earthquake:
    lat_lng: tuple[float, float]
    magnitude: float
    title: str
    time_ut: int
    url: str

    DIR_DATA = "data"
    DIR_DATA_EARTHQUAKES = os.path.join(DIR_DATA, "earthquakes")

    @property
    def title_id(self) -> str:
        s = self.title.lower()
        s = re.sub(r"[^a-zA-Z0-9]+", " ", s)
        s = re.sub(r"\s+", "_", s).strip("_")
        return s

    @property
    def time_id(self) -> str:
        return TimeFormat.TIME_ID.format(Time(self.time_ut))

    @property
    def dir_parent_data(self) -> str:
        t = Time(self.time_ut)
        year = TimeFormat("%Y").format(t)
        year_month = TimeFormat("%Y-%m").format(t)
        year_month_day = TimeFormat("%Y-%m-%d").format(t)
        return os.path.join(
            self.DIR_DATA_EARTHQUAKES, year, year_month, year_month_day
        )

    @property
    def file_path(self) -> str:
        file_name = f"{self.time_id}.{self.title_id}.json"
        return os.path.join(self.dir_parent_data, file_name)

    @property
    def distance_to_lk(self) -> float:
        lk_lat, lk_lng = 7.8731, 80.7718

        lat1, lng1 = self.lat_lng
        lat2, lng2 = lk_lat, lk_lng

        lat1_rad = radians(lat1)
        lat2_rad = radians(lat2)
        delta_lat = radians(lat2 - lat1)
        delta_lng = radians(lng2 - lng1)

        a = (
            sin(delta_lat / 2) ** 2
            + cos(lat1_rad) * cos(lat2_rad) * sin(delta_lng / 2) ** 2
        )
        c = 2 * asin(sqrt(a))

        earth_radius_km = 6371.0
        return earth_radius_km * c

    def write_if_not_exists(self):
        if os.path.exists(self.file_path):
            return False
        os.makedirs(self.dir_parent_data, exist_ok=True)

        json_file = JSONFile(self.file_path)
        json_file.write(asdict(self))
        log.debug(f"Wrote {json_file}")
        return True

    @classmethod
    def from_geojson_feature(cls, feature: dict):
        return cls(
            lat_lng=(
                feature["geometry"]["coordinates"][1],
                feature["geometry"]["coordinates"][0],
            ),
            magnitude=feature["properties"]["mag"],
            title=feature["properties"]["title"],
            time_ut=feature["properties"]["time"] // 1000,
            url=feature["properties"]["url"],
        )

    @classmethod
    def list_all(cls):
        d_list = []
        for dirpath, _, filenames in os.walk(cls.DIR_DATA_EARTHQUAKES):
            for filename in filenames:
                if not filename.endswith(".json"):
                    continue
                file_path = os.path.join(dirpath, filename)
                json_file = JSONFile(file_path)
                data = json_file.read()
                d = cls(**data)
                d_list.append(d)
        log.debug(
            f'Read {
                len(d_list)} earthquake(s) from "{
                cls.DIR_DATA_EARTHQUAKES}"'
        )
        d_list.sort(key=lambda d: d.time_ut, reverse=True)
        return d_list

    @classmethod
    def list_from_remote(cls, time_window: int, min_magnitude: float):
        base_url = "https://earthquake.usgs.gov/fdsnws/event/1/query"
        start_ut = Time.now().ut - time_window
        start_time = TimeFormat.DATE.format(Time(start_ut))
        params = dict(
            format="geojson",
            starttime=start_time,
            minlatitude=-5,
            maxlatitude=20,
            minlongitude=60,
            maxlongitude=105,
            minmagnitude=min_magnitude,
        )
        url = f"{base_url}?{urlencode(params)}"
        log.debug(f"{url=}")

        data_json = None
        with urlopen(url) as response:
            data_json = response.read().decode("utf-8")
            assert data_json is not None, "Failed to download earthquake data"
        data = json.loads(data_json)
        features = data["features"]
        d_list = [cls.from_geojson_feature(f) for f in features]

        for d in d_list:
            d.write_if_not_exists()
        log.info(f"Loaded {len(d_list)} earthquake(s from {url}")
        return d_list

    @staticmethod
    def generate_markdown_table(
        earthquakes: list["Earthquake"], title: str
    ) -> list[str]:
        """Generate markdown table lines from a list of earthquakes."""
        lines = []
        lines.append(f"### {title}")
        lines.append("")
        lines.append(
            "| Date & Time | Magnitude | Location | "
            "Coordinates | Distance to LK |"
        )
        lines.append(
            "|------------:|----------:|----------|"
            "------------:|---------------:|"
        )

        for e in earthquakes:
            date_time = TimeFormat("%Y-%m-%d %H:%M:%S").format(
                Time(e.time_ut)
            )
            location = e.title.replace(f"M {e.magnitude} - ", "")
            lat, lng = e.lat_lng
            lat_dir = "N" if lat >= 0 else "S"
            lng_dir = "E" if lng >= 0 else "W"
            coords_text = (
                f"{abs(lat):.4f}° {lat_dir}, {abs(lng):.4f}° {lng_dir}"
            )
            maps_url = f"https://www.google.com/maps?q={lat},{lng}"
            coords_link = f"[{coords_text}]({maps_url})"
            distance_km = f"{e.distance_to_lk:,.0f} km"
            line = (
                f"| `{date_time}` | {e.magnitude} | "
                f"{location} | {coords_link} | {distance_km} |"
            )
            lines.append(line)

        return lines

    @classmethod
    def aggregate(cls):
        earthquakes = cls.list_all()

        recent_earthquakes = earthquakes[:10]
        recent_path = os.path.join(
            cls.DIR_DATA,
            "recent_earthquakes.json",
        )
        recent_file = JSONFile(recent_path)
        recent_file.write([asdict(e) for e in recent_earthquakes])
        log.info(f"Wrote {recent_file}")

        all_path = os.path.join(
            cls.DIR_DATA,
            "all_earthquakes.json",
        )
        all_file = JSONFile(all_path)
        all_file.write([asdict(e) for e in earthquakes])
        log.info(f"Wrote {all_file}")

    @classmethod
    def build_readme(cls):
        earthquakes = cls.list_all()
        max_time_ut = max([e.time_ut for e in earthquakes])
        time_str = TimeFormat.TIME.format(Time(max_time_ut))
        time_updated_for_badge = Format.badge(time_str)

        readme_path = "README.md"
        lines = [
            "# lk_tsunamis",
            "",
            "![Status: Live]"
            + "(https://img.shields.io/badge/status-live-brightgreen)",
            "![LastUpdated](https://img.shields.io/badge"
            + f"/last_updated-{time_updated_for_badge}-green)",
            "",
            "## Earthquakes near Sri Lanka 🇱🇰",
            "",
        ]

        latest_earthquakes = earthquakes[:10]
        lines.extend(
            cls.generate_markdown_table(
                latest_earthquakes, "Latest Earthquakes"
            )
        )

        most_severe_earthquakes = sorted(
            earthquakes, key=lambda e: e.magnitude, reverse=True
        )[:10]
        lines.extend(
            cls.generate_markdown_table(
                most_severe_earthquakes, "Most Severe Earthquakes"
            )
        )

        lines.extend(
            [
                "![Maintainer]"
                + "(https://img.shields.io/badge/maintainer-nuuuwan-red)",
                "![MadeWith]"
                + "(https://img.shields.io/badge/made_with-python-blue)",
                "[![License: MIT]"
                + "(https://img.shields.io/badge/License-MIT-yellow.svg)]"
                + "(https://opensource.org/licenses/MIT)",
                "",
            ]
        )

        readme_file = File(readme_path)
        readme_file.write_lines(lines)
        log.info(f"Wrote {readme_file}")
