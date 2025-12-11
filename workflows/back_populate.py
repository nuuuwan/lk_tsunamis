from utils import TimeUnit

from lk_tsunamis import Earthquake

if __name__ == "__main__":
    Earthquake.list_from_remote(
        time_window=TimeUnit.SECONDS_IN.AVG_YEAR * 100, min_magnitude=7
    )
    Earthquake.build_readme()
