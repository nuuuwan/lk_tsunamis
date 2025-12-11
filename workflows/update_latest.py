from utils import TimeUnit

from lk_tsunamis import Earthquake

if __name__ == "__main__":
    Earthquake.list_from_remote(
        time_window=TimeUnit.SECONDS_IN.WEEK, min_magnitude=4
    )
    Earthquake.build_readme()
