"""Print the three section-1 close views as JSON. No network and no server."""
import json

from shivai_r3.snapshot import close_views, to_plain


def main() -> None:
    print(json.dumps([to_plain(view) for view in close_views()], indent=2))


if __name__ == "__main__":
    main()
