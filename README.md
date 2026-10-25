    # SigmaOS-wallpaper-engine

    Wallpaper set / slideshow / randomiser

    Part of the **SigmaOS** sovereign operating-system ecosystem — a multi-repository
    distribution modelled on Linux Mint and Omarchy Linux. See the parent
    [`SigmaOS`](https://github.com/AaryanSinghChauhan09/SigmaOS) repository for the
    full component index.

    ## Upstream inspirations
    - https://github.com/omacom/owe

    ## Design principles applied
    - **Plan Before Act**
- **Separation of Concerns**
- **Deterministic Testing**
- **Fail-Fast**
- **Defensive**
- **KISS**
- **DRY**

    ## Usage
    Verbs: `set, slideshow, randomize, list, schedule`

    ```
    $ sigma-wallpaper list --dir ~/Pictures/Wallpapers
  1  mountains.jpg
  2  dusk.png
$ sigma-wallpaper set ~/Pictures/Wallpapers/mountains.jpg --execute
$ sigma-wallpaper randomize --dir ~/Pictures/Wallpapers --seed 42
$ sigma-wallpaper slideshow --dir ~/Pictures/Wallpapers --interval 300
$ sigma-wallpaper schedule --start 8 --end 18 --days 0,2,4 \
    --interval 60 --count 6 --from 2026-01-05
2026-01-05 08:00 mountains.jpg

    ```

    ## Build & test
    ```
    make build
    make test
    ```

    ## Licence
    GNU General Public License v3.0 (FOSS).
