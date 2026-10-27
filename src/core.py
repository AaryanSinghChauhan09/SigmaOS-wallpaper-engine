"""Wallpaper engine for SigmaOS-wallpaper-engine (inspired by owe).

Principles: pure queue/schedule computation (deterministic randomisation via
seeding, exact slideshow slot maths), plan-before-act (`set` prints the
gsettings command and writes a state file; the real desktop mutation only
happens under --execute, which self_test never runs).
"""
import argparse, datetime as dt, json, os, random, sys

ENGINE = {
    "name": "sigma-wallpaper",
    "summary": "Set, slideshow, randomise and schedule wallpapers",
    "language": "python",
    "verbs": ["set", "slideshow", "randomize", "list", "schedule"],
    "principles": ["Plan Before Act", "Separation of Concerns",
                   "Deterministic Testing", "Fail-Fast", "Defensive",
                   "KISS", "DRY"],
}

cli_doc = """\
$ sigma-wallpaper list --dir ~/Pictures/Wallpapers
  1  mountains.jpg
  2  dusk.png
$ sigma-wallpaper set ~/Pictures/Wallpapers/mountains.jpg --execute
$ sigma-wallpaper randomize --dir ~/Pictures/Wallpapers --seed 42
$ sigma-wallpaper slideshow --dir ~/Pictures/Wallpapers --interval 300
$ sigma-wallpaper schedule --start 8 --end 18 --days 0,2,4 \\
    --interval 60 --count 6 --from 2026-01-05
2026-01-05 08:00 mountains.jpg
"""

_IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".bmp", ".webp", ".svg")


class WallpaperError(ValueError):
    pass


def _read(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def build_queue(directory):
    """Ordered list of image paths in a directory (deterministic)."""
    if not os.path.isdir(directory):
        raise WallpaperError(f"no such directory: {directory!r}")
    queue = [os.path.join(directory, f)
             for f in sorted(os.listdir(directory))
             if f.lower().endswith(_IMAGE_EXTS)
             and os.path.isfile(os.path.join(directory, f))]
    if not queue:
        raise WallpaperError(f"no images found in {directory!r}")
    return queue


def plan_set(path, state):
    """Pure plan for setting one wallpaper; validates before any mutation."""
    if not os.path.isfile(path):
        raise WallpaperError(f"no such wallpaper: {path!r}")
    if not path.lower().endswith(_IMAGE_EXTS):
        raise WallpaperError(f"not an image file: {path!r}")
    prev = state.get("current")
    return {"path": path, "previous": prev,
            "cmd": ["gsettings", "set", "org.gnome.desktop.background",
                    "picture-uri", f"file://{path}"],
            "history": (state.get("history", []) + [path])[-50:]}


def randomize(queue, seed):
    """Deterministic shuffle; the same seed always yields the same order."""
    if not queue:
        raise WallpaperError("empty queue")
    if not isinstance(seed, int):
        raise WallpaperError(f"seed must be an integer, got {seed!r}")
    order = list(queue)
    random.Random(seed).shuffle(order)
    return order


def slideshow_plan(queue, interval_min, count=5, seed=None):
    """Plan the first `count` slideshow slots with offsets in minutes."""
    if not queue:
        raise WallpaperError("empty queue")
    if not 1 <= interval_min <= 24 * 60:
        raise WallpaperError(f"interval must be 1..1440 minutes, got "
                             f"{interval_min}")
    if not 1 <= count <= 1000:
        raise WallpaperError(f"count must be 1..1000, got {count}")
    order = randomize(queue, seed) if seed is not None else list(queue)
    return {"interval": interval_min, "order": order,
            "slots": [{"n": i, "at_min": i * interval_min,
                       "path": order[i % len(order)]}
                      for i in range(count)]}


def _parse_days(text):
    try:
        days = {int(d) for d in text.split(",") if d.strip() != ""}
    except ValueError as e:
        raise WallpaperError(f"bad --days {text!r}") from e
    if not days or any(d < 0 or d > 6 for d in days):
        raise WallpaperError(f"--days must be 0..6 (Mon..Sun), got {text!r}")
    return days


def _parse_date(text):
    try:
        return dt.datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError as e:
        raise WallpaperError(f"bad --from date {text!r} (want YYYY-MM-DD)") \
            from e


def schedule_plan(start_date, days, start_hour, end_hour, interval_min,
                  count):
    """Exact daily slot maths: weekdays in [start_hour, end_hour)."""
    if not 0 <= start_hour <= 23 or not 1 <= end_hour <= 24:
        raise WallpaperError("hours must be 0..23 / 1..24")
    if start_hour >= end_hour:
        raise WallpaperError(f"start hour {start_hour} must be before end "
                             f"hour {end_hour}")
    if not 1 <= interval_min <= 24 * 60:
        raise WallpaperError("interval must be 1..1440 minutes")
    if not 1 <= count <= 500:
        raise WallpaperError("count must be 1..500")
    slots, day, guard = [], start_date, 0
    while len(slots) < count and guard < 366:
        if day.weekday() in days:
            t = dt.datetime.combine(day, dt.time(start_hour))
            end = dt.datetime.combine(day, dt.time(end_hour))
            while t < end and len(slots) < count:
                slots.append(t)
                t += dt.timedelta(minutes=interval_min)
        day += dt.timedelta(days=1)
        guard += 1
    if not slots:
        raise WallpaperError("no slots land inside the daily window")
    return slots


def load_state(path):
    if not os.path.exists(path):
        return {}
    try:
        state = json.loads(_read(path))
    except json.JSONDecodeError as e:
        raise WallpaperError(f"corrupt state file: {e}") from e
    if not isinstance(state, dict):
        raise WallpaperError("corrupt state file: expected an object")
    return state


def save_state(path, state):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2, sort_keys=True)
    os.replace(tmp, path)


def _execute(plan):
    """Side-effect layer: mutate the real session. Never run by self_test."""
    import subprocess
    return subprocess.run(plan["cmd"], check=True).returncode


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=ENGINE["name"],
                                description=ENGINE["summary"])
    p.add_argument("--state",
                   default=os.path.expanduser(
                       "~/.local/state/sigma-wallpaper/state.json"))
    sub = p.add_subparsers(dest="cmd", required=True)
    st = sub.add_parser("set", help="set a single wallpaper (plan by default)")
    st.add_argument("path")
    st.add_argument("--execute", action="store_true",
                    help="actually talk to the desktop (side effects!)")
    sl = sub.add_parser("slideshow", help="plan a timed slideshow")
    sl.add_argument("--dir", required=True)
    sl.add_argument("--interval", type=int, default=900,
                    help="minutes between changes")
    sl.add_argument("--count", type=int, default=5)
    sl.add_argument("--seed", type=int, default=None)
    rz = sub.add_parser("randomize", help="deterministically shuffle a queue")
    rz.add_argument("--dir", required=True)
    rz.add_argument("--seed", type=int, required=True)
    ls = sub.add_parser("list", help="list the wallpaper queue")
    ls.add_argument("--dir", required=True)
    sc = sub.add_parser("schedule", help="plan slideshow start times")
    sc.add_argument("--dir", required=True)
    sc.add_argument("--start", type=int, required=True)
    sc.add_argument("--end", type=int, required=True)
    sc.add_argument("--days", required=True, help="comma list, 0=Mon")
    sc.add_argument("--interval", type=int, default=60)
    sc.add_argument("--count", type=int, default=6)
    sc.add_argument("--from", dest="start_date",
                    default="2026-01-05")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        state = load_state(args.state)
        if args.cmd == "set":
            plan = plan_set(os.path.abspath(args.path), state)
            print(" ".join(plan["cmd"]))
            state = {"current": plan["path"], "history": plan["history"]}
            if args.execute:
                _execute(plan)
                save_state(args.state, state)
                print(f"applied (state: {args.state})", file=sys.stderr)
            else:
                print("dry run: re-run with --execute to apply",
                      file=sys.stderr)
        elif args.cmd == "slideshow":
            queue = build_queue(args.dir)
            plan = slideshow_plan(queue, args.interval, count=args.count,
                                  seed=args.seed)
            for slot in plan["slots"]:
                when = dt.datetime.now() + \
                    dt.timedelta(minutes=slot["at_min"])
                print(f"+{slot['at_min']:>4} min  "
                      f"{when:%Y-%m-%d %H:%M}  {os.path.basename(slot['path'])}")
        elif args.cmd == "randomize":
            queue = build_queue(args.dir)
            for path in randomize(queue, args.seed):
                print(os.path.basename(path))
        elif args.cmd == "list":
            queue = build_queue(args.dir)
            current = state.get("current")
            for i, path in enumerate(queue, 1):
                mark = "*" if path == current else " "
                print(f"{mark}{i:>3}  {os.path.basename(path)}")
        elif args.cmd == "schedule":
            queue = build_queue(args.dir)
            slots = schedule_plan(_parse_date(args.start_date),
                                  _parse_days(args.days), args.start,
                                  args.end, args.interval, args.count)
            for i, when in enumerate(slots):
                path = queue[i % len(queue)]
                print(f"{when:%Y-%m-%d %H:%M}  {os.path.basename(path)}")
        return 0
    except WallpaperError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


def self_test() -> None:
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        ws = os.path.join(d, "Wallpapers")
        os.makedirs(ws)
        for name in ("mountains.jpg", "dusk.png", "notes.txt",
                     "cover.svg", "old.bmp"):
            open(os.path.join(ws, name), "w").close()
        empty = os.path.join(d, "empty")
        os.makedirs(empty)

        queue = build_queue(ws)
        assert [os.path.basename(p) for p in queue] == \
            ["cover.svg", "dusk.png", "mountains.jpg", "old.bmp"]
        try:
            build_queue(empty)
        except WallpaperError:
            pass
        else:
            raise AssertionError("empty dir accepted")
        try:
            build_queue(os.path.join(d, "ghost"))
        except WallpaperError:
            pass
        else:
            raise AssertionError("missing dir accepted")

        # plan_set: pure validation + command rendering
        target = os.path.join(ws, "mountains.jpg")
        plan = plan_set(target, {"current": None, "history": []})
        assert plan["cmd"][-1] == f"file://{target}"
        assert plan["history"] == [target]
        try:
            plan_set(os.path.join(ws, "notes.txt"), {})
        except WallpaperError:
            pass
        else:
            raise AssertionError("non-image accepted")
        try:
            plan_set(os.path.join(ws, "ghost.jpg"), {})
        except WallpaperError:
            pass
        else:
            raise AssertionError("missing file accepted")

        # deterministic randomisation
        a = randomize(queue, 42)
        b = randomize(queue, 42)
        c = randomize(queue, 7)
        assert a == b and sorted(a) == sorted(queue)
        assert c != queue or a != queue or len(queue) < 2
        try:
            randomize(queue, "not-an-int")
        except WallpaperError:
            pass
        else:
            raise AssertionError("bad seed accepted")

        # slideshow slots
        plan = slideshow_plan(queue, 300, count=4, seed=42)
        assert [s["at_min"] for s in plan["slots"]] == [0, 300, 600, 900]
        assert plan["slots"][0]["path"] == plan["order"][0]
        for bad in (lambda: slideshow_plan([], 5),
                    lambda: slideshow_plan(queue, 0),
                    lambda: slideshow_plan(queue, 1500),
                    lambda: slideshow_plan(queue, 5, count=0)):
            try:
                bad()
            except WallpaperError:
                pass
            else:
                raise AssertionError("expected WallpaperError")

        # schedule maths: Mon & Wed, 08-10, hourly, 5 slots from 2026-01-05
        slots = schedule_plan(dt.date(2026, 1, 5), {0, 2}, 8, 10, 60, 5)
        assert [s.strftime("%Y-%m-%d %H:%M") for s in slots] == [
            "2026-01-05 08:00", "2026-01-05 09:00",
            "2026-01-07 08:00", "2026-01-07 09:00",
            "2026-01-12 08:00",
        ]
        for bad in (lambda: schedule_plan(dt.date(2026, 1, 5), {0}, 10, 8, 60, 1),
                    lambda: schedule_plan(dt.date(2026, 1, 5), {9}, 8, 10, 60, 1),
                    lambda: schedule_plan(dt.date(2026, 1, 5), {0}, 8, 10, 0, 1),
                    lambda: _parse_days("0,7"),
                    lambda: _parse_days("monday"),
                    lambda: _parse_date("05-01-2026"),
                    lambda: schedule_plan(dt.date(2026, 1, 5), {0}, 8, 10, 60, 0)):
            try:
                bad()
            except WallpaperError:
                pass
            else:
                raise AssertionError("expected WallpaperError")

        # state roundtrip
        state_path = os.path.join(d, "state", "state.json")
        save_state(state_path, {"current": target, "history": [target]})
        assert load_state(state_path)["current"] == target
        assert load_state(os.path.join(d, "ghost.json")) == {}
        with open(os.path.join(d, "corrupt.json"), "w") as fh:
            fh.write("not json")
        try:
            load_state(os.path.join(d, "corrupt.json"))
        except WallpaperError:
            pass
        else:
            raise AssertionError("corrupt state accepted")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
